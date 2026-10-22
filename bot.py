import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8934334004:AAESWVI3LqraM8eztb9tJldPOkzXGn0tI2c")
WEB_APP_DOMAIN = os.getenv("WEB_APP_DOMAIN", "https://zyphorkagex.onrender.com")

# Channel Usernames / IDs
CHANNEL_1 = "@zk_dubbing_studio"
CHANNEL_2_LINK = "https://t.me/+H3TykxfXuwdlODNl"  # Private link button ke liye

# Private channel ka Telegram ID (Agar -100123456789 jaisa ID pata ho toh yahan daalein, warna username)
# Note: Private channel ke verification ke liye bot ka Admin hona zaroori hai.
CHANNEL_2_ID = "-100123456789"  # <-- Apne backup channel ka Chat ID yahan dalein agar pata ho, warna username/ID use karein

def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(url, json=payload)

def is_user_member(user_id, channel_id):
    """Check karta hai ki user channel join kiya hai ya nahi"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        res = requests.get(url, params={"chat_id": channel_id, "user_id": user_id}, timeout=5).json()
        if res.get("ok"):
            status = res["result"]["status"]
            return status in ["creator", "administrator", "member"]
    except Exception as e:
        print(f"Member check error: {e}")
    return True # Fail-safe: agar check na ho paaye toh block na kare

@app.route('/', methods=['GET'])
def home():
    return "Kitsu Bot Serverless is Active!", 200

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    update = request.get_json()
    
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "")
        
        parts = text.split()
        
        # Check Force Join (Pehle Main Channel Check Karte Hain)
        is_sub_1 = is_user_member(user_id, CHANNEL_1)
        
        # Agar user channel mein nahi hai:
        if not is_sub_1:
            join_keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "📢 Join ZK Dubbing Studio", "url": "https://t.me/zk_dubbing_studio"}
                    ],
                    [
                        {"text": "🛡️ Join Backup Channel", "url": CHANNEL_2_LINK}
                    ],
                    [
                        {"text": "🔄 Joined / Try Again", "url": f"https://t.me/Kitsu_zk_bot?start={parts[1]}" if len(parts) > 1 else "https://t.me/Kitsu_zk_bot"}
                    ]
                ]
            }
            
            welcome_force_msg = (
                "✨ **Welcome to Kitsu (キツ) - ZK Dubbing Hub!** ✨\n\n"
                "🎌 *Hindi Dubbed Anime Stream Karne Ke Liye Requirements:*\n\n"
                "Aapko hamaare official channels join karne honge tabhi anime links unlocked hongi!\n\n"
                "1️⃣ **ZK Dubbing Studio** (Main Updates)\n"
                "2️⃣ **Backup Channel** (Important Links & Backup)\n\n"
                "👇 *Niche diye gaye buttons se dono channels join karein aur 'Joined / Try Again' par click karein!*"
            )
            
            send_telegram_message(chat_id, welcome_force_msg, reply_markup=join_keyboard)
            return "OK", 200

        # Normal Flow (Jab User Subscribed Ho)
        if len(parts) == 1 and parts[0] == "/start":
            welcome_msg = (
                "👋 **Welcome to Kitsu (キツ) - ZK Dubbing Studio!**\n\n"
                "🎉 Aapka swagat hai Hindi Dubbed Anime World mein!\n\n"
                "📌 **How to watch?**\n"
                "Channel par di gayi episode links par click karke aap direct anime high-quality player par stream kar sakte hain.\n\n"
                "Enjoy Watching! 🍿"
            )
            send_telegram_message(chat_id, welcome_msg)
            
        elif len(parts) > 1 and parts[1].startswith("ep_"):
            episode_id = parts[1]
            try:
                api_url = f"{WEB_APP_DOMAIN}/api/get-watch-token?episodeId={episode_id}&userId={user_id}"
                res = requests.get(api_url, timeout=10).json()

                if res.get("success"):
                    token = res.get("token")
                    watch_url = f"{WEB_APP_DOMAIN}/watch?id={episode_id}&token={token}"

                    keyboard = {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "▶️ Watch Anime Now (Kitsu Player)",
                                    "web_app": {"url": watch_url}
                                }
                            ]
                        ]
                    }

                    send_telegram_message(
                        chat_id,
                        "🎬 **Kitsu Player Ready!**\n\n"
                        "Neeche diye gaye button par click karke anime dekhein.",
                        reply_markup=keyboard
                    )
                else:
                    send_telegram_message(chat_id, f"❌ Token error: {res.get('message', 'Unknown')}")
            except Exception as e:
                send_telegram_message(chat_id, f"❌ Server connection error: {str(e)}")

    return "OK", 200
