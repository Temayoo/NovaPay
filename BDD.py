from sqlmodel import Session, create_engine, Field, SQLModel
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from typing import Optional


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session


create_db_and_tables()