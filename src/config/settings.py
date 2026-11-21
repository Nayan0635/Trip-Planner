import os

from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = "nvidia"

# API_KEYS
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# models
LLM_MODEL = {
    "nvidia": "nvidia/nemotron-3-ultra-550b-a55b",
    "gemini": "gemini-2.5-flash",
    "gemini": "gemini-3.1-flash-lite",
    "groq": "qwen/qwen3.8-27b",
    "groq": "openai/gpt-oss-120b",
}[LLM_PROVIDER]

# Travel data service credentials.
OPENTRIPMAP_API_KEY = os.getenv("OPENTRIPMAP_API_KEY")
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
