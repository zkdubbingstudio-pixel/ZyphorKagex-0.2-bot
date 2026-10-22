import os
import requests
import threading
import time
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8934334004:AAESWVI3LqraM8eztb9tJldPOkzXGn0tI2c")
WEB_APP_DOMAIN = os.getenv("WEB_APP_DOMAIN", "https://zyphorkagex.onrender.com")
BOT_USERNAME = "Kitsu_zk_bot"

CHANNEL_1 = "@zk_dubbing_studio"
CHANNEL_2_LINK = "https://t.me/+H3TykxfXuwdlODNl"

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
    res = requests.post(url, json=payload).json()
    if res.get("ok"):
        return res["result"]["message_id"]
    return None

def delete_telegram_message(chat_id, message_id, delay=300):
    """5 Minutes (300 Seconds) Baad Message Delete Karne Ke Liye Thread"""
    def delayed_delete():
        time.sleep(delay)
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
        requests.post(url, json={"chat_id": chat_id, "message_id": message_id})

    threading.Thread(target=delayed_delete).start()

def is_user_member(user_id, channel_id):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        res = requests.get(url, params={"chat_id": channel_id, "user_id": user_id}, timeout=5).json()
        if res.get("ok"):
            status = res["result"]["status"]
            return status in ["creator", "administrator", "member"]
    except Exception as e:
        print(f"Member check error: {e}")
    return True

def handle_episode_request(chat_id, user_id, episode_id):
    try:
        api_url = f"{WEB_APP_DOMAIN}/api/get-watch-token?episodeId={episode_id}&userId={user_id}"
        res = requests.get(api_url, timeout=10).json()

        if res.get("success"):
            token = res.get("token")
            # Dynamic player link with temporary token
            watch_url = f"{WEB_APP_DOMAIN}/watch.html?token={token}"

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

            msg_text = (
                "🎬 **Kitsu Player Ready!**\n\n"
                "⚠️ *Note: Yeh link sirf 2 baar use ki ja sakti hai aur 5 minute mein automatic delete ho jayegi!*"
            )
            
            msg_id = send_telegram_message(chat_id, msg_text, reply_markup=keyboard)
            
            # Auto-delete timer trigger (300 seconds = 5 mins)
            if msg_id:
                delete_telegram_message(chat_id, msg_id, delay=300)

        else:
            send_telegram_message(chat_id, f"❌ Episode nahi mila ya error: {res.get('message', 'Unknown')}")
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

        # Admin Link Generator Command
        if text.startswith("/getlink"):
            if len(parts) > 1:
                ep_id = parts[1]
                channel_post_link = f"https://t.me/{BOT_USERNAME}?start={ep_id}"
                send_telegram_message(
                    chat_id,
                    f"✅ **Official Channel Share Link:**\n\n`{channel_post_link}`\n\nIs link ko copy karke apne main channel mein share karein!"
                )
            else:
                send_telegram_message(chat_id, "⚠️ Format error! Write: `/getlink ep_xxxx`")
            return "OK", 200

        target_episode_id = None
        if len(parts) > 1 and parts[1].startswith("ep_"):
            target_episode_id = parts[1]
        elif text.startswith("ep_"):
            target_episode_id = text
            
        # Force Join Check
        if not is_user_member(user_id, CHANNEL_1):
            retry_param = f"?start={target_episode_id}" if target_episode_id else ""
            join_keyboard = {
                "inline_keyboard": [
                    [{"text": "📢 Join ZK Dubbing Studio", "url": "https://t.me/zk_dubbing_studio"}],
                    [{"text": "🛡️ Join Backup Channel", "url": CHANNEL_2_LINK}],
                    [{"text": "🔄 Joined / Try Again", "url": f"https://t.me/{BOT_USERNAME}{retry_param}"}]
                ]
            }
            send_telegram_message(chat_id, "✨ **Please Join Channel to Unlock Anime Links!**", reply_markup=join_keyboard)
            return "OK", 200

        if text == "/start" or (len(parts) == 1 and parts[0] == "/start"):
            send_telegram_message(chat_id, "👋 **Welcome to Kitsu (キツ) - ZK Dubbing Studio!**")
        elif target_episode_id:
            handle_episode_request(chat_id, user_id, target_episode_id)

    return "OK", 200
