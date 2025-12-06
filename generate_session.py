from pyrogram import Client

print("""
🍌 **Banana Bot String Session Generator** 🎵

1. Go to: https://my.telegram.org
2. Get your API ID and Hash
3. Enter details below
""")

api_id = int(input("Enter API ID: "))
api_hash = input("Enter API Hash: ")

with Client(":memory:", api_id=api_id, api_hash=api_hash) as app:
    session_string = app.export_session_string()
    print("\n" + "="*50)
    print("✅ **Your String Session:**")
    print("="*50)
    print(session_string)
    print("="*50)
    print("\n⚠️ **Save this string safely!**")
    print("Add to .env as: SESSION_STRING=your_string_here")