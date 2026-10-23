import os
import requests
from flask import Flask, request, jsonify

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
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Send message error: {e}")

def is_user_member(user_id, channel_id):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        res = requests.get(url, params={"chat_id": channel_id, "user_id": user_id}, timeout=4).json()
        if res.get("ok"):
            status = res["result"]["status"]
            return status in ["creator", "administrator", "member"]
    except Exception as e:
        print(f"Member check error: {e}")
    return True

@app.route('/', methods=['GET'])
def home():
    return "Kitsu Vercel Bot is Active!", 200

@app.route('/', methods=['POST'])
@app.route('/<path:subpath>', methods=['POST'])
def webhook(subpath=''):
    try:
        update = request.get_json(silent=True)
        if not update:
            return jsonify({"status": "ok"}), 200
        
        if "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]
            text = msg.get("text", "").strip()
            caption = msg.get("caption", "").strip()
            
            full_text = text if text else caption
            parts = full_text.split()

            # Admin Link Generator
            if full_text.startswith("/getlink"):
                if len(parts) > 1:
                    ep_id = parts[1]
                    channel_post_link = f"https://t.me/{BOT_USERNAME}?start={ep_id}"
                    send_telegram_message(
                        chat_id,
                        f"✅ **Official Channel Share Link:**\n\n`{channel_post_link}`"
                    )
                else:
                    send_telegram_message(chat_id, "⚠️ Write: `/getlink ep_xxxx`")
                return jsonify({"status": "ok"}), 200

            target_episode_id = None
            
            # Smart Episode ID Extractor
            if "start=ep_" in full_text:
                try:
                    sub = full_text.split("start=")[1]
                    target_episode_id = sub.split()[0].split("&")[0]
                except:
                    pass
            elif len(parts) > 1 and parts[0] == "/start" and parts[1].startswith("ep_"):
                target_episode_id = parts[1]
            else:
                for part in parts:
                    if "ep_" in part:
                        idx = part.find("ep_")
                        candidate = part[idx:]
                        clean_id = "".join([c for c in candidate if c.isalnum() or c == '_'])
                        if clean_id.startswith("ep_"):
                            target_episode_id = clean_id
                            break

            if target_episode_id:
                # Force join check
                if not is_user_member(user_id, CHANNEL_1):
                    retry_param = f"?start={target_episode_id}"
                    join_keyboard = {
                        "inline_keyboard": [
                            [{"text": "📢 Join ZK Dubbing Studio", "url": "https://t.me/zk_dubbing_studio"}],
                            [{"text": "🛡️ Join Backup Channel", "url": CHANNEL_2_LINK}],
                            [{"text": "🔄 Joined / Try Again", "url": f"https://t.me/{BOT_USERNAME}{retry_param}"}]
                        ]
                    }
                    send_telegram_message(chat_id, "✨ **Please Join Channel to Unlock Anime Links!**", reply_markup=join_keyboard)
                    return jsonify({"status": "ok"}), 200

                # Request token from Render backend with 15s safe timeout
                try:
                    api_url = f"{WEB_APP_DOMAIN}/api/get-watch-token?episodeId={target_episode_id}&userId={user_id}"
                    res = requests.get(api_url, timeout=15).json()

                    if res.get("success"):
                        token = res.get("token")
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
                            "⚠️ *Note: Yeh link secure hai aur kuch samay baad expire ho jayegi.*"
                        )
                        send_telegram_message(chat_id, msg_text, reply_markup=keyboard)
                    else:
                        send_telegram_message(chat_id, f"❌ Error: {res.get('message', 'Episode database mein nahi mila.')}")
                except Exception as e:
                    send_telegram_message(chat_id, f"❌ Server connection error: {str(e)}")

                return jsonify({"status": "ok"}), 200

            if full_text == "/start":
                send_telegram_message(chat_id, "👋 **Welcome to Kitsu (キツ) - ZK Dubbing Studio!**\n\nAapko anime episodes ke liye channel par di gayi links par click karna hoga.")

    except Exception as e:
        print(f"Webhook error: {e}")
        
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(port=5000)
