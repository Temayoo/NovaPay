from sqlmodel import Session, create_engine, Field, SQLModel
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    email: str = Field(index=True)
    password: str

class CreateUser(BaseModel):
    name: str
    email: str
    password: str

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session


create_db_and_tables()

@app.post("/users/")
def create_user(body: CreateUser, session = Depends(get_session)) -> User:
    user = User(name=body.name, email=body.email, password=body.password)
    session.add(user)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user