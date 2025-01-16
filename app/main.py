import threading
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base, Transaction, CompteBancaire, Depot
from schemas import (
    UserCreate,
    UserBase,
    CompteBancaireCreate,
    DepotCreate,
    CompteBancaireResponse,
    DepotResponse,
    TransactionBase,
)
from crud import (
    create_user,
    get_user_by_username,
    verify_password,
    create_compte_bancaire,
    create_premier_compte_bancaire,
    get_user_by_email,
    create_depot,
    create_transaction,
    get_my_transactions,
    asleep_transaction,
)
from jose import JWTError, jwt
from datetime import datetime, timedelta

from schemas import UserLogin, TransactionResponse
from database import SessionLocal, engine, Base
from models import User
from schemas import UserBase, UserCreate
from crud import create_user, get_user_by_username, verify_password
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES


Base.metadata.create_all(bind=engine)

app = FastAPI()

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
        compte=CompteBancaireCreate(nom="Compte Courant", est_compte_courant=True),
        user_id=db_user.id,
    )

    create_depot(
        db=db,
        depot=DepotCreate(montant=100, iban=compte_courant.iban),
        compte_bancaire_id=compte_courant.id,
    )

    return db_user


@app.post("/login", tags=["Authentication"])
async def login(form_data: UserLogin, db: Session = Depends(get_db)):
    print(form_data)
    user = get_user_by_username(db, email=form_data.email)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/me", response_model=UserBase, tags=["User"])
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


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

@app.patch("/compte-courant/cloture/{id_compte_courant}", tags=["Bank Account"])
def cloture_compte_courant(
    id_compte_courant: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    compte = db.query(CompteBancaire).get(id_compte_courant)

    if not compte:
        raise HTTPException(status_code=404, detail="Compte not found")
    if compte.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="You are not the owner of this account"
        )
    if compte.est_compte_courant:
        raise HTTPException(status_code=400, detail="This account is a current account")

    compte_courant = (
        db.query(CompteBancaire)
        .filter(CompteBancaire.user_id == current_user.id)
        .filter(CompteBancaire.est_compte_courant == True)
        .filter(CompteBancaire.date_deletion == None)
        .first()
    )

    if not compte_courant:
        raise HTTPException(status_code=404, detail="No current account found")

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


# ===========================
# Transaction Features
# ===========================
@app.post("/transactions", response_model=TransactionResponse, tags=["Transaction"])
def send_transaction(transaction: TransactionBase, db: Session = Depends(get_db)):
    db_transaction = create_transaction(db=db, transaction=transaction)
    threading.Thread(
        target=asleep_transaction,
        args=(db, db_transaction, db_transaction.compte_receveur),
    ).start()

    return TransactionResponse(
        id=db_transaction.id,
        montant=db_transaction.montant,
        description=db_transaction.description,
        compte_envoyeur=db_transaction.compte_envoyeur.iban,
        compte_receveur=db_transaction.compte_receveur.iban,
        date_creation=db_transaction.date_creation,
        status=db_transaction.status,
    )


@app.get(
    "/transactions", response_model=list[TransactionResponse], tags=["Transaction"]
)
def get_transactions(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return get_my_transactions(db=db, user_id=current_user.id)


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
    transaction.date_deletion = datetime.utcnow()
    db.commit()
    db.refresh(compte_envoyeur)
    db.refresh(transaction)
    return {"message": "Transaction annulée avec succès"}


@app.get("/transactions/{transaction_id}", tags=["Transaction"])
def get_transaction_details(transaction_id: int, db: Session = Depends(get_db)):
    transaction = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id)
        .filter(Transaction.date_deletion == None)
        .first()
    )

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction introuvable")
    return {
        "id": transaction.id,
        "date": transaction.date_creation,
        "montant": str(transaction.montant),
        "description": transaction.description,
        "status": transaction.status,
        "compte_envoyeur": {
            "details": transaction.compte_envoyeur,
        },
        "compte_receveur": {
            "details": transaction.compte_receveur,
        },
    }