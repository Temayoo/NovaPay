# crud.py
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from time import sleep
from models import User, CompteBancaire, Depot, Transaction
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from schemas import (
    UserCreate,
    CompteBancaireCreate,
    DepotCreate,
    TransactionBase,
    CompteBancaireResponse,
)
import random
import string
from datetime import datetime

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ===========================
# User Management Functions
# ===========================


def verify_user_password(db: Session, user_id: int, password: str) -> bool:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    return verify_password(password, user.hashed_password)


def create_user(db: Session, user: UserCreate):
    # Crée un nouvel utilisateur dans la base de données
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hash_password(user.password),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def generate_iban() -> str:
    return "FR" + "".join(random.choices(string.digits, k=20))


def get_user_by_username(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


# ===========================
# Bank Account Management Functions
# ===========================
def create_premier_compte_bancaire(
    db: Session, compte: CompteBancaireCreate, user_id: int
):
    try:
        iban = generate_iban()
        solde = 0
        est_compte_courant = True
        nom = "Compte Courant"
        type = "Compte Courant"

        db_compte = CompteBancaire(
            nom=nom,
            type=type,
            solde=solde,
            iban=iban,
            est_compte_courant=est_compte_courant,
            user_id=user_id,
        )

        db.add(db_compte)
        db.commit()
        db.refresh(db_compte)
        return db_compte
    except Exception as e:
        print(f"Erreur lors de la création du compte: {e}")
        raise


def create_compte_bancaire(db: Session, compte: CompteBancaireCreate, user_id: int):
    try:
        iban = generate_iban()
        solde = 0
        est_compte_courant = False

        db_compte = CompteBancaire(
            nom=compte.nom,
            type=compte.type,
            solde=solde,
            iban=iban,
            est_compte_courant=est_compte_courant,
            user_id=user_id,
            date_creation=datetime.utcnow(),
        )

        db.add(db_compte)
        db.commit()
        db.refresh(db_compte)
        return db_compte
    except Exception as e:
        print(f"Erreur lors de la création du compte: {e}")
        raise


def create_depot(db: Session, depot: DepotCreate, compte_bancaire_id: int):
    # Crée un dépôt dans un compte bancaire
    try:
        compte = (
            db.query(CompteBancaire)
            .filter(CompteBancaire.id == compte_bancaire_id)
            .filter(CompteBancaire.date_deletion == None)
            .first()
        )
        if not compte:
            raise ValueError("Compte bancaire non trouvé")

        # Vérifie si le dépôt dépasse la limite de 50 000
        difference = compte.solde + depot.montant - 50000
        if difference > 0 and not compte.est_compte_courant:
            # Gérer le dépôt pour le compte secondaire
            compte.solde += depot.montant - difference
            db.add(compte)
            db.commit()
            db.refresh(compte)

            db_depot = Depot(
                montant=depot.montant - difference,
                description=depot.description,
                compte_bancaire_id=compte_bancaire_id,
            )
            db.add(db_depot)
            db.commit()
            db.refresh(db_depot)

            # Crée un nouveau dépôt pour le compte courant
            compte_courant = (
                db.query(CompteBancaire)
                .filter(CompteBancaire.user_id == compte.user_id)
                .filter(CompteBancaire.est_compte_courant == True)
                .filter(CompteBancaire.date_deletion == None)
                .first()
            )
            if not compte_courant:
                raise ValueError("Compte courant non trouvé")
            return create_depot(
                db=db,
                depot=DepotCreate(
                    montant=difference,
                    description=depot.description,
                    iban=compte_courant.iban,
                ),
                compte_bancaire_id=compte_courant.id,
            )

        compte.solde += depot.montant
        db.commit()
        db.refresh(compte)

        db_depot = Depot(
            montant=depot.montant,
            description=depot.description,
            compte_bancaire_id=compte_bancaire_id,
        )
        db.add(db_depot)
        db.commit()
        db.refresh(db_depot)

        return db_depot

    except ValueError as ve:
        raise ValueError(f"Erreur: {ve}")
    except SQLAlchemyError as e:
        db.rollback()
        raise Exception(f"Erreur lors de la création du dépôt: {e}")


# ===========================
# Transaction Management Functions
# ===========================
def create_transaction(
    db: Session,
    transaction: TransactionBase,
    compte_envoyeur: CompteBancaire,
    compte_receveur: CompteBancaire,
    status: int,
):

    compte_envoyeur.solde -= transaction.montant

    db_transaction = Transaction(
        montant=transaction.montant,
        description=transaction.description,
        compte_id_envoyeur=compte_envoyeur.id,
        compte_id_receveur=compte_receveur.id,
        status=status,
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    return db_transaction


def get_my_transactions(db: Session, compte_id: int):

    transactions = (
        db.query(Transaction)
        .filter(
            (Transaction.compte_id_envoyeur == compte_id)
            | (Transaction.compte_id_receveur == compte_id)
        )
        .filter(Transaction.date_deletion == None)
        .order_by(Transaction.date_creation.desc())
        .all()
    )

    response = []
    for transaction in transactions:

        response.append(
            {
                "id": transaction.id,
                "montant": transaction.montant,
                "description": transaction.description,
                "compte_envoyeur": CompteBancaireResponse.model_validate(
                    transaction.compte_envoyeur
                ),
                "compte_receveur": CompteBancaireResponse.model_validate(
                    transaction.compte_receveur
                ),
                "date_creation": transaction.date_creation,
                "status": transaction.status,
            }
        )

    return response


def asleep_transaction(
    db: Session, transaction: Transaction, compte_receveur: CompteBancaire
):
    sleep(50)
    transaction = (
        db.query(Transaction)
        .filter(Transaction.id == transaction.id)
        .filter(Transaction.date_deletion == None)
        .first()
    )
    compte_receveur = (
        db.query(CompteBancaire)
        .filter(CompteBancaire.id == compte_receveur.id)
        .filter(CompteBancaire.date_deletion == None)
        .first()
    )

    if transaction is None:
        print("Transaction introuvable.")
        return

    if transaction.status == 2:
        print("Transaction annulée.")
        return

    if transaction.status == 0:
        compte_receveur.solde += transaction.montant
        transaction.status = 1
        db.commit()
        db.refresh(compte_receveur)
        db.refresh(transaction)
        difference = check_account_limit(compte_receveur)
        if difference > 0:
            print(
                "Avertissement: Le compte receveur a été changé car il ne doit pas dépasser 50 000."
            )
            compte_courant = (
                db.query(CompteBancaire)
                .filter(CompteBancaire.user_id == compte_receveur.user_id)
                .filter(CompteBancaire.est_compte_courant == True)
                .filter(CompteBancaire.date_deletion == None)
                .first()
            )
            compte_courant.solde += difference
            db.commit()
            db.refresh(compte_courant)

            create_transaction(
                db=db,
                transaction=TransactionBase(
                    montant=difference,
                    description="Limite de compte dépassée",
                    compte_envoyeur=compte_receveur.iban,
                    compte_receveur=compte_courant.iban,
                ),
                compte_envoyeur=compte_receveur,
                compte_receveur=compte_courant,
                status=1,
            )


def check_account_limit(compte_bancaire: CompteBancaire):
    if compte_bancaire.solde > 50000 and not compte_bancaire.est_compte_courant:
        return compte_bancaire.solde - 50000
    return 0
