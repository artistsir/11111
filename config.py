import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Token from @BotFather
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    
    # Telegram API from my.telegram.org
    API_ID = int(os.environ.get("API_ID", 0))
    API_HASH = os.environ.get("API_HASH")
    
    # MongoDB from mongodb.com (Free Cluster)
    MONGO_DB_URI = os.environ.get("MONGO_DB_URI")
    
    # Spotify (Optional) from developer.spotify.com
    SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    
    # Owner ID
    OWNER_ID = int(os.environ.get("OWNER_ID", 0))