import requests
import base64
import zlib
import json
import os

# Your live Discord connection line
WEBHOOK_URL = "https://discordapp.com/api/webhooks/1508269123602350200/CuOF_aExkClX9xqimNwBAkF8aIMqpuE0fYEE8m2EoGwL3jCKJImR5A_y7-_hAys_UwIp"

# OFFICIAL URL from Pixel's document
API_URL = "https://mcc-production.azurefd.net/api/ServerListListMultiplayerServers"

# Free cloud key-value store bucket
KV_URL = "https://kvdb.io/Vp4Z97g6E6BvM4s9KzWq3A/last_mcc_ping"

def get_xbox_live_token(refresh_token):
    """
    Executes the 3-step Xbox Live authentication chain using a Refresh Token.
    Returns the compiled 'x-auth-token' header string.
    """
    try:
        print("🔐 Authenticating with Xbox Live Services...")
        session = requests.Session()

        # --- STEP A: Refresh the Microsoft Account Access Token ---
        msa_url = "https://login.live.com/oauth20_token.srf"
        msa_data = {
            "grant_type": "refresh_token",
            "client_id": "000000004C12AE6F",  # Official Xbox App Client ID
            "refresh_token": refresh_token,
            "scope": "service::user.auth.xboxlive.com::MBI_SSL"
        }
        msa_res = session.post(msa_url, data=msa_data).json()
        access_token = msa_res.get("access_token")
        
        if not access_token:
            print("❌ Failed Step A: Could not refresh Microsoft Account Token.")
            return None

        # --- STEP B: Exchange MSA Token for an Xbox User Token ---
        xbl_url = "https://user.auth.xboxlive.com/user/authenticate"
        xbl_payload = {
            "Properties": {
                "AuthMethod": "RPS",
                "SiteName": "user.auth.xboxlive.com",
                "RpsTicket": f"d={access_token}"
            },
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT"
        }
        xbl_res = session.post(xbl_url, json=xbl_payload).json()
        user_token = xbl_res.get("Token")
        user_hash = xbl_res.get("DisplayClaims", {}).get("xui", [{}])[0].get("uhs")

        if not user_token or not user_hash:
            print("❌ Failed Step B: Could not acquire Xbox User Token.")
            return None

        # --- STEP C: Exchange User Token for an XSTS Token ---
        xsts_url = "https://xsts.auth.xboxlive.com/xsts/authorize"
        xsts_payload = {
            "Properties": {
                "SandboxId": "RETAIL",
                "UserTokens": [user_token]
            },
            "RelyingParty": "https://title.mplayfab.com/",
            "TokenType": "JWT"
        }
        xsts_res = session.post(xsts_url, json=xsts_payload)
        
        if xsts_res.status_code == 401:
            print("❌ Failed Step C: XSTS Authorization denied (Check age limits or account status).")
            return None
            
        xsts_token = xsts_res.json().get("Token")
        if not xsts_token:
            print("❌ Failed Step C: XSTS Token missing from response.")
            return None

        print("✅ Xbox Live Security Handshake Complete!")
        return f"XBL3.0 x={user_hash};{xsts_token}"

    except Exception as e:
        print(f"❌ Critical Authentication Error: {e}")
        return None

def fetch_live_mcc_data():
    try:
        # Fetch the permanent secret refresh token from GitHub Environment Secrets
        refresh_token = os.getenv("XBOX_REFRESH_TOKEN")
        if not refresh_token:
            print("❌ Error: XBOX_REFRESH_TOKEN variable is not set in GitHub Secrets.")
            return []

        # Get our freshly minted legal session ticket
        auth_header_value = get_xbox_live_token(refresh_token)
        if not auth_header_value:
            print("❌ Aborting tracking sweep due to authentication failure.")
            return []

        print("🌐 Step 2: Connecting directly to Xbox Live / Microsoft CGB Gateway...")
        payload = {
            "BuildId": "2025.08.16.178512.1-Release",
            "MaxResults": 2000
        }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MCC/1.3447.0.0 (Windows; RETAIL)",
            "x-auth-token": auth_header_value
        }
        
        response = requests.post(API_URL, json=payload, headers=headers, timeout=15)
        print(f"📡 Official Microsoft Server Response Code: {response.status_code}")
        
        if response.status_code == 200:
            raw_data = response.json()
            games_list = raw_data.get("data", {}).get("Games", [])
            print(f"📊 Successfully reached network. Processing {len(games_list)} encrypted server entries.")
            return games_list
        return []
    except Exception as e:
        print(f"❌ Failed to communicate with official Microsoft server: {e}")
        return []

def filter_parkour_only(raw_games):
    filtered_list = []
    print("\n--- 🛠️ DECODING & PARSING LIVE LOBBIES ---")
    
    for item in raw_games:
        encoded_payload = item.get("GameServerData")
        if not encoded_payload:
            continue
            
        try:
            # 1. Decode base64 2. Decompress Deflate raw string data
            compressed_bytes = base64.b64decode(encoded_payload)
            decompressed_json = zlib.decompress(compressed_bytes, -zlib.MAX_WBITS)
            game_data = json.loads(decompressed_json)
            
            # Extract names according to the decoded schema specification
            title = str(game_data.get("session_name", "Custom Game"))
            
            variants = game_data.get("playlistVariants", {})
            map_variants = variants.get("mapVariants", [{}])
            map_name = str(map_variants[0].get("name", "Unknown Map"))
            
            game_variants = variants.get("gameVariants", [{}])
            mode_name = str(game_variants[0].get("name", "Unknown Mode"))
            
            current_players = len(game_data.get("players", []))
            max_players = game_data.get("max_players", 16)
            
            title_lower = title.lower()
            map_lower = map_name.lower()
            mode_lower = mode_name.lower()
            
            if "parkour" in title_lower or "跑" in title_lower or "parkour" in map_lower or "parkour" in mode_lower:
                print(f"🔥 MATCH FOUND: '{title}' running map '{map_name}'")
                
                filtered_list.append({
                    "name": title,
                    "map": map_name,
                    "current_players": current_players,
                    "max_players": max_players
                })
        except Exception:
            continue
            
    print(f"🔍 Filtering Complete: Identified {len(filtered_list)} active Parkour matches.\n")
    return filtered_list

def delete_previous_ping():
    try:
        res = requests.get(KV_URL, timeout=5)
        if res.status_code == 200:
            old_message_id = res.text.strip()
            if old_message_id:
                print(f"🗑️ Removing old message (ID: {old_message_id}) from Discord...")
                requests.delete(f"{WEBHOOK_URL}/messages/{old_message_id}", timeout=5)
    except Exception:
        pass

def save_new_ping_id(response):
    if response.status_code in [200, 201]:
        new_id = response.json().get("id")
        try:
            requests.put(KV_URL, data=str(new_id), timeout=5)
            print(f"💾 Saved message tracking ID to cloud locker: {new_id}")
        except Exception:
            pass

def send_to_discord(lobbies):
    delete_previous_ping()
    print("🚀 Step 3: Delivering live match summary package to Discord...")
    
    embed = {
        "title": "🏃‍♂️ Live Parkour Lobbies Found!",
        "description": f"Found **{len(lobbies)}** active parkour server(s) running right now.",
        "color": 5763719,
        "fields": []
    }
    
    for game in lobbies:
        embed["fields"].append({
            "name": f"🎮 {game['name']}",
            "value": f"**Map:** {game['map']} | **Players:** {game['current_players']}/{game['max_players']}",
            "inline": False
        })
        
    payload = {"username": "Halo Parkour Tracker", "embeds": [embed]}
    response = requests.post(f"{WEBHOOK_URL}?wait=true", json=payload)
    save_new_ping_id(response)

if __name__ == "__main__":
    print("=== RUNNING HALO TRACKER SWEEP ===")
    live_lobbies = fetch_live_mcc_data()
    parkour_matches = filter_parkour_only(live_lobbies)

    if parkour_matches:
        send_to_discord(parkour_matches)
    else:
        print("🔍 No parkour lobbies active. Posting status update.")
        delete_previous_ping()
        
        empty_embed = {
            "title": "🏃‍♂️ No Parkour Lobbies",
            "description": "No live parkour lobbies are active at the moment. Checking again in 20 minutes!",
            "color": 16711680 
        }
        payload = {"username": "Halo Parkour Tracker", "embeds": [empty_embed]}
        response = requests.post(f"{WEBHOOK_URL}?wait=true", json=payload)
        save_new_ping_id(response)
        
    print("=== SWEEP COMPLETE ===")