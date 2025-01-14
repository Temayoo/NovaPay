# main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base
from schemas import UserCreate, UserBase
from crud import create_user, get_user_by_username, verify_password
from jose import JWTError, jwt
from datetime import datetime, timedelta
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

# Créer la base de données et les tables si elles n'existent pas
Base.metadata.create_all(bind=engine)

# Initialisation de l'application FastAPI
app = FastAPI()

# Configuration de l'authentification OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

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

# Route pour enregistrer un utilisateur
@app.post("/register", response_model=UserBase)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return create_user(db=db, user=user)

# Route pour se connecter et obtenir un token
@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = get_user_by_username(db, username=form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Route protégée par authentification JWT
@app.get("/me", response_model=UserBase)
async def read_users_me(current_user: UserBase = Depends(get_current_user)):
    return current_user
