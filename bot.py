import os
import requests
from flask import Flask

# --- FLASK SERVER SETUP (Render keep-alive ke liye) ---
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Kitsu Bot is Alive & Running smoothly via HTTP API!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Starting Flask server on port {port}...")
    web_app.run(host="0.0.0.0", port=port)

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8934334004:AAESWVI3LqraM8eztb9tJldPOkzXGn0tI2c")
WEB_APP_DOMAIN = os.getenv("WEB_APP_DOMAIN", "https://zyphorkagex.onrender.com")
# =======================================================

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

# Webhook route jo Telegram se messages receive karega bina kisi event loop error ke!
@web_app.route(f'/{BOT_TOKEN}', methods=['POST'])
def telegram_webhook():
    from flask import request
    update = request.get_json()
    
    if "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        user_id = message["from"]["id"]
        text = message.get("text", "")
        
        parts = text.split()
        
        # 1. Normal /start command
        if len(parts) == 1 and parts[0] == "/start":
            send_telegram_message(
                chat_id,
                "👋 **Welcome to Kitsu (キツ) - ZK Dubbing Bot!**\n\n"
                "Channel par di gayi episode links par click karke aap direct anime stream kar sakte hain."
            )
        
        # 2. Deep-link watch parameter
        elif len(parts) > 1 and parts[1].startswith("ep_"):
            episode_id = parts[1].replace("ep_", "")
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
                        "Neeche diye gaye button par click karke anime dekhein.\n\n"
                        "🔒 **Security Rules:**\n"
                        "• Yeh link sirf **2 baar** khol sakte hain.\n"
                        "• Yeh message secure hai!",
                        reply_markup=keyboard
                    )
                else:
                    send_telegram_message(chat_id, "❌ Episode token generate karne mein error aaya ya session expire ho gaya.")
            except Exception:
                send_telegram_message(chat_id, "❌ Web server se connect karne mein issue aaya.")

    return "OK", 200

if __name__ == "__main__":
    # Telegram ko Webhook URL set karna automatically
    webhook_url = f"{WEB_APP_DOMAIN}/{BOT_TOKEN}"
    set_webhook_api = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
    try:
        requests.get(set_webhook_api, timeout=10)
        print("🔗 Telegram Webhook Set Successfully!")
    except Exception as e:
        print(f"⚠️ Could not set webhook automatically: {e}")

    # Flask server run karega jo bot aur web dono sambhal lega
    run_flask()
