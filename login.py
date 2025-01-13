from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlmodel import Session

from BDD import get_session, User

app = FastAPI()

class CreateUser(BaseModel):
    name: str
    email: str
    password: str

@app.post("/users/")
def create_user(body: CreateUser, session: Session = Depends(get_session)) -> User:
    user = User(name=body.name, email=body.email, password=body.password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
