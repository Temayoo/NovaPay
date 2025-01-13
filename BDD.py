from sqlmodel import Session, create_engine, Field, SQLModel
from typing import Optional

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    email: str = Field(index=True)
    password: str


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


# Crée les tables si elles n'existent pas déjà
create_db_and_tables()
