import os
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import requests

app = Flask(__name__, static_folder='.', static_url_path='')

SUPABASE_URL = "https://knefbynsdhgjuhlklyvu.supabase.co"
SUPABASE_KEY = "sb_publishable_tZxPCR45AXkjm73Fq81YAQ_VHEsGZVJ"

@app.route('/', methods=['GET'])
def home():
    return "Render Backend & Stream Server is Active!", 200

@app.route('/api/get-watch-token', methods=['GET'])
def get_watch_token():
    episode_id = request.args.get('episodeId')
    user_id = request.args.get('userId')
    
    if not episode_id or not user_id:
        return jsonify({"success": False, "message": "Missing parameters"}), 400
        
    token = secrets.token_hex(16)
    expires_at = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
    
    # Token generate karte waqt uses = 0 rakhenge
    payload = {
        "token": token,
        "episode_id": episode_id,
        "user_id": str(user_id),
        "uses": 0,
        "expires_at": expires_at
    }
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    try:
        resp = requests.post(f"{SUPABASE_URL}/rest/v1/episode_tokens", json=payload, headers=headers, timeout=5)
        if resp.status_code in [200, 201, 204]:
            return jsonify({"success": True, "token": token})
        else:
            return jsonify({"success": False, "message": "Database error"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/verify-token', methods=['GET'])
def verify_token():
    token = request.args.get('token')
    if not token:
        return jsonify({"success": False, "message": "Token missing"}), 400
        
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    
    try:
        # 1. Supabase se token ki details fetch karo
        url = f"{SUPABASE_URL}/rest/v1/episode_tokens?token=eq.{token}&select=*"
        res = requests.get(url, headers=headers, timeout=5).json()
        
        if not res or not isinstance(res, list) or len(res) == 0:
            return jsonify({"success": False, "message": "Invalid or expired token!"}), 400
            
        token_data = res[0]
        uses = token_data.get("uses", 0)
        expires_at_str = token_data.get("expires_at", "").replace("Z", "")
        
        # 2. Check karo ki kya yeh link pehle hi use ho chuki hai (Single-Use enforcement)
        if uses >= 1:
            return jsonify({"success": False, "message": "Yeh link pehle hi use ho chuki hai aur ab expire ho gayi hai!"}), 400
            
        # 3. Expiry time check karo (5 minutes)
        if expires_at_str:
            expiry = datetime.fromisoformat(expires_at_str)
            if datetime.utcnow() > expiry:
                return jsonify({"success": False, "message": "Token time expired!"}), 400
                
        # 4. TURANT uses count ko 1 kar do taaki koi dubara use na kar sake
        update_url = f"{SUPABASE_URL}/rest/v1/episode_tokens?token=eq.{token}"
        update_payload = {"uses": uses + 1}
        patch_headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        requests.patch(update_url, json=update_payload, headers=patch_headers, timeout=5)
        
        # Success response return karo taaki player video load kar sake
        return jsonify({
            "success": True, 
            "episodeId": token_data.get("episode_id"),
            "userId": token_data.get("user_id")
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000)
