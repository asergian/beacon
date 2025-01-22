# app/__init__.py
from flask import Flask
from .config import Config  # Import the Config class from config.py
from dotenv import load_dotenv

import openai
import logging

# Load environment variables from the .env file (if present)
load_dotenv()

app = Flask(__name__)

# Load the configurations from config.py
app.config.from_object(Config)

openai.api_key = app.config['OPENAI_API_KEY']

# Set up logging from the config
logging_level = app.config['LOGGING_LEVEL']
logging.basicConfig(level=logging_level, format="%(asctime)s - %(levelname)s - %(message)s")

print('app initalized')
from . import routes  # Import routes to register them with the app