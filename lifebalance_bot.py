from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import datetime
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()  # Loads HF_TOKEN and BOT_TOKEN from Railway env vars

# --- DATA STORAGE (Simple JSON file - works for personal use) ---
DATA_FILE = "user_data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# --- NVIDIA/HUGGING FACE AI SETUP ---
HF_API_URL = "https://api-inference.huggingface.co/models/"
HEADERS = {"Authorization": f"Bearer {os.getenv('HF_TOKEN')}"}
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "nvidia/Llama3-ChatQA-1.5-8B")

def query_hf_model(payload, model=None):
    """Query Hugging Face hosted NVIDIA model"""
    model = model or DEFAULT_MODEL
    response = requests.post(f"{HF_API_URL}{model}", headers=HEADERS, json=payload)
    return response.json()

# --- AI PROMPT TEMPLATES ---
def build_suggestion_prompt(user_context):
    return f"""
