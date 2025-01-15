# crud.py
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from time import sleep
from models import User, CompteBancaire, Depot, Transaction
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from schemas import UserCreate, CompteBancaireCreate, DepotCreate, TransactionBase
import random
import string
from datetime import datetime

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_user(db: Session, user: UserCreate):
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


def create_premier_compte_bancaire(
    db: Session, compte: CompteBancaireCreate, user_id: int
):
    try:
        iban = generate_iban()
        solde = 0
        est_compte_courant = True
        nom = "Compte Courant"

        db_compte = CompteBancaire(
            nom=nom,
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
        print(f"Error during account creation: {e}")
        raise


def create_compte_bancaire(db: Session, compte: CompteBancaireCreate, user_id: int):
    try:
        iban = generate_iban()
        solde = 0
        est_compte_courant = False

        db_compte = CompteBancaire(
            nom=compte.nom,
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
        print(f"Error during account creation: {e}")
        raise


def create_depot(db: Session, depot: DepotCreate, compte_bancaire_id: int):
    try:
        compte = (
            db.query(CompteBancaire)
            .filter(CompteBancaire.id == compte_bancaire_id)
            .first()
        )
        if not compte:
            raise ValueError("Compte bancaire non trouvé")

        db_depot = Depot(montant=depot.montant, compte_bancaire_id=compte_bancaire_id)

        db.add(db_depot)
        db.commit()
        db.refresh(db_depot)

        compte.solde += depot.montant
        db.commit()
        db.refresh(compte)

        difference = check_account_limit(compte)
        if difference > 0:
            compte_courant = (
                db.query(CompteBancaire)
                .filter(CompteBancaire.user_id == compte.user_id)
                .filter(CompteBancaire.est_compte_courant == True)
                .first()
            )
            print(compte_courant)
            create_transaction(
                db=db,
                transaction=TransactionBase(
                    montant=difference,
                    description="Limite de compte dépassée",
                    compte_envoyeur=compte.iban,
                    compte_receveur=compte_courant.iban,
                ),
            )
            compte_courant.solde += difference
            db.commit()
            db.refresh(compte_courant)
        return db_depot

    except ValueError as ve:
        raise ValueError(f"Erreur: {ve}")
    except SQLAlchemyError as e:
        db.rollback()
        raise Exception(f"Erreur lors de la création du dépôt: {e}")


def get_user_by_username(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def get_my_transactions(db: Session, user_id: int):
    transactions = (
        db.query(Transaction)
        .filter(
            (Transaction.compte_id_envoyeur == user_id)
            | (Transaction.compte_id_receveur == user_id)
        )
        .order_by(Transaction.date_creation.desc())
        .all()
    )

    response = []
    for transaction in transactions:
        compte_envoyeur = (
            db.query(CompteBancaire)
            .filter(CompteBancaire.id == transaction.compte_id_envoyeur)
            .first()
        )
        compte_receveur = (
            db.query(CompteBancaire)
            .filter(CompteBancaire.id == transaction.compte_id_receveur)
            .first()
        )

        response.append(
            {
                "id": transaction.id,
                "montant": transaction.montant,
                "description": transaction.description,
                "compte_envoyeur": compte_envoyeur.iban,
                "compte_receveur": compte_receveur.iban,
                "date_creation": transaction.date_creation,
                "status": transaction.status,
            }
        )

    return response


def create_transaction(db: Session, transaction: TransactionBase):
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
    if not compte_envoyeur:
        raise ValueError("Compte source non trouvé")
    elif not compte_receveur:
        raise ValueError("Compte de destination non trouvé")
    elif compte_envoyeur.solde < transaction.montant:
        raise ValueError("Solde insuffisant")
    elif compte_envoyeur.id == compte_receveur.id:
        raise ValueError(
            "Le compte envoyeur et le compte receveur ne peuvent pas être identiques"
        )
    elif transaction.montant <= 0:
        raise ValueError(
            "Le montant de la transaction ne peut pas être inférieur ou égal à 0"
        )

    compte_envoyeur.solde -= transaction.montant

    db_transaction = Transaction(
        montant=transaction.montant,
        description=transaction.description,
        compte_id_envoyeur=compte_envoyeur.id,
        compte_id_receveur=compte_receveur.id,
        status=0,
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    return db_transaction


def asleep_transaction(
    db: Session, transaction: Transaction, compte_receveur: CompteBancaire
):
    sleep(10)
    transaction = db.query(Transaction).filter(Transaction.id == transaction.id).first()
    compte_receveur = (
        db.query(CompteBancaire).filter(CompteBancaire.id == compte_receveur.id).first()
    )

    if transaction is None:
        print("Transaction not found.")
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
                .first()
            )
            create_transaction(
                db=db,
                transaction=TransactionBase(
                    montant=difference,
                    description="Limite de compte dépassée",
                    compte_envoyeur=compte_receveur.iban,
                    compte_receveur=compte_courant.iban,
                ),
            )
            compte_courant.solde += difference
            db.commit()
            db.refresh(compte_courant)

def check_account_limit(compte_bancaire: CompteBancaire):
    if compte_bancaire.solde > 50000 and not compte_bancaire.est_compte_courant:
        return compte_bancaire.solde - 50000
    return 0

