import requests

# Your live Discord connection line
WEBHOOK_URL = "https://discordapp.com/api/webhooks/1508269123602350200/CuOF_aExkClX9xqimNwBAkF8aIMqpuE0fYEE8m2EoGwL3jCKJImR5A_y7-_hAys_UwIp"

# STABLE FIX: Using a highly reliable, open public custom games tracker API mirror
API_URL = "https://mcc.project-solas.com/api/v1/cgb"

# Free cloud key-value store bucket
KV_URL = "https://kvdb.io/Vp4Z97g6E6BvM4s9KzWq3A/last_mcc_ping"

def fetch_live_mcc_data():
    try:
        print("🌐 Step 1: Contacting stable open Halo MCC database mirror...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        response = requests.get(API_URL, headers=headers, timeout=10)
        
        print(f"📡 Server Response Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            # If the data is an open list right at the root, return it
            if isinstance(data, list):
                print(f"📊 Successfully fetched direct list. Found {len(data)} total active matches.")
                return data
            # Fallback if it's packed inside a 'servers' or 'lobbies' dictionary key
            elif isinstance(data, dict):
                servers = data.get("servers", data.get("lobbies", data.get("Result", [])))
                print(f"📊 Successfully fetched server list. Found {len(servers)} total active matches.")
                return servers
        return []
    except Exception as e:
        print(f"❌ Failed to reach data pipeline: {e}")
        return []

def filter_parkour_only(all_games):
    filtered_list = []
    
    print("\n--- 🛠️ LIVE MATCH CHECK ---")
    for game in all_games:
        # Check standard key variations across API models
        title = str(game.get("name", game.get("ServerName", game.get("Name", "UNKNOWN"))))
        map_name = str(game.get("map", game.get("MapName", "UNKNOWN")))
        mode = str(game.get("gamemode", game.get("GameMode", "UNKNOWN")))
        
        # Print matching rooms directly to your GitHub logs
        print(f"• Checking Room: '{title}' | Map: '{map_name}'")
        
        title_lower = title.lower()
        map_lower = map_name.lower()
        mode_lower = mode.lower()
        
        if "parkour" in title_lower or "parkour" in map_lower or "parkour" in mode_lower:
            print(f"🔥 TARGET MATCH IDENTIFIED: '{title}'")
            filtered_list.append(game)
            
    print(f"🔍 Filtering Complete: Found {len(filtered_list)} true Parkour matches.\n")
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
    print("🚀 Step 3: Delivering update package to Discord...")
    
    embed = {
        "title": "🏃‍♂️ Live Parkour Lobbies Found!",
        "description": f"Found **{len(lobbies)}** active parkour server(s) running right now.",
        "color": 5763719,
        "fields": []
    }
    
    for game in lobbies:
        name = game.get("name", game.get("ServerName", "Unknown Lobby"))
        m_name = game.get("map", game.get("MapName", "Unknown Map"))
        curr_p = game.get("current_players", game.get("PlayerCount", "?"))
        max_p = game.get("max_players", game.get("MaxPlayers", "?"))
        
        embed["fields"].append({
            "name": f"🎮 {name}",
            "value": f"**Map:** {m_name} | **Players:** {curr_p}/{max_p}",
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