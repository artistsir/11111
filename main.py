import os
import asyncio
import sys
import re
from typing import Dict, List, Optional

# Fix PyTgCalls import based on available version
try:
    from pytgcalls import PyTgCalls, StreamType
    from pytgcalls.types import Update
    from pytgcalls.types.input_stream import AudioPiped, AudioParameters
    from pytgcalls.types.input_stream.quality import HighQualityAudio, MediumQualityAudio, LowQualityAudio
    PYTGCALLS_AVAILABLE = True
    print("✅ Using pytgcalls dev version")
except ImportError:
    try:
        # Try alternative package
        from py_tgcalls import PyTgCalls
        from py_tgcalls.types import Update, AudioPiped, AudioParameters, HighQualityAudio
        PYTGCALLS_AVAILABLE = True
        StreamType = None
        print("✅ Using py-tgcalls stable version")
    except ImportError:
        PYTGCALLS_AVAILABLE = False
        print("❌ PyTgCalls not available")

# Pyrogram
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# YouTube
from youtube_search import YoutubeSearch
import yt_dlp

# Spotify
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# MongoDB
from pymongo import MongoClient

# Flask
from flask import Flask
import threading

# Config
from config import Config

# ============================================
# 🚀 FLASK WEB SERVER
# ============================================
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "🎵 Banana Music Bot 🍌"

@web_app.route('/ping')
def ping():
    return "🏓 Pong!"

def run_web():
    web_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# Start web server
web_thread = threading.Thread(target=run_web, daemon=True)
web_thread.start()

# ============================================
# 🗄️ DATABASE
# ============================================
try:
    mongo_client = MongoClient(Config.MONGO_DB_URI, serverSelectionTimeoutMS=5000)
    mongo_client.server_info()  # Test connection
    db = mongo_client["banana_music_bot"]
    users_db = db["users"]
    print("✅ MongoDB Connected")
except Exception as e:
    print(f"⚠️ MongoDB Warning: {e}")
    users_db = None

# ============================================
# 🎵 MUSIC QUEUE
# ============================================
class MusicQueue:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.queue: List[Dict] = []
        self.current: Optional[Dict] = None
    
    def add(self, song: Dict) -> int:
        self.queue.append(song)
        return len(self.queue)
    
    def get(self) -> Optional[Dict]:
        if self.queue:
            self.current = self.queue.pop(0)
            return self.current
        return None
    
    def clear(self):
        self.queue = []
        self.current = None
    
    def list(self) -> List[Dict]:
        return self.queue

# Global storage
queues: Dict[int, MusicQueue] = {}
active_chats: Dict[int, bool] = {}

# ============================================
# 🤖 CLIENTS
# ============================================
bot_client = Client(
    name="banana_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    in_memory=True
)

assistant_client = Client(
    name="banana_assistant",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    session_string=Config.SESSION_STRING,
    in_memory=True
)

# Initialize PyTgCalls if available
if PYTGCALLS_AVAILABLE:
    pytgcalls = PyTgCalls(assistant_client)
else:
    pytgcalls = None
    print("⚠️ PyTgCalls not installed - VC features disabled")

# ============================================
# 🎧 AUDIO FUNCTIONS
# ============================================
def get_audio_quality():
    quality_map = {
        "low": LowQualityAudio(),
        "medium": MediumQualityAudio(),
        "high": HighQualityAudio()
    }
    return quality_map.get(Config.AUDIO_QUALITY.lower(), HighQualityAudio())

def search_youtube(query: str) -> Optional[Dict]:
    try:
        results = YoutubeSearch(query, max_results=1).to_dict()
        if not results:
            return None
        
        return {
            'id': results[0]['id'],
            'title': results[0]['title'],
            'duration': results[0]['duration'],
            'url': f"https://youtube.com/watch?v={results[0]['id']}"
        }
    except Exception as e:
        print(f"Search Error: {e}")
        return None

def get_youtube_stream(url: str) -> Optional[str]:
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'extractaudio': True,
            'audioformat': 'mp3',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Find audio format
            for f in info.get('formats', []):
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    return f['url']
            
            return info['url']
    except Exception as e:
        print(f"Stream Error: {e}")
        return None

# ============================================
# 🎵 SPOTIFY
# ============================================
class SpotifyHandler:
    def __init__(self):
        self.spotify = None
        if Config.SPOTIFY_CLIENT_ID and Config.SPOTIFY_CLIENT_SECRET:
            try:
                auth_manager = SpotifyClientCredentials(
                    client_id=Config.SPOTIFY_CLIENT_ID,
                    client_secret=Config.SPOTIFY_CLIENT_SECRET
                )
                self.spotify = spotipy.Spotify(auth_manager=auth_manager)
                print("✅ Spotify Connected")
            except Exception as e:
                print(f"⚠️ Spotify Error: {e}")
    
    def extract_track(self, url: str) -> Optional[Dict]:
        if not self.spotify:
            return None
        
        try:
            track_id = re.search(r'track/([a-zA-Z0-9]+)', url)
            if not track_id:
                return None
            
            track = self.spotify.track(track_id.group(1))
            return {
                'title': track['name'],
                'artists': ', '.join([a['name'] for a in track['artists']]),
                'query': f"{track['name']} {track['artists'][0]['name']}"
            }
        except Exception as e:
            print(f"Spotify Track Error: {e}")
            return None

spotify_handler = SpotifyHandler()

# ============================================
# 🔊 VOICE CHAT
# ============================================
async def join_vc(chat_id: int, audio_url: str) -> bool:
    if not pytgcalls:
        return False
    
    try:
        if chat_id in pytgcalls.active_calls:
            await pytgcalls.change_stream(
                chat_id,
                AudioPiped(audio_url, AudioParameters.from_quality(get_audio_quality()))
            )
        else:
            if StreamType:
                await pytgcalls.join_group_call(
                    chat_id,
                    AudioPiped(audio_url, AudioParameters.from_quality(get_audio_quality())),
                    stream_type=StreamType().pulse_stream
                )
            else:
                await pytgcalls.join_group_call(
                    chat_id,
                    AudioPiped(audio_url, AudioParameters.from_quality(get_audio_quality()))
                )
        
        active_chats[chat_id] = True
        return True
    except Exception as e:
        print(f"VC Join Error: {e}")
        return False

async def leave_vc(chat_id: int) -> bool:
    if not pytgcalls:
        return False
    
    try:
        if chat_id in pytgcalls.active_calls:
            await pytgcalls.leave_group_call(chat_id)
        
        if chat_id in active_chats:
            del active_chats[chat_id]
        if chat_id in queues:
            del queues[chat_id]
        
        return True
    except Exception as e:
        print(f"VC Leave Error: {e}")
        return False

# ============================================
# 🎮 BOT COMMANDS
# ============================================
@bot_client.on_message(filters.command("start"))
async def start_cmd(_, message: Message):
    welcome = f"""
🍌 **Welcome {message.from_user.first_name}!**

**Commands:**
• `/play song` - Play music
• `/skip` - Skip
• `/pause` - Pause  
• `/resume` - Resume
• `/stop` - Stop
• `/queue` - Show queue
• `/ping` - Check status

**Examples:**
`/play shape of you`
`/play https://open.spotify.com/track/xxx`
`/play https://youtube.com/watch?v=xxx`
    """
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to Group", 
         url=f"https://t.me/{(await bot_client.get_me()).username}?startgroup=true")]
    ])
    
    await message.reply_text(welcome, reply_markup=kb)

@bot_client.on_message(filters.command("play") & filters.group)
async def play_cmd(_, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ Provide song name!\nEx: `/play shape of you`")
        return
    
    chat_id = message.chat.id
    query = " ".join(message.command[1:])
    
    msg = await message.reply_text(f"🔍 Searching: `{query[:50]}`")
    
    # Initialize queue
    if chat_id not in queues:
        queues[chat_id] = MusicQueue(chat_id)
    
    song_data = None
    
    # Check Spotify
    if "open.spotify.com" in query:
        track = spotify_handler.extract_track(query)
        if track:
            song_data = track
            await msg.edit_text(f"🎵 Spotify: {track['title']}")
    
    # Check YouTube URL
    elif "youtube.com" in query or "youtu.be" in query:
        yt_info = search_youtube(query)
        if yt_info:
            song_data = {
                'title': yt_info['title'],
                'artists': 'YouTube',
                'query': yt_info['title']
            }
            await msg.edit_text(f"📹 YouTube: {yt_info['title']}")
    
    # Regular search
    else:
        yt_info = search_youtube(query)
        if yt_info:
            song_data = {
                'title': yt_info['title'],
                'artists': 'YouTube', 
                'query': query
            }
            await msg.edit_text(f"✅ Found: {yt_info['title']}")
    
    if not song_data:
        await msg.edit_text("❌ Song not found!")
        return
    
    # Add to queue
    pos = queues[chat_id].add(song_data)
    
    # If already playing
    if chat_id in active_chats:
        await msg.edit_text(f"✅ Added #{pos}: {song_data['title']}")
        return
    
    # Play song
    await msg.edit_text("🎧 Joining VC...")
    await play_next(chat_id, message)

async def play_next(chat_id: int, message: Message = None):
    if chat_id not in queues or not queues[chat_id].queue:
        if Config.AUTO_LEAVE:
            await leave_vc(chat_id)
        return
    
    song = queues[chat_id].get()
    if not song:
        return
    
    yt_info = search_youtube(song['query'])
    if not yt_info:
        await play_next(chat_id, message)
        return
    
    audio_url = get_youtube_stream(yt_info['url'])
    if not audio_url:
        await play_next(chat_id, message)
        return
    
    success = await join_vc(chat_id, audio_url)
    
    if success and message:
        await message.reply_text(f"🎵 **Now Playing:** {yt_info['title']}")

@bot_client.on_message(filters.command("skip") & filters.group)
async def skip_cmd(_, message: Message):
    chat_id = message.chat.id
    
    if chat_id not in active_chats:
        await message.reply_text("❌ Not playing!")
        return
    
    await play_next(chat_id, message)
    await message.reply_text("⏭️ Skipped!")

@bot_client.on_message(filters.command("pause") & filters.group)
async def pause_cmd(_, message: Message):
    chat_id = message.chat.id
    
    if chat_id not in active_chats or not pytgcalls:
        await message.reply_text("❌ Not playing!")
        return
    
    await pytgcalls.pause_stream(chat_id)
    await message.reply_text("⏸️ Paused!")

@bot_client.on_message(filters.command("resume") & filters.group)
async def resume_cmd(_, message: Message):
    chat_id = message.chat.id
    
    if chat_id not in active_chats or not pytgcalls:
        await message.reply_text("❌ Not playing!")
        return
    
    await pytgcalls.resume_stream(chat_id)
    await message.reply_text("▶️ Resumed!")

@bot_client.on_message(filters.command("stop") & filters.group)
async def stop_cmd(_, message: Message):
    chat_id = message.chat.id
    
    if chat_id not in active_chats:
        await message.reply_text("❌ Not playing!")
        return
    
    await leave_vc(chat_id)
    await message.reply_text("⏹️ Stopped!")

@bot_client.on_message(filters.command("queue") & filters.group)
async def queue_cmd(_, message: Message):
    chat_id = message.chat.id
    
    if chat_id not in queues or not queues[chat_id].queue:
        await message.reply_text("📭 Queue empty!")
        return
    
    queue_text = "📋 **Queue:**\n\n"
    for i, song in enumerate(queues[chat_id].queue[:10], 1):
        queue_text += f"{i}. {song['title'][:40]}\n"
    
    if len(queues[chat_id].queue) > 10:
        queue_text += f"\n...{len(queues[chat_id].queue)-10} more"
    
    await message.reply_text(queue_text)

@bot_client.on_message(filters.command("ping"))
async def ping_cmd(_, message: Message):
    status = "✅ Online" if pytgcalls else "⚠️ No VC"
    await message.reply_text(f"🏓 Pong!\nStatus: {status}")

# ============================================
# 🚀 START BOT
# ============================================
async def main():
    try:
        Config.validate()
        
        print("🚀 Starting Banana Bot...")
        
        await bot_client.start()
        await assistant_client.start()
        
        if pytgcalls:
            await pytgcalls.start()
        
        bot = await bot_client.get_me()
        assistant = await assistant_client.get_me()
        
        print(f"🤖 Bot: @{bot.username}")
        print(f"👤 Assistant: @{assistant.username}")
        print(f"🎵 Spotify: {'✅' if spotify_handler.spotify else '❌'}")
        print(f"🎧 PyTgCalls: {'✅' if pytgcalls else '❌'}")
        
        print("\n" + "="*50)
        print("🍌 BOT READY!")
        print("="*50)
        
        await idle()
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        print("🛑 Stopping...")
        await bot_client.stop()
        await assistant_client.stop()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n👋 Stopped")
    except Exception as e:
        print(f"\n❌ Crash: {e}")