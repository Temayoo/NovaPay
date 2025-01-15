# crud.py
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from models import User, CompteBancaire, Depot
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from schemas import UserCreate, CompteBancaireCreate, DepotCreate
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
            date_creation=datetime.utcnow()
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
