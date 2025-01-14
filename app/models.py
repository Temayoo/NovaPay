from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Numeric, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=False, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    comptes_bancaires = relationship(
        "CompteBancaire", back_populates="user", cascade="all, delete-orphan"
    )


class CompteBancaire(Base):
    __tablename__ = "comptes_bancaires"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, index=True)
    solde = Column(Numeric(precision=10, scale=2), default=0.00)
    iban = Column(String, unique=True, index=True)
    est_compte_courant = Column(Boolean, default=False)
    user_id = Column(Integer, ForeignKey("users.id"))

    user = relationship("User", back_populates="comptes_bancaires")

    deposits = relationship(
        "Depot", back_populates="compte_bancaire", cascade="all, delete-orphan"
    )


class Depot(Base):
    __tablename__ = "depot"

    id = Column(Integer, primary_key=True, index=True)
    montant = Column(Numeric(precision=10, scale=2))
    date = Column(DateTime, default=datetime.utcnow)
    compte_bancaire_id = Column(Integer, ForeignKey("comptes_bancaires.id"))

    compte_bancaire = relationship("CompteBancaire", back_populates="deposits")
