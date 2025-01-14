# crud.py
from sqlalchemy.orm import Session
from models import User
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from schemas import UserCreate
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

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


# Fonction pour obtenir un utilisateur par son nom d'utilisateur
def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()
