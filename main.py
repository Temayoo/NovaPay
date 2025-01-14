from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import uvicorn

# --- Configuration des paramètres ---
SECRET_KEY = "your_secret_key_here"  # Clé pour signer les tokens JWT
ALGORITHM = "HS256"  # Algorithme de cryptage
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Durée d'expiration du token

DATABASE_URL = "sqlite:///./test.db"  # URL de la base de données SQLite

# --- Configuration de SQLAlchemy ---
Base = declarative_base()  # Classe de base pour les modèles
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})  # Création de l'engine
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)  # Configuration de la session

# --- Création de l'application FastAPI ---
app = FastAPI()

# --- Configuration de la sécurité ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")  # Hachage des mots de passe
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")  # Schéma d'authentification OAuth2

# --- Modèle SQLAlchemy pour l'utilisateur ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

# --- Création des tables dans la base de données ---
Base.metadata.create_all(bind=engine)

# --- Dépendance pour la session de base de données ---
def get_db():
    db = SessionLocal()  # Création d'une nouvelle session
    try:
        yield db  # Renvoie la session pour utilisation
    finally:
        db.close()  # Ferme la session après utilisation

# --- Fonctions liées aux utilisateurs ---
def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()  # Récupère un utilisateur par son nom d'utilisateur

def create_user(db: Session, username: str, password: str):
    hashed_password = pwd_context.hash(password)  # Hache le mot de passe
    db_user = User(username=username, hashed_password=hashed_password)  # Crée un nouvel utilisateur
    db.add(db_user)  # Ajoute l'utilisateur à la session
    db.commit()  # Valide les changements dans la base de données
    db.refresh(db_user)  # Rafraîchit l'utilisateur pour obtenir l'ID généré
    return db_user  # Retourne l'utilisateur créé

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)  # Vérifie si le mot de passe en clair correspond au haché

def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)  # Récupère l'utilisateur
    if not user or not verify_password(password, user.hashed_password):  # Vérifie l'authenticité
        return None
    return user  # Retourne l'utilisateur authentifié

# --- Fonctions pour le token JWT ---
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()  # Copie des données à encoder
    expire = datetime.now() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))  # Définit l'expiration
    to_encode.update({"exp": expire})  # Ajoute l'expiration aux données
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)  # Encode et retourne le token

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])  # Décode le token
        username: str = payload.get("sub")  # Récupère le nom d'utilisateur
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")  # Vérifie la validité
        return username  # Retourne le nom d'utilisateur
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")  # Gère les erreurs de décodage

# --- Routes de l'API ---
@app.post("/register", response_model=dict)
def register(username: str, password: str, db: Session = Depends(get_db)):
    if get_user_by_username(db, username):  # Vérifie si l'utilisateur existe déjà
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    user = create_user(db, username, password)  # Crée un nouvel utilisateur
    return {"username": user.username, "message": "User created successfully"}  # Retourne un message de succès

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)  # Authentifie l'utilisateur
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")  # Gère l'échec d'authentification
    access_token = create_access_token(data={"sub": user.username})  # Crée un token d'accès
    return {"access_token": access_token, "token_type": "bearer"}  # Retourne le token

@app.get("/users/me")
def read_users_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    print(f"Received token: {token}")
    username = decode_access_token(token)  # Décode le token pour obtenir le nom d'utilisateur
    user = get_user_by_username(db, username)  # Récupère l'utilisateur
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")  # Gère l'absence d'utilisateur
    return {"username": user}  # Retourne les informations de l'utilisateur

# --- Démarrage de l'application ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)