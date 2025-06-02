from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
# ADMIN_ID = ["ВАШ_АДМИН_ИД_1", "ВАШ_АДМИН_ИД_2"] # Список ID администраторов в виде строк

ADMIN_IDS_STR = os.getenv("ADMIN_ID")
ADMIN_ID = [admin_id.strip() for admin_id in ADMIN_IDS_STR.split(',')]


POSTGRES_URI = os.getenv("POSTGRES_URI")

print(BOT_TOKEN, ADMIN_ID)