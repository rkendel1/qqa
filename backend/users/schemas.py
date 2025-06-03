from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None
    address: str | None = None
    verified: bool = False

class UserRead(BaseModel):
    id: int
    email: EmailStr
    first_name: str | None
    last_name: str | None
    address: str | None
    verified: bool

    class Config:
        orm_mode = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str