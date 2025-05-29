import asyncio
import database
from bot import start_bot


async def main():
    await database.setup()
    await start_bot()


if __name__ == "__main__":
    asyncio.run(main())