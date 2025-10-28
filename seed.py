import asyncio
import datetime as dt

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.routes.auth import _hash_password


async def main():
    try:
        client = AsyncIOMotorClient(settings.MONGO_URI)
        await client.server_info()
        db = client[settings.MONGO_DB_NAME]

        # Seed admin user
        email = "domagojhack@gmail.com"
        password = "AquilaNQ4"
        existing = await db["users"].find_one({"email": email})
        if not existing:
            doc = {
                "email": email,
                "password_hash": _hash_password(password),
                "created_at": dt.datetime.utcnow().isoformat(),
            }
            await db["users"].insert_one(doc)
            print(f"Seeded admin user: {email}")
        else:
            print("Admin user already exists")

        client.close()
    except Exception as e:
        print(f"Seeding failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())