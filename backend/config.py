import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Models
MODEL_PLANNER = "nvidia/nemotron-3.5-lightning:free"
MODEL_CONTENT = "nvidia/nemotron-3.5-lightning:free"

# Tour Settings
WORDS_PER_MINUTE = 150
