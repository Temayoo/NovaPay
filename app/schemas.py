# schemas.py
from pydantic import BaseModel, root_validator, ConfigDict
from decimal import Decimal
from datetime import datetime


class UserBase(BaseModel):
    username: str
    email: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserCreate(UserBase):
    password: str

    @root_validator(pre=True)
    def check_email(cls, values):
        if "@" not in values.get("email"):
            raise ValueError("Email must contain an @")
        return values

    class Config:
        orm_mode = True

    @root_validator(pre=True)
    def check_password(cls, values):
        password = values.get("password")
        if password:
            if not any(c.islower() for c in password):
                raise ValueError("Password must contain at least one lowercase letter.")
            if not any(c.isupper() for c in password):
                raise ValueError("Password must contain at least one uppercase letter.")
            if not any(c.isdigit() for c in password):
                raise ValueError("Password must contain at least one number.")
        return values


class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str

    @root_validator(pre=True)
    def check_password(cls, values):
        password = values.get("new_password")
        if password:
            if not any(c.islower() for c in password):
                raise ValueError("Password must contain at least one lowercase letter.")
            if not any(c.isupper() for c in password):
                raise ValueError("Password must contain at least one uppercase letter.")
            if not any(c.isdigit() for c in password):
                raise ValueError("Password must contain at least one number.")
        return values


class UserInDB(UserBase):
    hashed_password: str


class CompteBancaireCreate(BaseModel):
    nom: str
    type: str

    class Config:
        orm_mode = True


class CompteBancaireResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nom: str
    type: str
    iban: str
    solde: float
    est_compte_courant: bool
    date_creation: datetime


class DepotCreate(BaseModel):
    montant: Decimal
    description: str
    iban: str

    class Config:
        orm_mode = True


class DepotResponse(BaseModel):
    date: datetime
    montant: Decimal
    description: str
    compte_nom: str
    compte_iban: str

    class Config:
        orm_mode = True


class TransactionBase(BaseModel):
    montant: Decimal
    description: str
    compte_envoyeur: str
    compte_receveur: str


class TransactionResponse(BaseModel):
    id: int
    type: str
    montant: Decimal
    description: str
    compte_envoyeur: CompteBancaireResponse
    compte_receveur: CompteBancaireResponse
    date_creation: datetime
    status: int

    class Config:
        orm_mode = True


class BeneficiaireCreate(BaseModel):
    pseudo: str
    iban: str

    class Config:
        orm_mode = True


class BeneficiaireResponse(BaseModel):
    id: int
    compte: CompteBancaireResponse
    pseudo: str

class PrelevementAutomatiqueCreate(BaseModel):
    montant: Decimal
    description: str
    frequence: str
    date_debut: datetime = datetime.utcnow()
    compte_envoyeur_iban: str
    compte_receveur_iban: str

    class Config:
        orm_mode = True

