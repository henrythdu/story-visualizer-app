import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    def __init__(self):
        # API Keys
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.STABILITY_API_KEY = os.getenv("STABILITY_API_KEY", "")
        
        # Model settings
        self.LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")
        self.IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gemini-2.0-flash-exp-image-generation")
        
        # Directories
        self.OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
        self.IMAGE_OUTPUT_DIR = os.path.join(self.OUTPUT_DIR, "images")
        self.AUDIO_OUTPUT_DIR = os.path.join(self.OUTPUT_DIR, "audio")
        self.VIDEO_OUTPUT_DIR = os.path.join(self.OUTPUT_DIR, "videos")
        
        # Create directories if they don't exist
        os.makedirs(self.IMAGE_OUTPUT_DIR, exist_ok=True)
        os.makedirs(self.AUDIO_OUTPUT_DIR, exist_ok=True)
        os.makedirs(self.VIDEO_OUTPUT_DIR, exist_ok=True)