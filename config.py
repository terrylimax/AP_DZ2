import os
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.DEBUG)

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
TEMP_API_KEY = os.getenv("TEMP_API_KEY")