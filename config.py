import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Credentials
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    API_ID = int(os.environ.get("API_ID", 0))
    API_HASH = os.environ.get("API_HASH")
    SESSION_STRING = os.environ.get("SESSION_STRING")
    
    # Database
    MONGO_DB_URI = os.environ.get("MONGO_DB_URI")
    
    # Spotify
    SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    
    # Owner
    OWNER_ID = int(os.environ.get("OWNER_ID", 0))
    
    # Settings
    MAX_QUEUE_SIZE = int(os.environ.get("MAX_QUEUE_SIZE", 50))
    AUDIO_QUALITY = os.environ.get("AUDIO_QUALITY", "high")
    AUTO_LEAVE = os.environ.get("AUTO_LEAVE", "true").lower() == "true"
    
    # Validate
    @classmethod
    def validate(cls):
        required = ["BOT_TOKEN", "API_ID", "API_HASH", "SESSION_STRING", "MONGO_DB_URI", "OWNER_ID"]
        for var in required:
            if not getattr(cls, var):
                raise ValueError(f"❌ Missing: {var}")
        print("✅ All config loaded!")
