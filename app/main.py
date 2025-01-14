from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base
from schemas import UserCreate, UserBase, CompteBancaireCreate
from crud import create_user, get_user_by_username, verify_password, create_compte_bancaire
from jose import JWTError, jwt
from datetime import datetime, timedelta

from schemas import UserLogin
from database import SessionLocal, engine, Base
from models import User
from schemas import UserBase, UserCreate
from crud import create_user, get_user_by_username, verify_password
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

# Créer la base de données et les tables si elles n'existent pas
Base.metadata.create_all(bind=engine)

# Initialisation de l'application FastAPI
app = FastAPI()

# Configuration de l'authentification HTTPBearer
http_bearer = HTTPBearer()

# Fonction pour créer un token JWT
def create_access_token(data: dict, expires_delta: timedelta = timedelta(minutes=15)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Fonction pour obtenir la session de la base de données
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Fonction pour obtenir l'utilisateur actuel basé sur le token JWT
def get_current_user(token: str = Depends(http_bearer), db: Session = Depends(get_db)):
    try:
        # Extraire le token depuis l'en-tête HTTP
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Could not validate credentials")

        # Recherche de l'utilisateur dans la base de données
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise HTTPException(status_code=401, detail="Could not validate credentials")
        return user  # Renvoie l'utilisateur complet
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")


# Route pour enregistrer un utilisateur
@app.post("/register", response_model=UserBase)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = get_user_by_username(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return create_user(db=db, user=user)


# Route pour se connecter et obtenir un token
@app.post("/login")
async def login(form_data: UserLogin, db: Session = Depends(get_db)):
    user = get_user_by_username(db, email=form_data.email)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


# Route protégée par authentification JWT pour récupérer les informations de l'utilisateur connecté
@app.get("/me", response_model=UserBase)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user  # Renvoie l'utilisateur complet

@app.post("/comptes-bancaires/")
def create_compte(compte: CompteBancaireCreate, db: Session = Depends(get_db)):
    user_id = 1
    return create_compte_bancaire(db=db, compte=compte, user_id=user_id)
