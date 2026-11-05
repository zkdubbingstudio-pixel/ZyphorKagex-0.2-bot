import os
import requests
import time
import threading
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8934334004:AAESWVI3LqraM8eztb9tJldPOkzXGn0tI2c")
WEB_APP_DOMAIN = os.getenv("WEB_APP_DOMAIN", "https://zyphorkagex.onrender.com")
BOT_USERNAME = "Kitsu_zk_bot"

CHANNEL_1 = "@zk_dubbing_studio"
CHANNEL_2_LINK = "https://t.me/+H3TykxfXuwdlODNl"

ADMIN_IDS = [6144546817, 8528056660]

SUPABASE_URL = "https://knefbynsdhgjuhlklyvu.supabase.co"
SUPABASE_KEY = "sb_publishable_tZxPCR45AXkjm73Fq81YAQ_VHEsGZVJ"

def save_sent_message(chat_id, message_id):
    try:
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
        payload = {"chat_id": str(chat_id), "message_id": int(message_id)}
        requests.post(f"{SUPABASE_URL}/rest/v1/sent_messages", json=payload, headers=headers, timeout=5)
    except Exception as e:
        print(f"Save message error: {e}")

def delete_telegram_message_delayed(chat_id, message_id, delay_seconds=300):
    def task():
        time.sleep(delay_seconds)
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
            requests.post(url, json={"chat_id": chat_id, "message_id": message_id}, timeout=5)
        except Exception as e:
            print(f"Auto-delete error: {e}")
    threading.Thread(target=task, daemon=True).start()

def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
        "protect_content": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        response = requests.post(url, json=payload, timeout=5).json()
        if response.get("ok"):
            msg_id = response["result"]["message_id"]
            save_sent_message(chat_id, msg_id)
            delete_telegram_message_delayed(chat_id, msg_id, 300)
    except Exception as e:
        print(f"Send message error: {e}")

def check_user_anime_access(user_id, episode_id):
    if user_id in ADMIN_IDS:
        return True
    try:
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        ep_url = f"{SUPABASE_URL}/rest/v1/episodes?id=eq.{episode_id}&select=anime_name"
        ep_res = requests.get(ep_url, headers=headers, timeout=5).json()
        if not ep_res or not isinstance(ep_res, list):
            return False
        
        anime_name = ep_res[0].get("anime_name", "").strip().lower()
        sub_url = f"{SUPABASE_URL}/rest/v1/user_subscriptions?user_id=eq.{user_id}"
        sub_res = requests.get(sub_url, headers=headers, timeout=5).json()
        
        if isinstance(sub_res, list):
            now = datetime.utcnow()
            for sub in sub_res:
                expiry_str = sub.get("expires_at", "").replace("Z", "")
                sub_anime = sub.get("anime_name", "").strip().lower()
                if expiry_str and sub_anime:
                    expiry = datetime.fromisoformat(expiry_str)
                    if expiry > now and (sub_anime == anime_name or sub_anime == "all"):
                        return True
    except Exception as e:
        print(f"Anime access check error: {e}")
    return False

def check_user_general_access(user_id):
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
        print(f"General access check error: {e}")
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
                    
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cq["id"], "text": "User access removed successfully!", "show_alert": True})
                    send_telegram_message(c_id, "✅ User ka access successfully hata diya gaya hai.")
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

            # 🧹 /clear Command: Bot messages cleanup across chats
            if full_text.startswith("/clear") and user_id in ADMIN_IDS:
                try:
                    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
                    get_url = f"{SUPABASE_URL}/rest/v1/sent_messages?select=chat_id,message_id"
                    res = requests.get(get_url, headers=headers, timeout=5).json()
                    
                    deleted_count = 0
                    if isinstance(res, list):
                        for item in res:
                            c_id = item.get("chat_id")
                            m_id = item.get("message_id")
                            try:
                                del_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
                                requests.post(del_url, json={"chat_id": c_id, "message_id": m_id}, timeout=3)
                                deleted_count += 1
                            except:
                                pass
                        
                        requests.delete(f"{SUPABASE_URL}/rest/v1/sent_messages?message_id=gt.0", headers=headers, timeout=5)
                    
                    send_telegram_message(chat_id, f"🧹 Successfully cleared and deleted {deleted_count} bot messages/links across chats!")
                except Exception as e:
                    send_telegram_message(chat_id, f"❌ Clear error: {str(e)}")
                return jsonify({"status": "ok"}), 200

            # 🔗 /setepad Command: Specific episode ke liye custom ad/protection link set karne ke liye
            if full_text.startswith("/setepad") and user_id in ADMIN_IDS:
                try:
                    parts = full_text.split(maxsplit=2)
                    if len(parts) < 3:
                        send_telegram_message(
                            chat_id,
                            "⚠️ Sahi format use karein:\n"
                            "`/setepad <episode_id> <ad_link>`\n\n"
                            "Example:\n`/setepad ep_1793711255297 https://links.otaku-provider-bots.workers.dev/...`"
                        )
                        return jsonify({"status": "ok"}), 200
                    
                    _, target_ep_id, new_ad_link = parts
                    target_ep_id = target_ep_id.strip()
                    new_ad_link = new_ad_link.strip()

                    headers = {
                        "apikey": SUPABASE_KEY, 
                        "Authorization": f"Bearer {SUPABASE_KEY}", 
                        "Content-Type": "application/json", 
                        "Prefer": "return=minimal"
                    }
                    
                    update_url = f"{SUPABASE_URL}/rest/v1/episodes?id=eq.{target_ep_id}"
                    resp = requests.patch(update_url, json={"ad_link": new_ad_link}, headers=headers, timeout=5)
                    
                    if resp.status_code in [200, 204]:
                        send_telegram_message(chat_id, f"✅ Episode `{target_ep_id}` ke liye ad/protection link successfully set ho gayi hai!\n\n`{new_ad_link}`")
                    else:
                        send_telegram_message(chat_id, f"❌ Database update error: {resp.text}")
                except Exception as e:
                    send_telegram_message(chat_id, f"❌ Error: {str(e)}")
                return jsonify({"status": "ok"}), 200

            if full_text.startswith("/adduser"):
                if user_id not in ADMIN_IDS:
                    send_telegram_message(chat_id, "❌ Aap yeh command use nahi kar sakte!")
                    return jsonify({"status": "ok"}), 200
                
                try:
                    parts = full_text.split(maxsplit=2)
                    if len(parts) < 3:
                        raise ValueError("Invalid format")
                    
                    _, target_user_id, remaining = parts
                    rem_parts = remaining.rsplit(maxsplit=1)
                    if len(rem_parts) < 2:
                        raise ValueError("Invalid format")
                    
                    anime_name, days_str = rem_parts
                    days = int(days_str)
                except Exception as e:
                    send_telegram_message(
                        chat_id,
                        "⚠️ Sahi format use karein:\n"
                        "`/adduser <user_id> <anime_name> <days>`\n\n"
                        "Example:\n`/adduser 8308984306 Hello, I Am a Witch 20`"
                    )
                    return jsonify({"status": "ok"}), 200
                
                expiry_date = datetime.utcnow() + timedelta(days=days)
                payload = {
                    "user_id": target_user_id.strip(),
                    "anime_name": anime_name.strip(),
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
                is_premium = check_user_anime_access(user_id, target_episode_id)

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

                if is_premium:
                    # 💎 PREMIUM USER: Direct Ad-Free Player Link
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
                                            "text": "▶️ Watch Anime Now (Ad-Free)",
                                            "web_app": {"url": watch_url}
                                        }
                                    ]
                                ]
                            }

                            msg_text = (
                                "🎬 **Kitsu Player Ready (Premium - No Ads)!**\n\n"
                                "• Aapke paas active premium hai, isliye yeh link bilkul ad-free hai."
                            )
                            send_telegram_message(chat_id, msg_text, reply_markup=keyboard)
                        else:
                            send_telegram_message(chat_id, f"❌ Error: {res.get('message', 'Episode database mein nahi mila.')}")
                    except Exception as e:
                        send_telegram_message(chat_id, f"❌ Server connection error: {str(e)}")
                else:
                    # 📺 FREE USER: Fetch specific episode ad/protection link from database
                    episode_ad_link = "https://shrinkme.click/default" # Fallback link
                    try:
                        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
                        ep_query_res = requests.get(f"{SUPABASE_URL}/rest/v1/episodes?id=eq.{target_episode_id}&select=ad_link", headers=headers, timeout=5).json()
                        if isinstance(ep_query_res, list) and len(ep_query_res) > 0:
                            db_link = ep_query_res[0].get("ad_link")
                            if db_link:
                                episode_ad_link = db_link
                    except Exception as e:
                        print(f"Fetch episode ad link error: {e}")

                    keyboard = {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "🔗 Watch via Ads (Protected Link)",
                                    "url": episode_ad_link
                                }
                            ],
                            [
                                {
                                    "text": "💎 Buy Premium (Remove Ads)",
                                    "url": "https://t.me/zk_studio_owner"
                                }
                            ]
                        ]
                    }

                    msg_text = (
                        "🎬 **Free Episode Link (With Ads):**\n\n"
                        "• Aapne premium nahi liya hai, isliye is episode ki ad-protected link niche di gayi hai.\n"
                        "• Ads cross karke episode dekhein!"
                    )
                    send_telegram_message(chat_id, msg_text, reply_markup=keyboard)

                return jsonify({"status": "ok"}), 200

            if full_text == "/start":
                if not check_user_general_access(user_id):
                    send_telegram_message(
                        chat_id,
                        "⚠️ Aap anime stream nhi kar sakte aapko hamre premium lena hoga.\n\n"
                        "Premium lene ke liye yha pe message/dm karo :- @zk\\_studio\\_owner"
                    )
                else:
                    send_telegram_message(chat_id, "👋 **Welcome to Kitsu (キツ) - ZK Dubbing Studio!**\n\nAapko anime episodes ke liye channel par di gayi links par click karna hoga.")

    except Exception as e:
        print(f"Webhook error: {e}")
        
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(port=5000)
