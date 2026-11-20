import os
import uuid
import requests
import threading
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8934334004:AAESWVI3LqraM8eztb9tJldPOkzXGn0tI2c")
WEB_APP_DOMAIN = os.getenv("WEB_APP_DOMAIN", "https://kitsu-watch-zk.vercel.app")
BOT_USERNAME = "Kitsu_zk_bot"

POSTER_URL = os.getenv(
    "POSTER_URL",
    "https://i.ibb.co/FbBPKwB1/photo-2026-11-20-04-31-24-7710106632994160668.jpg"
)

CHANNEL_1_ID = "@zk_dubbing_studio"
CHANNEL_1_URL = "https://t.me/zk_dubbing_studio"

CHANNEL_2_ID = "@IntheClearMoonlitDuskhindidub"
CHANNEL_2_URL = "https://t.me/IntheClearMoonlitDuskhindidub"

CHANNEL_3_ID = -1003927801868
CHANNEL_3_URL = "https://t.me/+H3TykxfXuwdlODNl"

ADMIN_IDS = [6144546817, 8528056660]

ADMIN_ONLY_COMMANDS = (
    "/ban",
    "/unban",
    "/banlist",
    "/leaderboard",
    "/check",
    "/replace",
    "/broadcast",
    "/clear",
    "/setepad",
    "/adduser",
    "/users",
    "/getlink",
)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://knefbynsdhgjuhlklyvu.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_tZxPCR45AXkjm73Fq81YAQ_VHEsGZVJ")

USER_LIST_CACHE = {}
USER_SUBS_CACHE = {}
CHANNEL_3_REQUESTED_USERS = set()
PENDING_EPISODE_CACHE = {}
ACTIVE_BROADCAST_CANCEL = {}


def sb_headers(json_body=False):
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def track_bot_user(user_id):
    try:
        uid = str(user_id).strip()
        if not uid:
            return
        headers = sb_headers(True)
        headers["Prefer"] = "resolution=ignore-duplicates,return=minimal"
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/bot_users",
            json={"user_id": uid},
            headers=headers,
            timeout=4
        )
        if r.status_code not in [200, 201, 204]:
            print(f"track_bot_user status {r.status_code}: {r.text}")
    except Exception as e:
        print(f"track_bot_user error: {e}")


def record_channel_3_request(user_id):
    uid = str(user_id).strip()
    if not uid:
        return
    CHANNEL_3_REQUESTED_USERS.add(uid)
    try:
        headers = sb_headers(True)
        headers["Prefer"] = "resolution=ignore-duplicates,return=minimal"
        requests.post(
            f"{SUPABASE_URL}/rest/v1/channel_requests",
            json={"user_id": uid, "channel_id": str(CHANNEL_3_ID)},
            headers=headers,
            timeout=3
        )
    except Exception:
        pass


def has_requested_channel_3(user_id):
    uid = str(user_id).strip()
    if uid in CHANNEL_3_REQUESTED_USERS:
        return True
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/channel_requests?user_id=eq.{uid}&channel_id=eq.{CHANNEL_3_ID}&select=user_id",
            headers=sb_headers(),
            timeout=3
        ).json()
        if isinstance(res, list) and len(res) > 0:
            CHANNEL_3_REQUESTED_USERS.add(uid)
            return True
    except Exception:
        pass
    return False


def is_user_banned(user_id):
    if user_id in ADMIN_IDS:
        return False
    try:
        uid = str(user_id).strip()
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/banned_users?user_id=eq.{uid}&select=user_id",
            headers=sb_headers(),
            timeout=4
        ).json()
        return isinstance(res, list) and len(res) > 0
    except Exception:
        return False


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


def send_telegram_photo(chat_id, photo_url, caption, reply_markup=None, track_for_delete=True):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "Markdown",
        "protect_content": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        response = requests.post(url, json=payload, timeout=8).json()
        if response.get("ok"):
            if track_for_delete:
                msg_id = response["result"]["message_id"]
                save_sent_message(chat_id, msg_id)
            return response
    except Exception as e:
        print(f"Send photo error: {e}")

    return send_telegram_message(chat_id, caption, reply_markup=reply_markup, track_for_delete=track_for_delete)


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


def save_broadcast_delivery(batch_id, target_chat_id, delivered_msg_id):
    try:
        h = sb_headers(True)
        h["Prefer"] = "return=minimal"
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/broadcast_logs",
            json={
                "batch_id": batch_id,
                "chat_id": str(target_chat_id),
                "message_id": int(delivered_msg_id)
            },
            headers=h,
            timeout=4
        )
        if r.status_code not in [200, 201, 204]:
            print(f"Broadcast log status {r.status_code}: {r.text}")
    except Exception as e:
        print(f"Broadcast log save error: {e}")


def format_broadcast_report(status_label, total, success, blocked, deleted_acc, unsuccessful):
    return (
        f"**Broadcast {status_label}**\n\n"
        f"◇ Total Users: `{total}`\n"
        f"◇ Successful: `{success}`\n"
        f"◇ Blocked Users: `{blocked}`\n"
        f"◇ Deleted Accounts: `{deleted_acc}`\n"
        f"◇ Unsuccessful: `{unsuccessful}`"
    )


def get_telegram_user_label(user_id):
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


def is_single_channel_member(user_id, channel_id):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        res = requests.get(url, params={"chat_id": channel_id, "user_id": user_id}, timeout=4).json()
        if res.get("ok"):
            status = res["result"].get("status", "")
            return status in ["creator", "administrator", "member", "restricted"] and res["result"].get("is_member", True)
    except Exception as e:
        print(f"Member check error for {channel_id}: {e}")
    return False


def get_missing_channels(user_id):
    if user_id in ADMIN_IDS:
        return []

    missing = []
    if not is_single_channel_member(user_id, CHANNEL_1_ID):
        missing.append(("📢 Channel 1", CHANNEL_1_URL))
    if not is_single_channel_member(user_id, CHANNEL_2_ID):
        missing.append(("🎬 Channel 2", CHANNEL_2_URL))
    if not (is_single_channel_member(user_id, CHANNEL_3_ID) or has_requested_channel_3(user_id)):
        missing.append(("🔐 Channel 3", CHANNEL_3_URL))
    return missing


def build_dynamic_join_keyboard(user_id, episode_id=None):
    missing = get_missing_channels(user_id)
    rows = [[{"text": label, "url": url}] for label, url in missing]
    if episode_id:
        PENDING_EPISODE_CACHE[str(user_id)] = episode_id
    rows.append([{"text": "🔄 Try Again", "callback_data": "chk_join"}])
    return {"inline_keyboard": rows}


def deliver_episode_link(chat_id, user_id, target_episode_id):
    is_premium = check_user_anime_access(user_id, target_episode_id)
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

        if "chat_join_request" in update:
            cjr = update["chat_join_request"]
            req_chat_id = cjr.get("chat", {}).get("id")
            req_user_id = cjr.get("from", {}).get("id")
            if req_chat_id == CHANNEL_3_ID and req_user_id:
                record_channel_3_request(req_user_id)
            return jsonify({"status": "ok"}), 200

        if "callback_query" in update:
            cq = update["callback_query"]
            c_id = cq["message"]["chat"]["id"]
            m_id = cq["message"]["message_id"]
            u_id = cq["from"]["id"]
            u_first = cq.get("from", {}).get("first_name", "Dost")
            data = cq.get("data", "")

            if data == "chk_join":
                missing = get_missing_channels(u_id)
                if not missing:
                    delete_telegram_message_now(c_id, m_id)
                    answer_callback(cq["id"], "✅ Sabhi channels verify ho gaye!")
                    ep_id = PENDING_EPISODE_CACHE.pop(str(u_id), None)
                    if ep_id:
                        deliver_episode_link(c_id, u_id, ep_id)
                    else:
                        welcome_caption = (
                            f"👋 **Welcome to ZK Dubbing Studio, {u_first}!**\n\n"
                            "@zk\\_dubbing\\_studio — is channel par hamare jitne anime dub kiye hain, "
                            "woh aap watch aur download kar sakte hain."
                        )
                        send_telegram_photo(c_id, POSTER_URL, welcome_caption)
                else:
                    answer_callback(cq["id"], "⚠️ Abhi kuch channel join karna baaki hai!", show_alert=True)
                    updated_kb = build_dynamic_join_keyboard(u_id, PENDING_EPISODE_CACHE.get(str(u_id)))
                    try:
                        requests.post(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageReplyMarkup",
                            json={"chat_id": c_id, "message_id": m_id, "reply_markup": updated_kb},
                            timeout=4
                        )
                    except Exception:
                        pass
                return jsonify({"status": "ok"}), 200

            if u_id not in ADMIN_IDS:
                answer_callback(cq["id"], "Sirf Owner aur Admin hi iska use kar sakte hain.", show_alert=True)
                return jsonify({"status": "ok"}), 200

            if data.startswith("bc_stop_"):
                batch_key = data[len("bc_stop_"):]
                ACTIVE_BROADCAST_CANCEL[batch_key] = True
                answer_callback(cq["id"], "🛑 Broadcast rokne ka signal bhej diya gaya hai!", show_alert=True)
                return jsonify({"status": "ok"}), 200

            if data.startswith("bc_del_"):
                batch_key = data[len("bc_del_"):]
                answer_callback(cq["id"], "🗑️ Sabhi users se message delete kiya ja raha hai...")
                deleted_msgs = 0
                try:
                    rows = requests.get(
                        f"{SUPABASE_URL}/rest/v1/broadcast_logs?batch_id=eq.{batch_key}&select=id,chat_id,message_id",
                        headers=sb_headers(),
                        timeout=6
                    ).json()
                    if isinstance(rows, list):
                        for r in rows:
                            delete_telegram_message_now(r.get("chat_id"), r.get("message_id"))
                            deleted_msgs += 1
                        requests.delete(
                            f"{SUPABASE_URL}/rest/v1/broadcast_logs?batch_id=eq.{batch_key}",
                            headers=sb_headers(),
                            timeout=5
                        )
                except Exception as e:
                    print(f"Broadcast delete error: {e}")

                edit_telegram_message(
                    c_id,
                    m_id,
                    f"🗑️ **Broadcast Deleted From Users**\n\nTotal `{deleted_msgs}` user message(s) delete kiye gaye."
                )
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
            first_name = msg.get("from", {}).get("first_name", "Dost")

            if is_user_banned(user_id):
                return jsonify({"status": "ok"}), 200

            track_bot_user(user_id)

            if "new_chat_members" in msg:
                for member in msg["new_chat_members"]:
                    if member.get("is_bot"):
                        continue
                    m_uid = member.get("id")
                    m_name = member.get("first_name", "Dost")
                    join_caption = (
                        f"👋 **Welcome to ZK Dubbing Studio, {m_name}!**\n\n"
                        "Aage ke episodes aur updates ke liye neeche diye gaye channels join karein:"
                    )
                    send_telegram_photo(
                        chat_id,
                        POSTER_URL,
                        join_caption,
                        reply_markup=build_dynamic_join_keyboard(m_uid)
                    )
                return jsonify({"status": "ok"}), 200

            text = msg.get("text", "").strip()
            caption = msg.get("caption", "").strip()

            full_text = text if text else caption
            parts = full_text.split()
            cmd_token = parts[0].split("@")[0].lower() if parts else ""

            if cmd_token in ADMIN_ONLY_COMMANDS and user_id not in ADMIN_IDS:
                send_telegram_message(chat_id, "❌ Yeh command sirf Owner aur Admin hi use kar sakte hain!")
                return jsonify({"status": "ok"}), 200

            if cmd_token == "/ban":
                if len(parts) < 2:
                    send_telegram_message(chat_id, "⚠️ Use: `/ban <user_id>`")
                    return jsonify({"status": "ok"}), 200
                target_id = parts[1].strip()
                try:
                    h = sb_headers(True)
                    h["Prefer"] = "resolution=ignore-duplicates,return=minimal"
                    resp = requests.post(f"{SUPABASE_URL}/rest/v1/banned_users", json={"user_id": target_id}, headers=h, timeout=5)
                    if resp.status_code in [200, 201, 204]:
                        send_telegram_message(chat_id, f"🚫 User `{target_id}` ko ban kar diya gaya hai.")
                    else:
                        send_telegram_message(chat_id, f"❌ Ban error: {resp.text}")
                except Exception as e:
                    send_telegram_message(chat_id, f"❌ Error: {str(e)}")
                return jsonify({"status": "ok"}), 200

            if cmd_token == "/unban":
                if len(parts) < 2:
                    send_telegram_message(chat_id, "⚠️ Use: `/unban <user_id>`")
                    return jsonify({"status": "ok"}), 200
                target_id = parts[1].strip()
                try:
                    requests.delete(f"{SUPABASE_URL}/rest/v1/banned_users?user_id=eq.{target_id}", headers=sb_headers(), timeout=5)
                    send_telegram_message(chat_id, f"✅ User `{target_id}` ko unban kar diya gaya hai.")
                except Exception as e:
                    send_telegram_message(chat_id, f"❌ Error: {str(e)}")
                return jsonify({"status": "ok"}), 200

            if cmd_token == "/banlist":
                try:
                    res = requests.get(f"{SUPABASE_URL}/rest/v1/banned_users?select=user_id", headers=sb_headers(), timeout=5).json()
                    if isinstance(res, list) and len(res) > 0:
                        ids_txt = "\n".join([f"• `{r.get('user_id')}`" for r in res])
                        send_telegram_message(chat_id, f"🚫 **Banned Users:**\n\n{ids_txt}")
                    else:
                        send_telegram_message(chat_id, "ℹ️ Koi banned user nahi hai.")
                except Exception as e:
                    send_telegram_message(chat_id, f"❌ Error: {str(e)}")
                return jsonify({"status": "ok"}), 200

            if cmd_token == "/leaderboard":
                try:
                    tokens = requests.get(f"{SUPABASE_URL}/rest/v1/episode_tokens?select=user_id,episode_id,uses", headers=sb_headers(), timeout=5).json()
                    eps = requests.get(f"{SUPABASE_URL}/rest/v1/episodes?select=id,anime_name", headers=sb_headers(), timeout=5).json()
                    ep_map = {str(e.get("id")): e.get("anime_name", "Unknown") for e in eps} if isinstance(eps, list) else {}

                    anime_counts = {}
                    user_counts = {}
                    if isinstance(tokens, list):
                        for t in tokens:
                            u_cnt = int(t.get("uses") or 0)
                            if u_cnt <= 0:
                                continue
                            aname = ep_map.get(str(t.get("episode_id")), "Unknown")
                            uid_s = str(t.get("user_id", ""))
                            anime_counts[aname] = anime_counts.get(aname, 0) + u_cnt
                            if uid_s:
                                user_counts[uid_s] = user_counts.get(uid_s, 0) + u_cnt

                    top_animes = sorted(anime_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                    top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:5]

                    lb_msg = "🏆 **Leaderboard**\n\n**🔥 Top Animes (Opens):**\n"
                    if top_animes:
                        for i, (a, c) in enumerate(top_animes, 1):
                            lb_msg += f"{i}. {a} — `{c}`\n"
                    else:
                        lb_msg += "No data yet.\n"

                    lb_msg += "\n**👑 Top Active Users (Opens):**\n"
                    if top_users:
                        for i, (u, c) in enumerate(top_users, 1):
                            lb_msg += f"{i}. `{u}` — `{c}`\n"
                    else:
                        lb_msg += "No data yet.\n"

                    send_telegram_message(chat_id, lb_msg)
                except Exception as e:
                    send_telegram_message(chat_id, f"❌ Leaderboard error: {str(e)}")
                return jsonify({"status": "ok"}), 200

            if cmd_token == "/check":
                query_anime = full_text.split(maxsplit=1)[1].strip().lower() if len(parts) > 1 else ""
                if not query_anime:
                    send_telegram_message(chat_id, "⚠️ Use: `/check <anime_name>`")
                    return jsonify({"status": "ok"}), 200
                try:
                    eps = requests.get(f"{SUPABASE_URL}/rest/v1/episodes?select=id,anime_name,episode_number", headers=sb_headers(), timeout=5).json()
                    matched = [e for e in eps if query_anime in str(e.get("anime_name", "")).lower()] if isinstance(eps, list) else []
                    if matched:
                        lines = "\n".join([f"• `{m.get('id')}` — {m.get('anime_name')} (Ep {m.get('episode_number')})" for m in matched[:20]])
                        send_telegram_message(chat_id, f"✅ **{len(matched)} Episode(s) Found:**\n\n{lines}")
                    else:
                        send_telegram_message(chat_id, f"❌ `{query_anime}` ke liye koi episode nahi mila.")
                except Exception as e:
                    send_telegram_message(chat_id, f"❌ Check error: {str(e)}")
                return jsonify({"status": "ok"}), 200

            if cmd_token == "/replace":
                rep_parts = full_text.split(maxsplit=2)
                if len(rep_parts) < 3:
                    send_telegram_message(chat_id, "⚠️ Use: `/replace <ep_id> <new_url>`")
                    return jsonify({"status": "ok"}), 200
                ep_id_rep = rep_parts[1].strip()
                new_url_rep = rep_parts[2].strip()
                try:
                    h = sb_headers(True)
                    h["Prefer"] = "return=minimal"
                    resp = requests.patch(f"{SUPABASE_URL}/rest/v1/episodes?id=eq.{ep_id_rep}", json={"video_url": new_url_rep}, headers=h, timeout=5)
                    if resp.status_code in [200, 204]:
                        send_telegram_message(chat_id, f"✅ Episode `{ep_id_rep}` ka link update ho gaya hai.")
                    else:
                        send_telegram_message(chat_id, f"❌ Update error: {resp.text}")
                except Exception as e:
                    send_telegram_message(chat_id, f"❌ Error: {str(e)}")
                return jsonify({"status": "ok"}), 200

            if cmd_token == "/broadcast":
                reply_msg = msg.get("reply_to_message")
                if not reply_msg:
                    send_telegram_message(
                        chat_id,
                        "⚠️ Pehle apna message bhejein, fir **us message par reply karke** `/broadcast` likhein."
                    )
                    return jsonify({"status": "ok"}), 200

                reply_msg_id = reply_msg.get("message_id")
                batch_id = uuid.uuid4().hex[:10]
                ACTIVE_BROADCAST_CANCEL[batch_id] = False

                status_resp = send_telegram_message(
                    chat_id,
                    "📣 **Broadcast Starting...**",
                    reply_markup={
                        "inline_keyboard": [
                            [{"text": "🛑 Stop Broadcast", "callback_data": f"bc_stop_{batch_id}"}]
                        ]
                    },
                    track_for_delete=False
                )
                status_msg_id = status_resp["result"]["message_id"] if status_resp and status_resp.get("ok") else None

                users_res = requests.get(f"{SUPABASE_URL}/rest/v1/bot_users?select=user_id", headers=sb_headers(), timeout=5).json()
                user_ids = []
                if isinstance(users_res, list):
                    for u in users_res:
                        uid_b = str(u.get("user_id", "")).strip()
                        if uid_b and uid_b not in user_ids:
                            user_ids.append(uid_b)
                else:
                    print(f"bot_users unexpected response: {users_res}")

                total_users = len(user_ids)
                successful = 0
                blocked_users = 0
                deleted_accounts = 0
                unsuccessful = 0
                was_cancelled = False

                for uid_b in user_ids:
                    if ACTIVE_BROADCAST_CANCEL.get(batch_id):
                        was_cancelled = True
                        break

                    try:
                        cp_res = requests.post(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/copyMessage",
                            json={
                                "chat_id": uid_b,
                                "from_chat_id": chat_id,
                                "message_id": reply_msg_id
                            },
                            timeout=5
                        ).json()

                        if cp_res.get("ok"):
                            successful += 1
                            delivered_mid = cp_res.get("result", {}).get("message_id")
                            if delivered_mid is not None:
                                save_broadcast_delivery(batch_id, uid_b, delivered_mid)
                        else:
                            err_code = cp_res.get("error_code", 0)
                            desc = str(cp_res.get("description", "")).lower()
                            if err_code == 403 or "blocked" in desc:
                                blocked_users += 1
                            elif "deactivated" in desc or "user is deactivated" in desc:
                                deleted_accounts += 1
                            else:
                                unsuccessful += 1
                    except Exception:
                        unsuccessful += 1

                ACTIVE_BROADCAST_CANCEL.pop(batch_id, None)
                status_label = "cancelled" if was_cancelled else "complete"
                report_text = format_broadcast_report(
                    status_label,
                    total_users,
                    successful,
                    blocked_users,
                    deleted_accounts,
                    unsuccessful
                )
                done_markup = {
                    "inline_keyboard": [
                        [{"text": "🗑️ Delete From All Users", "callback_data": f"bc_del_{batch_id}"}]
                    ]
                }

                if status_msg_id:
                    edit_telegram_message(chat_id, status_msg_id, report_text, done_markup)
                else:
                    send_telegram_message(chat_id, report_text, reply_markup=done_markup, track_for_delete=False)

                return jsonify({"status": "ok"}), 200

            if cmd_token == "/clear":
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

            if cmd_token == "/setepad":
                try:
                    sp_parts = full_text.split(maxsplit=2)
                    if len(sp_parts) < 3:
                        send_telegram_message(
                            chat_id,
                            "⚠️ Sahi format use karein:\n"
                            "`/setepad <telegram_link_ya_id> <ad_link>`\n\n"
                            "Example:\n`/setepad https://t.me/Kitsu_zk_bot?start=ep_1793711255297 https://links.otaku-provider-bots.workers.dev/...`"
                        )
                        return jsonify({"status": "ok"}), 200

                    raw_target = sp_parts[1].strip()
                    new_ad_link = sp_parts[2].strip()

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

            if cmd_token == "/adduser":
                try:
                    au_parts = full_text.split(maxsplit=2)
                    if len(au_parts) < 3:
                        raise ValueError("Invalid format")

                    _, target_user_id, remaining = au_parts
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

            if cmd_token == "/users":
                try:
                    txt, kb = build_users_list_view(chat_id)
                    send_telegram_message(chat_id, txt, reply_markup=kb)
                except Exception as e:
                    send_telegram_message(chat_id, f"❌ Error fetching users: {str(e)}")
                return jsonify({"status": "ok"}), 200

            if cmd_token == "/getlink":
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

            if cmd_token == "/report":
                report_body = full_text.split(maxsplit=1)[1].strip() if len(parts) > 1 else ""
                if not report_body:
                    send_telegram_message(chat_id, "⚠️ Kripya apni issue likhein:\n`/report Episode 3 server 1 load nahi ho raha`")
                    return jsonify({"status": "ok"}), 200
                alert = (
                    f"📩 **New User Report**\n"
                    f"• **From:** {first_name} (`{user_id}`)\n"
                    f"• **Issue:** {report_body}"
                )
                for adm in ADMIN_IDS:
                    send_telegram_message(adm, alert, track_for_delete=False)
                send_telegram_message(chat_id, "✅ Aapki report admin tak bhej di gayi hai. Dhanyawad!")
                return jsonify({"status": "ok"}), 200

            target_episode_id = None
            if "start=ep_" in full_text:
                try:
                    sub = full_text.split("start=")[1]
                    target_episode_id = sub.split()[0].split("&")[0]
                except Exception:
                    pass
            elif len(parts) > 1 and cmd_token == "/start" and parts[1].startswith("ep_"):
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
                missing = get_missing_channels(user_id)
                if missing:
                    join_caption = (
                        f"👋 **Welcome to ZK Dubbing Studio, {first_name}!**\n\n"
                        "Episode link unlock karne ke liye pehle neeche diye gaye channels join karein:"
                    )
                    send_telegram_photo(
                        chat_id,
                        POSTER_URL,
                        join_caption,
                        reply_markup=build_dynamic_join_keyboard(user_id, target_episode_id)
                    )
                    return jsonify({"status": "ok"}), 200

                deliver_episode_link(chat_id, user_id, target_episode_id)
                return jsonify({"status": "ok"}), 200

            if cmd_token == "/start":
                missing = get_missing_channels(user_id)
                if missing:
                    join_caption = (
                        f"👋 **Welcome to ZK Dubbing Studio, {first_name}!**\n\n"
                        "Aage badhne ke liye neeche diye gaye channels join karein:"
                    )
                    send_telegram_photo(
                        chat_id,
                        POSTER_URL,
                        join_caption,
                        reply_markup=build_dynamic_join_keyboard(user_id)
                    )
                    return jsonify({"status": "ok"}), 200

                welcome_caption = (
                    f"👋 **Welcome to ZK Dubbing Studio, {first_name}!**\n\n"
                    "@zk\\_dubbing\\_studio — is channel par hamare jitne anime dub kiye hain, "
                    "woh aap watch aur download kar sakte hain."
                )
                send_telegram_photo(chat_id, POSTER_URL, welcome_caption)

    except Exception as e:
        print(f"Webhook error: {e}")

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(port=5000)
