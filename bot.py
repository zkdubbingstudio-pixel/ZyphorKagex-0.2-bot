import os
import requests
import threading
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8934334004:AAESWVI3LqraM8eztb9tJldPOkzXGn0tI2c")
WEB_APP_DOMAIN = os.getenv("WEB_APP_DOMAIN", "https://kitsu-watch-zk.vercel.app")
BOT_USERNAME = "Kitsu_zk_bot"

CHANNEL_1 = "@zk_dubbing_studio"
CHANNEL_2_LINK = "https://t.me/+H3TykxfXuwdlODNl"

ADMIN_IDS = [6144546817, 8528056660]

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://knefbynsdhgjuhlklyvu.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_tZxPCR45AXkjm73Fq81YAQ_VHEsGZVJ")

# In-memory lookup for callback_data (< 64 bytes safe)
USER_LIST_CACHE = {}
USER_SUBS_CACHE = {}


def sb_headers(json_body=False):
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def save_sent_message(chat_id, message_id):
    try:
        delete_at = (datetime.utcnow() + timedelta(seconds=300)).isoformat()
        payload = {
            "chat_id": str(chat_id),
            "message_id": int(message_id),
            "delete_at": delete_at
        }
        requests.post(f"{SUPABASE_URL}/rest/v1/sent_messages", json=payload, headers=sb_headers(True), timeout=5)
    except Exception as e:
        print(f"Save message error: {e}")


def delete_telegram_message_now(chat_id, message_id):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
        requests.post(url, json={"chat_id": chat_id, "message_id": message_id}, timeout=5)
    except Exception as e:
        print(f"Delete message error: {e}")


def cleanup_expired_messages():
    try:
        now_iso = datetime.utcnow().isoformat()
        get_url = f"{SUPABASE_URL}/rest/v1/sent_messages?delete_at=lt.{now_iso}&select=id,chat_id,message_id"
        res = requests.get(get_url, headers=sb_headers(), timeout=4).json()
        if isinstance(res, list):
            for item in res:
                delete_telegram_message_now(item.get("chat_id"), item.get("message_id"))
                if item.get("id") is not None:
                    requests.delete(
                        f"{SUPABASE_URL}/rest/v1/sent_messages?id=eq.{item['id']}",
                        headers=sb_headers(),
                        timeout=3
                    )
    except Exception as e:
        print(f"Cleanup check error: {e}")


def send_telegram_message(chat_id, text, reply_markup=None, track_for_delete=True):
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
        if response.get("ok") and track_for_delete:
            msg_id = response["result"]["message_id"]
            save_sent_message(chat_id, msg_id)
        return response
    except Exception as e:
        print(f"Send message error: {e}")
        return None


def edit_telegram_message(chat_id, message_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        res = requests.post(url, json=payload, timeout=5).json()
        return res
    except Exception as e:
        print(f"Edit message error: {e}")
        return None


def answer_callback(callback_id, text="", show_alert=False):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": text, "show_alert": show_alert},
            timeout=4
        )
    except Exception as e:
        print(f"Answer callback error: {e}")


def get_telegram_user_label(user_id):
    """Fetch display name from Telegram if possible, else fallback to User ID."""
    uid_str = str(user_id).strip()
    if not uid_str.lstrip("-").isdigit():
        return uid_str
    try:
        res = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getChat",
            params={"chat_id": uid_str},
            timeout=3
        ).json()
        if res.get("ok") and isinstance(res.get("result"), dict):
            u = res["result"]
            full_name = " ".join([p for p in [u.get("first_name", ""), u.get("last_name", "")] if p]).strip()
            username = f"@{u['username']}" if u.get("username") else ""
            if full_name and username:
                return f"{full_name} ({username})"
            if full_name:
                return full_name
            if username:
                return username
    except Exception:
        pass
    return f"User {uid_str}"


def fetch_all_subscriptions():
    get_url = f"{SUPABASE_URL}/rest/v1/user_subscriptions?select=id,user_id,anime_name,expires_at"
    res = requests.get(get_url, headers=sb_headers(), timeout=5).json()
    return res if isinstance(res, list) else []


def build_users_list_view(admin_chat_id):
    subs = fetch_all_subscriptions()
    if not subs:
        return "📁 Koi bhi active premium user nahi hai.", None

    grouped = {}
    for s in subs:
        uid = str(s.get("user_id", "")).strip()
        if not uid:
            continue
        grouped.setdefault(uid, []).append(s)

    if not grouped:
        return "📁 Koi bhi active premium user nahi hai.", None

    user_ids = list(grouped.keys())
    USER_LIST_CACHE[str(admin_chat_id)] = user_ids

    text_msg = "📋 **Premium Users List:**\n\n"
    keyboard = []

    for idx, uid in enumerate(user_ids):
        label = get_telegram_user_label(uid)
        text_msg += f"👤 `{uid}` — **{label}**\n"
        btn_title = f"👤 {label} ({uid})"[:60]
        keyboard.append([{"text": btn_title, "callback_data": f"usr_{idx}"}])

    return text_msg, {"inline_keyboard": keyboard}


def format_remaining_days(expires_str):
    if not expires_str:
        return "N/A"
    try:
        cleaned = expires_str.replace("Z", "").split("+")[0]
        exp_dt = datetime.fromisoformat(cleaned)
        diff = exp_dt - datetime.utcnow()
        days_left = max(0, diff.days)
        date_only = cleaned[:10]
        return f"{days_left} din bache (Exp: {date_only})"
    except Exception:
        return expires_str[:10]


def build_user_detail_view(admin_chat_id, user_idx):
    user_ids = USER_LIST_CACHE.get(str(admin_chat_id), [])
    if user_idx < 0 or user_idx >= len(user_ids):
        return build_users_list_view(admin_chat_id)

    uid = user_ids[user_idx]
    label = get_telegram_user_label(uid)
    all_subs = fetch_all_subscriptions()
    user_subs = [s for s in all_subs if str(s.get("user_id", "")).strip() == uid]
    USER_SUBS_CACHE[f"{admin_chat_id}_{user_idx}"] = user_subs

    text_msg = (
        f"👤 **User Information**\n"
        f"• **Naam:** {label}\n"
        f"• **User ID:** `{uid}`\n"
        f"• **Total Plans:** {len(user_subs)}\n\n"
    )

    keyboard = []
    if not user_subs:
        text_msg += "⚠️ Is user ke paas koi active anime plan nahi mila.\n"
    else:
        for s_idx, sub in enumerate(user_subs):
            anime_name = sub.get("anime_name", "Unknown")
            rem_info = format_remaining_days(sub.get("expires_at", ""))
            text_msg += (
                f"🎬 **Anime:** {anime_name}\n"
                f"⏳ **Duration / Expiry:** {rem_info}\n"
                f"-------------------------\n"
            )
            sub_id = sub.get("id")
            if sub_id is not None:
                keyboard.append([
                    {"text": f"❌ Remove ({anime_name})"[:55], "callback_data": f"rm_{user_idx}_{s_idx}"}
                ])

    keyboard.append([
        {"text": "📜 History", "callback_data": f"hst_{user_idx}"},
        {"text": "⬅️ Back", "callback_data": "bk_lst"}
    ])

    return text_msg, {"inline_keyboard": keyboard}


def build_user_history_view(admin_chat_id, user_idx):
    user_ids = USER_LIST_CACHE.get(str(admin_chat_id), [])
    if user_idx < 0 or user_idx >= len(user_ids):
        return build_users_list_view(admin_chat_id)

    uid = user_ids[user_idx]
    label = get_telegram_user_label(uid)

    # Fetch tokens opened/generated by this user
    tokens = []
    try:
        t_res = requests.get(
            f"{SUPABASE_URL}/rest/v1/episode_tokens?user_id=eq.{uid}&select=episode_id,uses,created_at",
            headers=sb_headers(),
            timeout=5
        ).json()
        if isinstance(t_res, list):
            tokens = t_res
    except Exception as e:
        print(f"Token history fetch error: {e}")

    # Map episode_id -> anime_name
    ep_to_anime = {}
    try:
        ep_res = requests.get(
            f"{SUPABASE_URL}/rest/v1/episodes?select=id,anime_name,episode_number",
            headers=sb_headers(),
            timeout=5
        ).json()
        if isinstance(ep_res, list):
            for ep in ep_res:
                eid = str(ep.get("id", ""))
                aname = ep.get("anime_name", "Unknown Anime")
                ep_num = ep.get("episode_number", "")
                ep_to_anime[eid] = f"{aname} (Ep {ep_num})" if ep_num else aname
    except Exception as e:
        print(f"Episodes fetch error: {e}")

    anime_open_counts = {}
    total_opens = 0
    for t in tokens:
        uses = int(t.get("uses") or 0)
        if uses <= 0:
            continue
        eid = str(t.get("episode_id", ""))
        anime_label = ep_to_anime.get(eid, eid or "Unknown")
        anime_open_counts[anime_label] = anime_open_counts.get(anime_label, 0) + uses
        total_opens += uses

    text_msg = (
        f"📜 **Link Open History**\n"
        f"• **Naam:** {label}\n"
        f"• **User ID:** `{uid}`\n"
        f"• **Total Opens:** {total_opens}\n\n"
    )

    if not anime_open_counts:
        text_msg += "ℹ️ Is user ne abhi tak kisi anime link ko open nahi kiya hai."
    else:
        for anime_label, count in anime_open_counts.items():
            text_msg += f"🎬 **{anime_label}** — `{count}` baar open kiya\n"

    keyboard = {
        "inline_keyboard": [
            [{"text": "⬅️ Back", "callback_data": f"bk_usr_{user_idx}"}]
        ]
    }
    return text_msg, keyboard


def get_join_keyboard(start_param=""):
    retry_url = f"https://t.me/{BOT_USERNAME}{start_param}"
    return {
        "inline_keyboard": [
            [{"text": "📢 Join ZK Dubbing Studio", "url": "https://t.me/zk_dubbing_studio"}],
            [{"text": "🛡️ Join Backup Channel", "url": CHANNEL_2_LINK}],
            [{"text": "🔄 Joined / Try Again", "url": retry_url}]
        ]
    }


def check_user_anime_access(user_id, episode_id):
    if user_id in ADMIN_IDS:
        return True
    try:
        ep_url = f"{SUPABASE_URL}/rest/v1/episodes?id=eq.{episode_id}&select=anime_name"
        ep_res = requests.get(ep_url, headers=sb_headers(), timeout=5).json()
        if not ep_res or not isinstance(ep_res, list):
            return False

        anime_name = ep_res[0].get("anime_name", "").strip().lower()
        sub_url = f"{SUPABASE_URL}/rest/v1/user_subscriptions?user_id=eq.{user_id}"
        sub_res = requests.get(sub_url, headers=sb_headers(), timeout=5).json()

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
        url = f"{SUPABASE_URL}/rest/v1/user_subscriptions?user_id=eq.{user_id}"
        res = requests.get(url, headers=sb_headers(), timeout=5).json()
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
            status = res["result"].get("status", "")
            return status in ["creator", "administrator", "member", "restricted"] and res["result"].get("is_member", True)
    except Exception as e:
        print(f"Member check error: {e}")
    return False


@app.route('/', methods=['GET'])
def home():
    cleanup_expired_messages()
    return "Kitsu Bot & Webhook is Active!", 200


@app.route('/cleanup', methods=['GET', 'POST'])
def cleanup_route():
    cleanup_expired_messages()
    return jsonify({"status": "cleaned"}), 200


@app.route('/', methods=['POST'])
@app.route('/<path:subpath>', methods=['POST'])
def webhook(subpath=''):
    try:
        update = request.get_json(silent=True)
        if not update:
            return jsonify({"status": "ok"}), 200

        threading.Thread(target=cleanup_expired_messages, daemon=True).start()

        if "callback_query" in update:
            cq = update["callback_query"]
            c_id = cq["message"]["chat"]["id"]
            m_id = cq["message"]["message_id"]
            u_id = cq["from"]["id"]
            data = cq.get("data", "")

            if u_id not in ADMIN_IDS:
                answer_callback(cq["id"], "Sirf admin hi iska use kar sakte hain.", show_alert=True)
                return jsonify({"status": "ok"}), 200

            if data.startswith("usr_"):
                try:
                    user_idx = int(data.split("_")[1])
                    txt, kb = build_user_detail_view(c_id, user_idx)
                    edit_telegram_message(c_id, m_id, txt, kb)
                    answer_callback(cq["id"])
                except Exception as e:
                    print(f"User detail callback error: {e}")
                    answer_callback(cq["id"], "Error loading user details.", show_alert=True)
                return jsonify({"status": "ok"}), 200

            if data.startswith("hst_"):
                try:
                    user_idx = int(data.split("_")[1])
                    txt, kb = build_user_history_view(c_id, user_idx)
                    edit_telegram_message(c_id, m_id, txt, kb)
                    answer_callback(cq["id"])
                except Exception as e:
                    print(f"History callback error: {e}")
                    answer_callback(cq["id"], "Error loading history.", show_alert=True)
                return jsonify({"status": "ok"}), 200

            if data.startswith("bk_usr_"):
                try:
                    user_idx = int(data.split("_")[2])
                    txt, kb = build_user_detail_view(c_id, user_idx)
                    edit_telegram_message(c_id, m_id, txt, kb)
                    answer_callback(cq["id"])
                except Exception as e:
                    print(f"Back to user callback error: {e}")
                    answer_callback(cq["id"])
                return jsonify({"status": "ok"}), 200

            if data == "bk_lst":
                try:
                    txt, kb = build_users_list_view(c_id)
                    edit_telegram_message(c_id, m_id, txt, kb)
                    answer_callback(cq["id"])
                except Exception as e:
                    print(f"Back to list callback error: {e}")
                    answer_callback(cq["id"])
                return jsonify({"status": "ok"}), 200

            if data.startswith("rm_"):
                try:
                    _, u_idx_s, s_idx_s = data.split("_")
                    u_idx = int(u_idx_s)
                    s_idx = int(s_idx_s)
                    cached_subs = USER_SUBS_CACHE.get(f"{c_id}_{u_idx}", [])
                    if 0 <= s_idx < len(cached_subs):
                        sub_id = cached_subs[s_idx].get("id")
                        if sub_id is not None:
                            requests.delete(
                                f"{SUPABASE_URL}/rest/v1/user_subscriptions?id=eq.{sub_id}",
                                headers=sb_headers(),
                                timeout=5
                            )
                    answer_callback(cq["id"], "Access removed!", show_alert=True)
                    txt, kb = build_user_detail_view(c_id, u_idx)
                    edit_telegram_message(c_id, m_id, txt, kb)
                except Exception as e:
                    print(f"Remove sub callback error: {e}")
                    answer_callback(cq["id"], "Remove error!", show_alert=True)
                return jsonify({"status": "ok"}), 200

            if data.startswith("del_"):
                sub_id = data.split("_")[1]
                try:
                    del_url = f"{SUPABASE_URL}/rest/v1/user_subscriptions?id=eq.{sub_id}"
                    requests.delete(del_url, headers=sb_headers(), timeout=5)
                    answer_callback(cq["id"], "User access removed successfully!", show_alert=True)
                    txt, kb = build_users_list_view(c_id)
                    edit_telegram_message(c_id, m_id, txt, kb)
                except Exception as e:
                    print(f"Delete callback error: {e}")
            return jsonify({"status": "ok"}), 200

        if "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]

            if "new_chat_members" in msg:
                for member in msg["new_chat_members"]:
                    if member.get("is_bot"):
                        continue
                    first_name = member.get("first_name", "Dost")
                    welcome_text = (
                        f"👋 **Welcome, {first_name}!**\n\n"
                        "Aage ke anime episodes aur updates ke liye hamare channels join karein:"
                    )
                    send_telegram_message(chat_id, welcome_text, reply_markup=get_join_keyboard())
                return jsonify({"status": "ok"}), 200

            text = msg.get("text", "").strip()
            caption = msg.get("caption", "").strip()

            full_text = text if text else caption
            parts = full_text.split()

            # 🧹 /clear Command
            if full_text.startswith("/clear") and user_id in ADMIN_IDS:
                try:
                    get_url = f"{SUPABASE_URL}/rest/v1/sent_messages?select=chat_id,message_id"
                    res = requests.get(get_url, headers=sb_headers(), timeout=5).json()

                    deleted_count = 0
                    if isinstance(res, list):
                        for item in res:
                            delete_telegram_message_now(item.get("chat_id"), item.get("message_id"))
                            deleted_count += 1

                        requests.delete(f"{SUPABASE_URL}/rest/v1/sent_messages?message_id=gt.0", headers=sb_headers(), timeout=5)

                    send_telegram_message(chat_id, f"🧹 Successfully cleared and deleted {deleted_count} bot messages/links across chats!")
                except Exception as e:
                    send_telegram_message(chat_id, f"❌ Clear error: {str(e)}")
                return jsonify({"status": "ok"}), 200

            # 🔗 /setepad Command
            if full_text.startswith("/setepad") and user_id in ADMIN_IDS:
                try:
                    parts = full_text.split(maxsplit=2)
                    if len(parts) < 3:
                        send_telegram_message(
                            chat_id,
                            "⚠️ Sahi format use karein:\n"
                            "`/setepad <telegram_link_ya_id> <ad_link>`\n\n"
                            "Example:\n`/setepad https://t.me/Kitsu_zk_bot?start=ep_1793711255297 https://links.otaku-provider-bots.workers.dev/...`"
                        )
                        return jsonify({"status": "ok"}), 200

                    raw_target = parts[1].strip()
                    new_ad_link = parts[2].strip()

                    target_ep_id = ""
                    if "ep_" in raw_target:
                        idx = raw_target.find("ep_")
                        candidate = raw_target[idx:]
                        target_ep_id = "".join([c for c in candidate if c.isalnum() or c == '_'])

                    if not target_ep_id.startswith("ep_"):
                        send_telegram_message(chat_id, "❌ Invalid Episode ID or Link! Sahi link ya ID dalein.")
                        return jsonify({"status": "ok"}), 200

                    headers = sb_headers(True)
                    headers["Prefer"] = "return=minimal"

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
                except Exception:
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
                    post_url = f"{SUPABASE_URL}/rest/v1/user_subscriptions"
                    resp = requests.post(post_url, json=payload, headers=sb_headers(True), timeout=5)
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
                    txt, kb = build_users_list_view(chat_id)
                    send_telegram_message(chat_id, txt, reply_markup=kb)
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
                except Exception:
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
                    send_telegram_message(
                        chat_id,
                        "✨ **Please Join Channel to Unlock Anime Links!**",
                        reply_markup=get_join_keyboard(retry_param)
                    )
                    return jsonify({"status": "ok"}), 200

                if is_premium:
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
                    episode_ad_link = "https://shrinkme.click/default"
                    try:
                        ep_query_res = requests.get(
                            f"{SUPABASE_URL}/rest/v1/episodes?id=eq.{target_episode_id}&select=ad_link",
                            headers=sb_headers(),
                            timeout=5
                        ).json()
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
                if not is_user_member(user_id, CHANNEL_1):
                    send_telegram_message(
                        chat_id,
                        "👋 **Welcome to Kitsu (キツ) - ZK Dubbing Studio!**\n\n"
                        "Pehle hamara channel join karein:",
                        reply_markup=get_join_keyboard()
                    )
                    return jsonify({"status": "ok"}), 200

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
