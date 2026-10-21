import os
import asyncio
import requests
from threading import Thread
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# --- FLASK SERVER SETUP (Fly.io port 8080 bind ke liye) ---
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Kitsu Bot is Alive & Running on Fly.io!", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    print(f"🌐 Starting Flask server on port {port}...")
    web_app.run(host="0.0.0.0", port=port)

# ==================== CONFIGURATION ====================
API_ID = int(os.getenv("API_ID", "38215355"))
API_HASH = os.getenv("API_HASH", "3f095c170be8c744b8f3d7f9c75ae544")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8934334004:AAESWVI3LqraM8eztb9tJldPOkzXGn0tI2c")

WEB_APP_DOMAIN = os.getenv("WEB_APP_DOMAIN", "https://zyphorkagex.onrender.com")
# =======================================================

bot = Client(
    "Kitsu_Dubbing_Bot", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN,
    workdir="/tmp"
)

@bot.on_message(filters.command("start"))
async def start_handler(client, message):
    text = message.text.split()
    user_id = message.from_user.id

    if len(text) == 1:
        await message.reply_text(
            "👋 **Welcome to Kitsu (キツ) - ZK Dubbing Bot!**\n\n"
            "Channel par di gayi episode links par click karke aap direct anime stream kar sakte hain."
        )
        return

    param = text[1]

    if param.startswith("ep_"):
        episode_id = param.replace("ep_", "")

        try:
            api_url = f"{WEB_APP_DOMAIN}/api/get-watch-token?episodeId={episode_id}&userId={user_id}"
            res = requests.get(api_url, timeout=10).json()

            if res.get("success"):
                token = res.get("token")
                watch_url = f"{WEB_APP_DOMAIN}/watch?id={episode_id}&token={token}"

                sent_msg = await message.reply_text(
                    "🎬 **Kitsu Player Ready!**\n\n"
                    "Neeche diye gaye button par click karke anime dekhein.\n\n"
                    "🔒 **Security Rules:**\n"
                    "• Yeh link sirf **2 baar** khol sakte hain.\n"
                    "• Yeh message **5 minute** mein automatically delete ho jayega!",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(
                                "▶️ Watch Anime Now (Kitsu Player)",
                                web_app=WebAppInfo(url=watch_url)
                            )
                        ]
                    ])
                )

                await asyncio.sleep(300)
                try:
                    await sent_msg.delete()
                except Exception:
                    pass
            else:
                await message.reply_text("❌ Episode token generate karne mein error aaya ya session expire ho gaya.")

        except Exception as e:
            await message.reply_text("❌ Web server se connect karne mein issue aaya.")

if __name__ == "__main__":
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()

    print("🦊 Kitsu Bot Status: Starting on Fly.io...")
    bot.run()
