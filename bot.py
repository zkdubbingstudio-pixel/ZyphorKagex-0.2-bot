import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8934334004:AAESWVI3LqraM8eztb9tJldPOkzXGn0tI2c")
WEB_APP_DOMAIN = os.getenv("WEB_APP_DOMAIN", "https://zyphorkagex.onrender.com")

def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(url, json=payload)

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
        
        if len(parts) == 1 and parts[0] == "/start":
            send_telegram_message(
                chat_id,
                "👋 **Welcome to Kitsu (キツ) - ZK Dubbing Bot!**\n\n"
                "Channel par di gayi episode links par click karke aap direct anime stream kar sakte hain."
            )
        elif len(parts) > 1 and parts[1].startswith("ep_"):
            # Yahan fix kiya hai taaki poora ep_ID jaye
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
