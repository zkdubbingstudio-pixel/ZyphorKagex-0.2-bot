import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8934334004:AAESWVI3LqraM8eztb9tJldPOkzXGn0tI2c")
WEB_APP_DOMAIN = os.getenv("WEB_APP_DOMAIN", "https://zyphorkagex.onrender.com")

# Channel Usernames / IDs
CHANNEL_1 = "@zk_dubbing_studio"
CHANNEL_2_LINK = "https://t.me/+H3TykxfXuwdlODNl"  # Private link button ke liye
CHANNEL_2_ID = "-100123456789"  # Backup channel ID

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
    return True # Fail-safe

def handle_episode_request(chat_id, user_id, episode_id):
    """Episode ID ke liye watch link aur button generate karta hai"""
    try:
        api_url = f"{WEB_APP_DOMAIN}/api/get-watch-token?episodeId={episode_id}&userId={user_id}"
        res = requests.get(api_url, timeout=10).json()

        if res.get("success"):
            token = res.get("token")
            watch_url = f"{WEB_APP_DOMAIN}/watch.html?id={episode_id}&token={token}"

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
            send_telegram_message(chat_id, f"❌ Episode nahi mila ya error hai: {res.get('message', 'Unknown')}")
    except Exception as e:
        send_telegram_message(chat_id, f"❌ Server connection error: {str(e)}")

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
        text = msg.get("text", "").strip()
        
        parts = text.split()
        
        # Determine karna ki user kya bhej raha hai (Episode ID extract karne ke liye)
        target_episode_id = None
        if len(parts) > 1 and parts[1].startswith("ep_"):
            target_episode_id = parts[1]
        elif text.startswith("ep_"):
            target_episode_id = text
            
        # Check Force Join (Pehle Main Channel Check Karte Hain)
        is_sub_1 = is_user_member(user_id, CHANNEL_1)
        
        # Agar user channel mein nahi hai:
        if not is_sub_1:
            retry_param = f"?start={target_episode_id}" if target_episode_id else ""
            join_keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "📢 Join ZK Dubbing Studio", "url": "https://t.me/zk_dubbing_studio"}
                    ],
                    [
                        {"text": "🛡️ Join Backup Channel", "url": CHANNEL_2_LINK}
                    ],
                    [
                        {"text": "🔄 Joined / Try Again", "url": f"https://t.me/Kitsu_zk_bot{retry_param}"}
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

        # Agar User Subscribed hai:
        if text == "/start" or len(parts) == 1 and parts[0] == "/start":
            welcome_msg = (
                "👋 **Welcome to Kitsu (キツ) - ZK Dubbing Studio!**\n\n"
                "🎉 Aapka swagat hai Hindi Dubbed Anime World mein!\n\n"
                "📌 **How to watch?**\n"
                "Channel par di gayi episode links par click karke aap direct anime high-quality player par stream kar sakte hain.\n\n"
                "Enjoy Watching! 🍿"
            )
            send_telegram_message(chat_id, welcome_msg)
            
        elif target_episode_id:
            # Ab chahe deep link ho ya direct text mein ep_xxxx bheja ho, yeh function button bhej dega
            handle_episode_request(chat_id, user_id, target_episode_id)

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.PORT, 5000))
