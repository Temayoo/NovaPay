# schemas.py
from pydantic import BaseModel, root_validator
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


class UserInDB(UserBase):
    hashed_password: str


class CompteBancaireCreate(BaseModel):
    nom: str

    class Config:
        orm_mode = True


class CompteBancaireResponse(BaseModel):
    nom: str
    iban: str
    solde: Decimal
    date_creation: datetime

    class Config:
        orm_mode = True


class DepotCreate(BaseModel):
    montant: Decimal

    class Config:
        orm_mode = True


class DepotResponse(BaseModel):
    date: datetime
    montant: Decimal
    compte_nom: str
    compte_iban: str

    class Config:
        orm_mode = True
