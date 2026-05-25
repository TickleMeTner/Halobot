import requests

# Your live Discord connection line
WEBHOOK_URL = "https://discordapp.com/api/webhooks/1508269123602350200/CuOF_aExkClX9xqimNwBAkF8aIMqpuE0fYEE8m2EoGwL3jCKJImR5A_y7-_hAys_UwIp"
# The direct backend JSON stream discovered from your network tab
API_URL = "https://backend.jumpnexus.org:8445/site/cgbdata"

# Free cloud key-value store bucket
KV_URL = "https://kvdb.io/Vp4Z97g6E6BvM4s9KzWq3A/last_mcc_ping"

def fetch_live_mcc_data():
    try:
        print("🌐 Step 1: Contacting live Halo MCC database...")
        # We add a standard browser Header so the request looks completely normal to their backend
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        response = requests.get(API_URL, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # FIX: If the data is a list directly at the root, return it immediately!
            if isinstance(data, list):
                print(f"📊 Successfully fetched raw server list. Found {len(data)} total active matches.")
                return data
                
            # Fallback if it's packed inside a dictionary key
            if isinstance(data, dict):
                return data.get("servers", data.get("lobbies", []))
                
        return []
    except Exception as e:
        print(f"❌ Failed to reach data pipeline: {e}")
        return []

def filter_parkour_only(all_games):
    filtered_list = []
    for game in all_games:
        # Check capitalized data tags used by Halo's engine and fallback to lowercase alternatives
        title = str(game.get("Name", game.get("name", game.get("ServerName", "")))).lower()
        map_name = str(game.get("MapName", game.get("map", ""))).lower()
        mode = str(game.get("GameMode", game.get("gamemode", ""))).lower()
        
        # Also look through custom gameplay tags if they exist in the raw match payload
        tags = [str(t).lower() for t in game.get("Tags", game.get("tags", []))]
        
        # If the word 'parkour' shows up in the title, map name, mode, or tags—we grab it!
        if "parkour" in title or "parkour" in map_name or "parkour" in mode or "parkour" in tags:
            filtered_list.append(game)
            
    print(f"🔍 Filtering Complete: Found {len(filtered_list)} true Parkour matches.")
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

def send_to_discord(lobbies, was_simulated=False):
    delete_previous_ping()
    print("🚀 Step 3: Delivering update package to Discord...")
    
    title_text = "🏃‍♂️ Live Parkour Lobbies Found!"
    desc_text = f"Found **{len(lobbies)}** active parkour server(s) running right now."
    color_code = 5763719 # Bright green color
    
    embed = {
        "title": title_text,
        "description": desc_text,
        "color": color_code,
        "fields": []
    }
    
    for game in lobbies:
        name = game.get("Name", game.get("name", game.get("ServerName", "Unknown Lobby")))
        m_name = game.get("MapName", game.get("map", "Unknown Map"))
        
        # Read player counts based on standard API payloads
        curr_p = game.get("PlayerCount", game.get("current_players", game.get("PlayerCount", "?")))
        max_p = game.get("MaxPlayers", game.get("max_players", game.get("MaxPlayers", "?")))
        players = f"{curr_p}/{max_p}"
        
        embed["fields"].append({
            "name": f"🎮 {name}",
            "value": f"**Map:** {m_name} | **Players:** {players}",
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
        send_to_discord(parkour_matches, was_simulated=False)
    else:
        print("🔍 No parkour lobbies active. Posting status update.")
        delete_previous_ping()
        
        empty_embed = {
            "title": "🏃‍♂️ No Parkour Lobbies",
            "description": "No live parkour lobbies are active at the moment. Checking again in 20 minutes!",
            "color": 16711680 # Red color for empty status
        }
        payload = {"username": "Halo Parkour Tracker", "embeds": [empty_embed]}
        response = requests.post(f"{WEBHOOK_URL}?wait=true", json=payload)
        save_new_ping_id(response)
        
    print("=== SWEEP COMPLETE ===")