import threading
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base, Transaction, CompteBancaire, Depot, Beneficiaire
from schemas import (
    UserCreate,
    UserBase,
    CompteBancaireCreate,
    DepotCreate,
    CompteBancaireResponse,
    DepotResponse,
    TransactionBase,
    PasswordUpdate,
    TransactionResponse,
    BeneficiaireCreate,
    BeneficiaireResponse,
)
from crud import (
    create_user,
    get_user_by_username,
    verify_password,
    verify_user_password,
    create_compte_bancaire,
    create_premier_compte_bancaire,
    get_user_by_email,
    create_depot,
    create_transaction,
    asleep_transaction,
    # create_beneficiaire,
    hash_password,
)
from jose import JWTError, jwt
from datetime import datetime, timedelta

from schemas import UserLogin, TransactionResponse
from database import SessionLocal, engine, Base
from models import User
from schemas import UserBase, UserCreate
from crud import create_user, get_user_by_username, verify_password
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, ORIGIN


Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGIN,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

http_bearer = HTTPBearer()


def create_access_token(data: dict, expires_delta: timedelta = timedelta(minutes=15)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = Depends(http_bearer), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=401, detail="Could not validate credentials"
            )

        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise HTTPException(
                status_code=401, detail="Could not validate credentials"
            )
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")


# ===========================
# Authentication Features
# ===========================
@app.post("/register", response_model=UserBase, tags=["Authentication"])
async def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    db_user = create_user(db=db, user=user)

    compte_courant = create_premier_compte_bancaire(
        db=db,
        compte=CompteBancaireCreate(
            nom="Compte Courant", type="Compte Courant", est_compte_courant=True
        ),
        user_id=db_user.id,
    )

    create_depot(
        db=db,
        depot=DepotCreate(
            montant=100,
            iban=compte_courant.iban,
            description="Dépôt initial",
        ),
        compte_bancaire_id=compte_courant.id,
    )

    return db_user


@app.post("/login", tags=["Authentication"])
async def login(form_data: UserLogin, db: Session = Depends(get_db)):
    user = get_user_by_username(db, email=form_data.email)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/me", response_model=UserBase, tags=["User"])
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.post("/verify-password", tags=["User"])
def verify_password_endpoint(
    password: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> bool:
    return verify_user_password(db, current_user.id, password)


@app.post("/change-password", tags=["Authentication"])
async def change_password(
    password_data: PasswordUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    if password_data.old_password == password_data.new_password:
        raise HTTPException(
            status_code=400,
            detail="Le nouveau mot de passe ne doit pas être identique à l'ancien.",
        )

    if not verify_user_password(db, current_user.id, password_data.old_password):
        raise HTTPException(status_code=400, detail="Ancien mot de passe incorrect")

    hashed_password = hash_password(password_data.new_password)

    current_user.hashed_password = hashed_password
    db.add(current_user)
    db.commit()

    return {"message": "Mot de passe modifié avec succès"}


# ===========================
# Bank Account Features
# ===========================
@app.post("/comptes-bancaires", tags=["Bank Account"])
def create_compte(
    compte: CompteBancaireCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="User not authenticated")
    print(f"Current user ID: {current_user.id}")

    return create_compte_bancaire(db=db, compte=compte, user_id=current_user.id)


@app.get(
    "/comptes-bancaires",
    response_model=list[CompteBancaireResponse],
    tags=["Bank Account"],
)
def get_comptes_bancaires(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    comptes = (
        db.query(CompteBancaire)
        .filter(CompteBancaire.user_id == current_user.id)
        .filter(CompteBancaire.date_deletion == None)
        .order_by(CompteBancaire.date_creation.desc())
        .all()
    )
    return comptes


@app.get(
    "/comptes-bancaires/{compte_id}",
    response_model=CompteBancaireResponse,
    tags=["Bank Account"],
)
def get_compte_bancaire(
    compte_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    compte = (
        db.query(CompteBancaire)
        .filter(CompteBancaire.id == compte_id)
        .filter(CompteBancaire.date_deletion == None)
        .first()
    )
    if not compte:
        raise HTTPException(status_code=404, detail="Compte bancaire non trouvé")
    if compte.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Vous n'avez pas les permissions nécessaires pour accéder à ce compte",
        )
    return compte


@app.get(
    "/compte-courant",
    response_model=list[CompteBancaireResponse],
    tags=["Bank Account"],
)
def get_comptes_bancaires(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    comptes = (
        db.query(CompteBancaire)
        .filter(CompteBancaire.user_id == current_user.id)
        .filter(CompteBancaire.est_compte_courant == True)
        .filter(CompteBancaire.date_deletion == None)
        .all()
    )
    return comptes


@app.patch("/comptes-bancaires/cloture/{id_compte}", tags=["Bank Account"])
def cloture_compte_bancaire(
    id_compte: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    compte = db.query(CompteBancaire).get(id_compte)

    # Récupération des transactions en cours
    transactions = (
        db.query(Transaction)
        .filter(
            (Transaction.compte_id_envoyeur == id_compte)
            | (Transaction.compte_id_receveur == id_compte)
        )
        .filter(Transaction.date_deletion == None)
        .filter(Transaction.status == 0)
        .all()
    )

    if transactions:
        raise HTTPException(
            status_code=400, detail="Ce compte contient des transactions en cours"
        )
    if not compte:
        raise HTTPException(status_code=404, detail="Compte non trouvé")
    if compte.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Vous n'êtes pas le propriétaire de ce compte"
        )
    if compte.est_compte_courant:
        raise HTTPException(status_code=400, detail="Ce compte est un compte courant")

    compte_courant = (
        db.query(CompteBancaire)
        .filter(CompteBancaire.user_id == current_user.id)
        .filter(CompteBancaire.est_compte_courant == True)
        .filter(CompteBancaire.date_deletion == None)
        .first()
    )

    if not compte_courant:
        raise HTTPException(status_code=404, detail="Aucun compte courant trouvé")

    compte_courant.solde += compte.solde

    compte.solde = 0
    compte.date_deletion = datetime.utcnow()

    db.add(compte)
    db.add(compte_courant)

    db.commit()

    db.refresh(compte)
    db.refresh(compte_courant)

    return compte


# ===========================
# Deposit Features
# ===========================
@app.get("/depots", response_model=list[DepotResponse], tags=["Deposits"])
def get_depots(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    depots = (
        db.query(Depot)
        .join(CompteBancaire)
        .filter(CompteBancaire.user_id == current_user.id)
        .all()
    )

    depots_response = [
        DepotResponse(
            date=depot.date,
            montant=depot.montant,
            description=depot.description,
            compte_nom=depot.compte_bancaire.nom,
            compte_iban=depot.compte_bancaire.iban,
        )
        for depot in depots
    ]

    return depots_response


@app.post("/depot", tags=["Deposits"])
def create_depot_endpoint(
    depot: DepotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if depot.montant <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif")

    # Recherche du compte bancaire avec l'IBAN fourni
    compte_bancaire = (
        db.query(CompteBancaire)
        .filter(CompteBancaire.user_id == current_user.id)
        .filter(CompteBancaire.iban == depot.iban)
        .filter(CompteBancaire.date_deletion == None)
        .first()
    )

    if not compte_bancaire:
        raise HTTPException(
            status_code=404,
            detail=f"Compte bancaire avec IBAN {depot.iban} introuvable",
        )
    try:
        new_depot = create_depot(
            db=db, depot=depot, compte_bancaire_id=compte_bancaire.id
        )
        return new_depot
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Erreur lors de la création du dépôt: {e}"
        )


@app.get("/{compte_id}/depots", response_model=list[DepotResponse], tags=["Deposits"])
def get_depot(
    compte_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    compte = (
        db.query(CompteBancaire)
        .filter(CompteBancaire.id == compte_id)
        .filter(CompteBancaire.user_id == current_user.id)
        .filter(CompteBancaire.date_deletion == None)
        .first()
    )
    if not compte:
        raise HTTPException(status_code=404, detail="Compte bancaire introuvable")
    if compte.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Vous n'avez pas les permissions nécessaires pour accéder à ces dépôts",
        )
    depots = (
        db.query(Depot)
        .filter(Depot.compte_bancaire_id == compte_id)
        .filter(Depot.date_deletion == None)
        .all()
    )

    depots_response = [
        DepotResponse(
            date=depot.date,
            montant=depot.montant,
            description=depot.description,
            compte_nom=depot.compte_bancaire.nom,
            compte_iban=depot.compte_bancaire.iban,
        )
        for depot in depots
    ]

    return depots_response


# ===========================
# Transaction Features
# ===========================
@app.get(
    "/{compte_id}/recette",
    response_model=list[TransactionResponse],
    tags=["Transaction"],
)
def get_recette(
    compte_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transactions = (
        db.query(Transaction)
        .join(CompteBancaire, Transaction.compte_id_receveur == CompteBancaire.id)
        .filter(CompteBancaire.user_id == current_user.id)
        .filter(CompteBancaire.id == compte_id)
        .filter(Transaction.date_deletion == None)
        .filter(Transaction.status != 2)
        .order_by(Transaction.date_creation.desc())
        .all()
    )

    transactions_response = [
        TransactionResponse(
            id=transaction.id,
            type="recette",
            montant=transaction.montant,
            description=transaction.description,
            compte_envoyeur=CompteBancaireResponse.model_validate(
                transaction.compte_envoyeur
            ),
            compte_receveur=CompteBancaireResponse.model_validate(
                transaction.compte_receveur
            ),
            date_creation=transaction.date_creation,
            status=transaction.status,
        )
        for transaction in transactions
    ]

    return transactions_response


@app.get(
    "/{compte_id}/depense",
    response_model=list[TransactionResponse],
    tags=["Transaction"],
)
def get_depense(
    compte_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transactions = (
        db.query(Transaction)
        .join(CompteBancaire, Transaction.compte_id_envoyeur == CompteBancaire.id)
        .filter(CompteBancaire.user_id == current_user.id)
        .filter(CompteBancaire.id == compte_id)
        .filter(Transaction.date_deletion == None)
        .filter(Transaction.status != 2)
        .order_by(Transaction.date_creation.desc())
        .all()
    )

    transactions_response = [
        TransactionResponse(
            id=transaction.id,
            type="depense",
            montant=transaction.montant,
            description=transaction.description,
            compte_envoyeur=CompteBancaireResponse.model_validate(
                transaction.compte_envoyeur
            ),
            compte_receveur=CompteBancaireResponse.model_validate(
                transaction.compte_receveur
            ),
            date_creation=transaction.date_creation,
            status=transaction.status,
        )
        for transaction in transactions
    ]

    return transactions_response


@app.get(
    "/transactions", response_model=list[TransactionResponse], tags=["Transaction"]
)
def get_all_transactions(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    depenses = (
        db.query(Transaction)
        .join(CompteBancaire, Transaction.compte_id_envoyeur == CompteBancaire.id)
        .filter(CompteBancaire.user_id == current_user.id)
        .filter(Transaction.date_deletion == None)
        .filter(Transaction.status != 2)
        .order_by(Transaction.date_creation.desc())
        .all()
    )

    depense_responce = [
        TransactionResponse(
            id=depense.id,
            type="depense",
            montant=depense.montant,
            description=depense.description,
            compte_envoyeur=CompteBancaireResponse.model_validate(
                depense.compte_envoyeur
            ),
            compte_receveur=CompteBancaireResponse.model_validate(
                depense.compte_receveur
            ),
            date_creation=depense.date_creation,
            status=depense.status,
        )
        for depense in depenses
    ]

    recettes = (
        db.query(Transaction)
        .join(CompteBancaire, Transaction.compte_id_receveur == CompteBancaire.id)
        .filter(CompteBancaire.user_id == current_user.id)
        .filter(Transaction.date_deletion == None)
        .filter(Transaction.status != 2)
        .order_by(Transaction.date_creation.desc())
        .all()
    )

    recette_response = [
        TransactionResponse(
            id=recette.id,
            type="recette",
            montant=recette.montant,
            description=recette.description,
            compte_envoyeur=CompteBancaireResponse.model_validate(
                recette.compte_envoyeur
            ),
            compte_receveur=CompteBancaireResponse.model_validate(
                recette.compte_receveur
            ),
            date_creation=recette.date_creation,
            status=recette.status,
        )
        for recette in recettes
    ]

    return depense_responce + recette_response


@app.post("/transactions", response_model=int, tags=["Transaction"])
def send_transaction(
    transaction: TransactionBase,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    compte_envoyeur = (
        db.query(CompteBancaire)
        .filter(CompteBancaire.iban == transaction.compte_envoyeur)
        .filter(CompteBancaire.date_deletion == None)
        .first()
    )
    compte_receveur = (
        db.query(CompteBancaire)
        .filter(CompteBancaire.iban == transaction.compte_receveur)
        .filter(CompteBancaire.date_deletion == None)
        .first()
    )

    if compte_envoyeur.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Vous n'avez pas les permissions nécessaires pour effectuer cette transaction",
        )
    if not compte_envoyeur:
        raise HTTPException(
            status_code=400,
            detail="Compte source non trouvé",
        )
    elif not compte_receveur:
        raise HTTPException(
            status_code=400,
            detail="Compte de destination non trouvé",
        )
    elif compte_envoyeur.solde < transaction.montant:
        raise HTTPException(
            status_code=400,
            detail="Solde insuffisant",
        )
    elif compte_envoyeur.id == compte_receveur.id:
        raise HTTPException(
            status_code=400,
            detail="Le compte envoyeur et le compte receveur ne peuvent pas être identiques",
        )
    elif transaction.montant <= 0:
        raise HTTPException(
            status_code=400,
            detail="Le montant de la transaction ne peut pas être inférieur ou égal à 0",
        )
    db_transaction = create_transaction(
        db=db,
        transaction=transaction,
        compte_envoyeur=compte_envoyeur,
        compte_receveur=compte_receveur,
        status=0,
    )
    threading.Thread(
        target=asleep_transaction,
        args=(db, db_transaction, db_transaction.compte_receveur),
    ).start()

    # return TransactionResponse(
    #     id=db_transaction.id,
    #     type='depense',
    #     montant=db_transaction.montant,
    #     description=db_transaction.description,
    #     compte_envoyeur=CompteBancaireResponse.model_validate(
    #         db_transaction.compte_envoyeur
    #     ),
    #     compte_receveur=CompteBancaireResponse.model_validate(
    #         db_transaction.compte_receveur
    #     ),
    #     date_creation=db_transaction.date_creation,
    #     status=db_transaction.status,
    # )
    return db_transaction.id


@app.post("/transactions/{transaction_id}/cancel", tags=["Transaction"])
def cancel_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    compte_envoyeur = (
        db.query(CompteBancaire)
        .filter(CompteBancaire.id == transaction.compte_id_envoyeur)
        .first()
    )

    if transaction.status != 0:
        raise HTTPException(
            status_code=400, detail="Impossible d'annuler cette transaction"
        )
    elif compte_envoyeur.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Vous n'avez pas les permissions nécessaires pour annuler cette transaction",
        )

    compte_envoyeur.solde += transaction.montant
    transaction.status = 2
    db.commit()
    db.refresh(compte_envoyeur)
    db.refresh(transaction)
    return {"message": "Transaction annulée avec succès"}


@app.get("/transactions/{transaction_id}", tags=["Transaction"])
def get_transaction_details(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transaction = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id)
        .filter(Transaction.date_deletion == None)
        .first()
    )

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction introuvable")

    compte_envoyeur = (
        db.query(CompteBancaire)
        .filter(CompteBancaire.id == transaction.compte_id_envoyeur)
        .filter(CompteBancaire.date_deletion == None)
        .first()
    )
    compte_receveur = (
        db.query(CompteBancaire)
        .filter(CompteBancaire.id == transaction.compte_id_receveur)
        .filter(CompteBancaire.date_deletion == None)
        .first()
    )

    if (
        compte_envoyeur.user_id != current_user.id
        and compte_receveur.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=403,
            detail="Vous n'avez pas les permissions nécessaires pour accéder à cette transaction",
        )

    return {
        "id": transaction.id,
        "montant": transaction.montant,
        "description": transaction.description,
        "compte_envoyeur": compte_envoyeur.iban,
        "compte_receveur": compte_receveur.iban,
        "date_creation": transaction.date_creation,
        "status": transaction.status,
    }


# ===========================
# Beneficiaire Features
# ===========================


@app.post("/beneficiaire", tags=["Beneficiaire"])
def create_beneficiaire(
    beneficiaire: BeneficiaireCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    compte = (
        db.query(CompteBancaire)
        .filter(CompteBancaire.iban == beneficiaire.iban)
        .first()
    )
    if not compte:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Compte bancaire non trouvé"
        )
    if compte.user_id == current_user.id:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez pas ajouter votre propre compte comme beneficiaire",
        )
    db_beneficiaire = Beneficiaire(
        pseudo=beneficiaire.pseudo,
        user_id=current_user.id,
        comptes_id=compte.id,
    )
    db.add(db_beneficiaire)
    db.commit()
    db.refresh(db_beneficiaire)
    return db_beneficiaire


@app.get("/beneficiaire", tags=["Beneficiaire"])
def get_beneficiaire(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    beneficiaire = (
        db.query(Beneficiaire, CompteBancaire)
        .join(CompteBancaire, Beneficiaire.comptes_id == CompteBancaire.id)
        .filter(Beneficiaire.user_id == current_user.id)
        .filter(CompteBancaire.date_deletion == None)
        .all()
    )

    return [
        BeneficiaireResponse(
            id=b.id, compte=CompteBancaireResponse.model_validate(c), pseudo=b.pseudo
        )
        for b, c in beneficiaire
    ]
