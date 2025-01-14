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
    TransactionCreate
)
from crud import (
    create_user,
    get_user_by_username,
    verify_password,
    create_compte_bancaire,
    create_premier_compte_bancaire,
    get_user_by_email,
    create_depot,
)
from jose import JWTError, jwt
from datetime import datetime, timedelta

from schemas import UserLogin
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
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=401, detail="Could not validate credentials"
            )

        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise HTTPException(
                status_code=401, detail="Could not validate credentials"
            )
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")


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
        db=db, depot=DepotCreate(montant=100), compte_bancaire_id=compte_courant.id
    )

    return db_user


@app.post("/login", tags=["Authentication"])
async def login(form_data: UserLogin, db: Session = Depends(get_db)):
    user = get_user_by_username(db, email=form_data.email)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/me", response_model=UserBase, tags=["User"])
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.post("/comptes-bancaires/", tags=["Bank Account"])
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
        .all()
    )
    return comptes


@app.post("/depot", tags=["Deposits"])
def create_depot_endpoint(
    depot: DepotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if depot.montant <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif")

    compte_bancaire = (
        db.query(CompteBancaire)
        .filter(CompteBancaire.user_id == current_user.id)
        .filter(CompteBancaire.est_compte_courant == True)
        .first()
    )

    if not compte_bancaire:
        raise HTTPException(status_code=404, detail="Compte courant non trouvé")

    try:
        new_depot = create_depot(
            db=db, depot=depot, compte_bancaire_id=compte_bancaire.id
        )
        return new_depot
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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


@app.post("/send", response_model=TransactionCreate)
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db)):
    return create_transaction(db=db, transaction=transaction)