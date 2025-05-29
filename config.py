from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')
POSTGRES_URI = os.getenv("POSTGRES_URI")

print(BOT_TOKEN, ADMIN_ID)