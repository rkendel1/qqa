import asyncio
from users.database import engine
from users.models import Base

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ User database initialized")

if __name__ == "__main__":
    asyncio.run(init_db())