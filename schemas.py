# schemas.py
from pydantic import BaseModel, root_validator


class UserBase(BaseModel):
    username: str
    email: str


class UserCreate(UserBase):
    password: str

    @root_validator(pre=True)
    def check_password(cls, values):
        password = values.get("password")
        if password:
            if not any(
                c.islower() for c in password
            ):  # Vérifie la présence de minuscule
                raise ValueError("Password must contain at least one lowercase letter.")
            if not any(
                c.isupper() for c in password
            ):  # Vérifie la présence de majuscule
                raise ValueError("Password must contain at least one uppercase letter.")
            if not any(c.isdigit() for c in password):  # Vérifie la présence de chiffre
                raise ValueError("Password must contain at least one number.")
        return values


class UserInDB(UserBase):
    hashed_password: str
