import os
from dotenv import load_dotenv

load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY", "your_huggingface_api_key")
HF_MODEL = "meta-llama/Llama-3.2-1B-Instruct"  # Free tier model