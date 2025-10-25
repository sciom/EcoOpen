import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    try:
        client = AsyncIOMotorClient("mongodb://localhost:27017")
        db = client["ecoopen"]
        await db["users"].find_one()
        print("Connection and query successful")
        client.close()
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())