from tortoise import Tortoise 
from config import POSTGRES_URI

TORTOISE_ORM = {
    "connections": {
        "default": POSTGRES_URI,
    },
    "apps": {
        "models": {
            "models": ["database.models"],
            "default_connection": "default",
        },
    },
}


async def setup():
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()