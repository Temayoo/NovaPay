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
    date_creation = Column(DateTime, default=datetime.utcnow)
    date_deletion = Column(DateTime, default=None)

    # Relations
    comptes_bancaires = relationship(
        "CompteBancaire", back_populates="user", cascade="all, delete-orphan"
    )


class CompteBancaire(Base):
    __tablename__ = "comptes_bancaires"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, index=True)
    type = Column(String, default=None)
    solde = Column(Numeric(precision=10, scale=2), default=0.00)
    iban = Column(String, unique=True, index=True)
    est_compte_courant = Column(Boolean, default=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    date_creation = Column(DateTime, default=datetime.utcnow)
    date_deletion = Column(DateTime, default=None)

    # Relations
    user = relationship("User", back_populates="comptes_bancaires")

    deposits = relationship(
        "Depot", back_populates="compte_bancaire", cascade="all, delete-orphan"
    )

    transactions_envoyees = relationship(
        "Transaction",
        foreign_keys="Transaction.compte_id_envoyeur",
        back_populates="compte_envoyeur",
        cascade="all, delete-orphan",
    )
    transactions_reçues = relationship(
        "Transaction",
        foreign_keys="Transaction.compte_id_receveur",
        back_populates="compte_receveur",
        cascade="all, delete-orphan",
    )


class Depot(Base):
    __tablename__ = "depot"

    id = Column(Integer, primary_key=True, index=True)
    montant = Column(Numeric(precision=10, scale=2))
    description = Column(String)
    date = Column(DateTime, default=datetime.utcnow)
    compte_bancaire_id = Column(Integer, ForeignKey("comptes_bancaires.id"))
    date_creation = Column(DateTime, default=datetime.utcnow)
    date_deletion = Column(DateTime, default=None)

    # Relations
    compte_bancaire = relationship("CompteBancaire", back_populates="deposits")


class Transaction(Base):
    __tablename__ = "transaction"

    id = Column(Integer, primary_key=True, index=True)
    date_creation = Column(DateTime, default=datetime.utcnow)
    date_deletion = Column(DateTime, default=None)
    montant = Column(Numeric(precision=10, scale=2))
    description = Column(String)
    status = Column(Integer, default=0)
    compte_id_envoyeur = Column(
        Integer, ForeignKey("comptes_bancaires.id"), nullable=True
    )
    compte_id_receveur = Column(
        Integer, ForeignKey("comptes_bancaires.id"), nullable=True
    )

    # Relations
    compte_envoyeur = relationship(
        "CompteBancaire",
        foreign_keys=[compte_id_envoyeur],
        back_populates="transactions_envoyees",
    )
    compte_receveur = relationship(
        "CompteBancaire",
        foreign_keys=[compte_id_receveur],
        back_populates="transactions_reçues",
    )
