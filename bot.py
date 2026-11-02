import os
import requests
import asyncio
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8934334004:AAESWVI3LqraM8eztb9tJldPOkzXGn0tI2c")
WEB_APP_DOMAIN = os.getenv("WEB_APP_DOMAIN", "https://zyphorkagex.onrender.com")
BOT_USERNAME = "Kitsu_zk_bot"

CHANNEL_1 = "@zk_dubbing_studio"
CHANNEL_2_LINK = "https://t.me/+H3TykxfXuwdlODNl"

# 🟢 Sirf aap dono ki IDs admin hain jo /adduser aur /users chala sakenge
ADMIN_IDS = [6144546817, 8528056660]

SUPABASE_URL = os.getenv("SUPABASE_URL", "YOUR_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "YOUR_SUPABASE_ANON_KEY")

def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
        "protect_content": True  # Forwarding rokne ke liye
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Send message error: {e}")

def delete_telegram_message_delayed(chat_id, message_id, delay_seconds=600):
    """10 minute baad message auto-delete karne ke liye background task"""
    def task():
        import time
        time.sleep(delay_seconds)
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
            requests.post(url, json={"chat_id": chat_id, "message_id": message_id}, timeout=5)
        except Exception as e:
            print(f"Auto-delete error: {e}")
    import threading
    threading.Thread(target=task, daemon=True).start()

def check_user_access_db(user_id):
    """Check karta hai ki user ka subscription active hai ya nahi"""
    if user_id in ADMIN_IDS:
        return True
    try:
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        url = f"{SUPABASE_URL}/rest/v1/user_subscriptions?user_id=eq.{user_id}"
        res = requests.get(url, headers=headers, timeout=5).json()
        if isinstance(res, list):
            now = datetime.utcnow()
            for sub in res:
                expiry_str = sub.get("expires_at", "").replace("Z", "")
                if expiry_str:
                    expiry = datetime.fromisoformat(expiry_str)
                    if expiry > now:
                        return True
    except Exception as e:
        print(f"DB access check error: {e}")
    return False

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
    return "Kitsu Bot & Webhook is Active!", 200

@app.route('/', methods=['POST'])
@app.route('/<path:subpath>', methods=['POST'])
def webhook(subpath=''):
    try:
        update = request.get_json(silent=True)
        if not update:
            return jsonify({"status": "ok"}), 200
        
        # Callback query handle karne ke liye (Jaise user remove button dabaye)
        if "callback_query" in update:
            cq = update["callback_query"]
            c_id = cq["message"]["chat"]["id"]
            u_id = cq["from"]["id"]
            data = cq["data"]
            
            if data.startswith("del_") and u_id in ADMIN_IDS:
                sub_id = data.split("_")[1]
                try:
                    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
                    del_url = f"{SUPABASE_URL}/rest/v1/user_subscriptions?id=eq.{sub_id}"
                    requests.delete(del_url, headers=headers, timeout=5)
                    
                    # Answer callback query
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cq["id"], "text": "User access removed successfully!", "show_alert": True})
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": c_id, "text": "✅ User ka access successfully hata diya gaya hai.", "protect_content": True})
                except Exception as e:
                    print(f"Delete callback error: {e}")
            return jsonify({"status": "ok"}), 200

        if "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]
            text = msg.get("text", "").strip()
            caption = msg.get("caption", "").strip()
            
            full_text = text if text else caption
            parts = full_text.split()

            # 1. Admin Command: /adduser <user_id> <anime_name> <days>
            if full_text.startswith("/adduser"):
                if user_id not in ADMIN_IDS:
                    send_telegram_message(chat_id, "❌ Aap yeh command use nahi kar sakte!")
                    return jsonify({"status": "ok"}), 200
                
                if len(parts) < 4:
                    send_telegram_message(chat_id, "⚠️ Sahi format use karein:\n`/adduser <user_id> <anime_name> <days>`\nExample: `/adduser 123456789 Overlord 30`")
                    return jsonify({"status": "ok"}), 200
                
                target_user_id, anime_name, days_str = parts[1], parts[2], parts[3]
                try:
                    days = int(days_str)
                except ValueError:
                    send_telegram_message(chat_id, "❌ Days ek valid number hona chahiye!")
                    return jsonify({"status": "ok"}), 200
                
                expiry_date = datetime.utcnow() + timedelta(days=days)
                payload = {
                    "user_id": target_user_id,
                    "anime_name": anime_name,
                    "expires_at": expiry_date.isoformat()
                }
                
                try:
                    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
                    post_url = f"{SUPABASE_URL}/rest/v1/user_subscriptions"
                    resp = requests.post(post_url, json=payload, headers=headers, timeout=5)
                    if resp.status_code in [200, 201, 204]:
                        send_telegram_message(chat_id, f"✅ User `{target_user_id}` ko **{anime_name}** ka access **{days}** dino ke liye successfully mil gaya hai!")
                    else:
                        send_telegram_message(chat_id, f"❌ Database error: {resp.text}")
                except Exception as e:
                    send_telegram_message(chat_id, f"❌ Server error: {str(e)}")
                return jsonify({"status": "ok"}), 200

            # 2. Admin Command: /users (List active users & remove buttons)
            if full_text.startswith("/users"):
                if user_id not in ADMIN_IDS:
                    return jsonify({"status": "ok"}), 200
                
                try:
                    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
                    get_url = f"{SUPABASE_URL}/rest/v1/user_subscriptions?select=id,user_id,anime_name,expires_at"
                    res = requests.get(get_url, headers=headers, timeout=5).json()
                    
                    if not res or not isinstance(res, list):
                        send_telegram_message(chat_id, "📁 Koi bhi active premium user nahi hai.")
                        return jsonify({"status": "ok"}), 200
                    
                    text_msg = "📋 **Active Premium Users List:**\n\n"
                    inline_keyboard = []
                    for u in res:
                        exp_date = u['expires_at'][:10] if u.get('expires_at') else "N/A"
                        text_msg += f"👤 User: `{u['user_id']}`\n🎬 Anime: {u['anime_name']}\n⏳ Expires: {exp_date}\n-------------------\n"
                        inline_keyboard.append([{"text": f"❌ Remove {u['user_id']} ({u['anime_name']})", "callback_data": f"del_{u['id']}"}])
                    
                    send_telegram_message(chat_id, text_msg, reply_markup={"inline_keyboard": inline_keyboard})
                except Exception as e:
                    send_telegram_message(chat_id, f"❌ Error fetching users: {str(e)}")
                return jsonify({"status": "ok"}), 200

            # Admin Link Generator
            if full_text.startswith("/getlink") and user_id in ADMIN_IDS:
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
                # 🛑 ACCESS & PREMIUM CHECK
                if not check_user_access_db(user_id):
                    send_telegram_message(
                        chat_id,
                        "⚠️ Aap anime stream nhi kar sakte aapko hamre premium lena hoga.\n\n"
                        "Premium lene ke liye yha pe message/dm karo :- @zk_studio_owner"
                    )
                    return jsonify({"status": "ok"}), 200

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

                # Request token from Render backend with safe timeout
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
                            "📌 **Rules:**\n"
                            "• Yeh link sirf **2 baar** open ki ja sakti hai.\n"
                            "• Yeh message **10 minute** mein automatic delete ho jayega."
                        )
                        
                        # Send message and get message ID for auto-delete
                        url_send = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                        payload_send = {
                            "chat_id": chat_id,
                            "text": msg_text,
                            "parse_mode": "Markdown",
                            "reply_markup": keyboard,
                            "protect_content": True
                        }
                        r_sent = requests.post(url_send, json=payload_send, timeout=5).json()
                        if r_sent.get("ok"):
                            sent_msg_id = r_sent["result"]["message_id"]
                            delete_telegram_message_delayed(chat_id, sent_msg_id, 600) # 10 minutes (600 seconds)
                    else:
                        send_telegram_message(chat_id, f"❌ Error: {res.get('message', 'Episode database mein nahi mila.')}")
                except Exception as e:
                    send_telegram_message(chat_id, f"❌ Server connection error: {str(e)}")

                return jsonify({"status": "ok"}), 200

            if full_text == "/start":
                if not check_user_access_db(user_id):
                    send_telegram_message(
                        chat_id,
                        "⚠️ Aap anime stream nhi kar sakte aapko hamre premium lena hoga.\n\n"
                        "Premium lene ke liye yha pe message/dm karo :- @zk_studio_owner"
                    )
                else:
                    send_telegram_message(chat_id, "👋 **Welcome to Kitsu (キツ) - ZK Dubbing Studio!**\n\nAapko anime episodes ke liye channel par di gayi links par click karna hoga.")

    except Exception as e:
        print(f"Webhook error: {e}")
        
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(port=5000)
