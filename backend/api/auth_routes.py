from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from users.models import User
from users.schemas import UserCreate, UserLogin, AuthResponse
from users.auth import hash_password, verify_password, create_access_token
from users.database import get_db

router = APIRouter()

@router.post("/signup", response_model=AuthResponse)
async def signup(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter_by(email=user.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")

    db_user = User(
        email=user.email,
        hashed_password=hash_password(user.password),
        first_name=user.first_name,
        last_name=user.last_name,
        address=user.address,
        verified=user.verified,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    access_token = create_access_token({"sub": db_user.email})
    return {
        "id": db_user.id,
        "email": db_user.email,
        "first_name": db_user.first_name,
        "last_name": db_user.last_name,
        "address": db_user.address,
        "verified": db_user.verified,
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/login", response_model=AuthResponse)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter_by(email=credentials.email))
    user = result.scalars().first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    access_token = create_access_token({"sub": user.email})
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "address": user.address,
        "verified": user.verified,
        "access_token": access_token,
        "token_type": "bearer"
    }