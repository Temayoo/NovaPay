# database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./database.db"  # Chemin vers la base de données SQLite locale

# Création de l'engine de base de données
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Session locale
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base pour la déclaration des modèles
Base = declarative_base()
