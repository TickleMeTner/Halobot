import requests

# Your live Discord connection line
WEBHOOK_URL = "https://discordapp.com/api/webhooks/1508269123602350200/CuOF_aExkClX9xqimNwBAkF8aIMqpuE0fYEE8m2EoGwL3jCKJImR5A_y7-_hAys_UwIp"
API_URL = "https://api.jumpnexus.org/v1/mcc/cgb"

# Free cloud key-value store bucket (No account or credit card needed)
# This keeps track of our message ID across GitHub runs without spamming your git history
KV_URL = "https://kvdb.io/Vp4Z97g6E6BvM4s9KzWq3A/last_mcc_ping"

def fetch_live_mcc_data():
    try:
        print("🌐 Step 1: Contacting live Halo MCC database...")
        response = requests.get(API_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("servers", data.get("lobbies", []))
        return []
    except Exception as e:
        print(f"❌ Failed to reach data pipeline: {e}")
        return []

def filter_parkour_only(all_games):
    filtered_list = []
    for game in all_games:
        title = str(game.get("name", game.get("ServerName", ""))).lower()
        map_name = str(game.get("map", game.get("MapName", ""))).lower()
        mode = str(game.get("gamemode", game.get("GameMode", ""))).lower()
        
        if "parkour" in title or "parkour" in map_name or "parkour" in mode:
            filtered_list.append(game)
    return filtered_list

def delete_previous_ping():
    try:
        # Pull the last saved message ID out of the cloud storage bucket
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
            # Save the fresh message ID back to our cloud memory bucket
            requests.put(KV_URL, data=str(new_id), timeout=5)
            print(f"💾 Saved message tracking ID to cloud locker: {new_id}")
        except Exception:
            pass

def send_to_discord(lobbies, was_simulated=False):
    delete_previous_ping()
    print("🚀 Step 3: Delivering update package to Discord...")
    
    title_text = "🏃‍♂️ Live Parkour Lobbies Found!" if not was_simulated else "⚙️ Bot Connection System Test"
    desc_text = f"Found **{len(lobbies)}** parkour server(s) running right now." if not was_simulated else "No live parkour lobbies are online right now, so here is a test format match!"
    color_code = 5763719 if not was_simulated else 3447003 
    
    embed = {
        "title": title_text,
        "description": desc_text,
        "color": color_code,
        "fields": []
    }
    
    for game in lobbies:
        name = game.get("name", game.get("ServerName", "Unknown Lobby"))
        m_name = game.get("map", game.get("MapName", "Unknown Map"))
        players = f"{game.get('current_players', game.get('PlayerCount', '?'))}/{game.get('max_players', game.get('MaxPlayers', '?'))}"
        
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
        # No parkour lobbies found. Update status to notify that the bot is alive.
        print("🔍 No parkour lobbies active. Posting status update.")
        
        # We delete the old message so the new "empty" one is always the latest
        delete_previous_ping()
        
        # Send a "No Lobbies" status update
        empty_embed = {
            "title": "🏃‍♂️ No Parkour Lobbies",
            "description": "No live parkour lobbies are active at the moment. Checking again in 10 minutes!",
            "color": 16711680 # Red color for empty
        }
        payload = {"username": "Halo Parkour Tracker", "embeds": [empty_embed]}
        response = requests.post(f"{WEBHOOK_URL}?wait=true", json=payload)
        save_new_ping_id(response)
        
    print("=== SWEEP COMPLETE ===")