# crud.py
from sqlalchemy.orm import Session
from models import User, CompteBancaire
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from schemas import UserCreate, CompteBancaireCreate
import random
import string

# Initialiser le contexte de cryptage de mot de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Fonction pour hacher les mots de passe
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# Fonction pour vérifier les mots de passe
def verify_password(plain_password, hashed_password) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# Fonction pour créer un utilisateur
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
    return "FR" + ''.join(random.choices(string.digits, k=20))


def create_compte_bancaire(db: Session, compte: CompteBancaireCreate, user_id: int):
    try:
        iban = generate_iban()
        solde = 0

        db_compte = CompteBancaire(
            nom=compte.nom,
            solde=solde,
            iban=iban,
            est_compte_courant=compte.est_compte_courant,
            user_id=user_id,
        )

        db.add(db_compte)
        db.commit()
        db.refresh(db_compte)
        return db_compte
    except Exception as e:
        print(f"Error during account creation: {e}")
        raise


# Fonction pour obtenir un utilisateur par son nom d'utilisateur
def get_user_by_username(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()
