import os
import asyncio
import sys
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from youtube_search import YoutubeSearch
import pymongo
from config import Config
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp
from datetime import datetime

# Keep bot alive for Render
from flask import Flask, render_template
import threading

# Flask app for web server (Render requirement)
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "🎵 Banana Music Bot is Running! 🍌"

def run_flask():
    web_app.run(host='0.0.0.0', port=5000)

# Start Flask in a separate thread
flask_thread = threading.Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

# Initialize MongoDB
try:
    mongo_client = pymongo.MongoClient(Config.MONGO_DB_URI)
    db = mongo_client["banana_music_bot"]
    users_collection = db["users"]
    queue_collection = db["queue"]
    print("✅ MongoDB Connected Successfully")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")

# Initialize Spotify
spotify = None
if Config.SPOTIFY_CLIENT_ID and Config.SPOTIFY_CLIENT_SECRET:
    try:
        auth_manager = SpotifyClientCredentials(
            client_id=Config.SPOTIFY_CLIENT_ID,
            client_secret=Config.SPOTIFY_CLIENT_SECRET
        )
        spotify = spotipy.Spotify(auth_manager=auth_manager)
        print("✅ Spotify Initialized")
    except Exception as e:
        print(f"❌ Spotify Error: {e}")

# Global variables for PyTgCalls
calls = {}

# Function to get YouTube URL
def get_youtube_url(query):
    try:
        results = YoutubeSearch(query, max_results=1).to_dict()
        if results:
            video_id = results[0]['id']
            return f"https://www.youtube.com/watch?v={video_id}"
    except Exception as e:
        print(f"YouTube Search Error: {e}")
    return None

# Function to get audio stream URL
def get_audio_stream(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extractaudio': True,
        'audioformat': 'mp3',
        'outtmpl': '%(id)s.%(ext)s',
        'noplaylist': True,
        'cookiefile': 'cookies.txt'
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info['url']
    except Exception as e:
        print(f"Audio Stream Error: {e}")
        return None

# Initialize Pyrogram Client
app = Client(
    "banana_music_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

# Initialize PyTgCalls
pytgcalls = PyTgCalls(app)

# Store user data
async def add_user(user_id):
    try:
        users_collection.update_one(
            {'user_id': user_id},
            {'$set': {'joined_date': datetime.now()}},
            upsert=True
        )
    except Exception as e:
        print(f"Database Error: {e}")

# Start Command with Welcome Message
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    await add_user(user_id)
    
    welcome_text = f"""
    🍌 **Welcome to Banana Music Bot!** 🎵
    
    👋 **Hello {message.from_user.first_name}!**
    
    **I can play music in voice chats!**
    
    **Available Commands:**
    ▶️ /play [song name] - Play a song
    ⏩ /skip - Skip current song
    ⏸️ /pause - Pause playback
    ▶️ /resume - Resume playback
    ⏹️ /stop - Stop playback
    📋 /queue - Show current queue
    ❓ /help - Show help message
    
    **To use me:**
    1. Add me to your group
    2. Make me admin
    3. Start a voice chat
    4. Use /play [song name]
    
    Made with ❤️ by Banana Bot Team
    """
    
    await message.reply_text(welcome_text)

# Help Command
@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    help_text = """
    🆘 **Banana Music Bot Help** 🍌
    
    **Basic Commands:**
    /start - Start the bot
    /help - Show this help message
    
    **Music Commands:**
    /play [song name or URL] - Play a song
    /skip - Skip current song
    /pause - Pause playback
    /resume - Resume playback
    /stop - Stop playback
    /queue - Show current queue
    
    **Examples:**
    • `/play Shape of You`
    • `/play https://youtube.com/watch?v=xxx`
    
    **Need help?** Contact @YourUsername
    """
    await message.reply_text(help_text)

# Play Command
@app.on_message(filters.command("play"))
async def play_command(client: Client, message: Message):
    try:
        # Check if user is in voice chat
        if not message.from_user:
            await message.reply_text("❌ Please use this command in a group!")
            return
            
        # Get song query
        if len(message.command) < 2:
            await message.reply_text("❌ Please provide a song name!\nExample: `/play Shape of You`")
            return
            
        query = " ".join(message.command[1:])
        await message.reply_text(f"🔍 **Searching for:** `{query}`")
        
        # Get YouTube URL
        youtube_url = get_youtube_url(query)
        if not youtube_url:
            await message.reply_text("❌ Song not found!")
            return
            
        # Get audio stream URL
        await message.reply_text("📥 **Downloading audio...**")
        audio_url = get_audio_stream(youtube_url)
        
        if not audio_url:
            await message.reply_text("❌ Failed to get audio stream!")
            return
            
        # Join voice chat
        chat_id = message.chat.id
        if chat_id not in calls:
            try:
                call = await client.join_group_call(
                    chat_id,
                    AudioPiped(audio_url)
                )
                calls[chat_id] = call
                await message.reply_text(f"🎵 **Now Playing:** `{query}`")
            except Exception as e:
                await message.reply_text(f"❌ Failed to join voice chat!\nError: {str(e)}")
        else:
            # Already in call, just play
            await calls[chat_id].change_stream(
                AudioPiped(audio_url)
            )
            await message.reply_text(f"🎵 **Now Playing:** `{query}`")
            
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# Skip Command
@app.on_message(filters.command("skip"))
async def skip_command(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in calls:
        # Implement your queue logic here
        await message.reply_text("⏩ **Song skipped!**")
    else:
        await message.reply_text("❌ **I'm not playing anything!**")

# Stop Command
@app.on_message(filters.command("stop"))
async def stop_command(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in calls:
        try:
            await client.leave_group_call(chat_id)
            del calls[chat_id]
            await message.reply_text("⏹️ **Playback stopped!**")
        except Exception as e:
            await message.reply_text(f"❌ Error: {str(e)}")
    else:
        await message.reply_text("❌ **I'm not in a voice chat!**")

# Pause Command
@app.on_message(filters.command("pause"))
async def pause_command(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in calls:
        await calls[chat_id].pause()
        await message.reply_text("⏸️ **Playback paused!**")
    else:
        await message.reply_text("❌ **I'm not playing anything!**")

# Resume Command
@app.on_message(filters.command("resume"))
async def resume_command(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in calls:
        await calls[chat_id].resume()
        await message.reply_text("▶️ **Playback resumed!**")
    else:
        await message.reply_text("❌ **I'm not playing anything!**")

# Stats Command
@app.on_message(filters.command("stats"))
async def stats_command(client: Client, message: Message):
    try:
        total_users = users_collection.count_documents({})
        await message.reply_text(f"📊 **Bot Statistics:**\n\n👥 **Total Users:** `{total_users}`\n🍌 **Bot Status:** `Running`")
    except Exception as e:
        await message.reply_text(f"❌ Error getting stats: {str(e)}")

# Keep-alive message
@app.on_message(filters.command("ping"))
async def ping_command(client: Client, message: Message):
    await message.reply_text("🏓 **Pong!**\n🍌 **Banana Bot is alive!**")

# Run the bot
async def main():
    print("🚀 Starting Banana Music Bot...")
    await app.start()
    print("✅ Bot Started Successfully!")
    
    # Keep the bot running
    await idle()
    
    await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(" Bot stopped by user")
    except Exception as e:
        print(f" Bot error: {e}")