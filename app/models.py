from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Numeric
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=False, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class CompteBancaire(Base):
    __tablename__ = "comptes_bancaires"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, index=True)
    solde = Column(Numeric(precision=10, scale=2))
    iban = Column(String, unique=True, index=True)
    est_compte_courant = Column(Boolean, default=False)
    user_id = Column(Integer, ForeignKey('users.id'))

    user = relationship("User", back_populates="comptes_bancaires")

User.comptes_bancaires = relationship("CompteBancaire", back_populates="user", cascade="all, delete-orphan")
