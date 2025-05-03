import argparse
import requests
import os
import json
import uuid
import time
from urllib.parse import urlencode, urlparse, parse_qs
from datetime import datetime, UTC
import csv

## FUNCTIONS

# Function - Load Cache
def load_cache(cache_file):
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)
    else:
        return {"characters": [], "ore_type": []}  # Initialize both sections in the cache

# Function - Save Cache
def save_cache(cache, cache_file):
    with open(cache_file, 'w') as f:
        json.dump(cache, f, indent=2)

# Function - Cache Character ID
def get_character_name(character_id, headers, cache_file="cache.json"):
    cache = load_cache(cache_file)
    today = datetime.now(UTC).date()

    # Search for existing character in cache
    for char in cache["characters"]:
        if char["id"] == character_id:
            last_updated = datetime.strptime(char["last_updated"], "%Y-%m-%d").date()
            if (today - last_updated).days < 180:
                return char["name"]
            break  # Found but stale, will update below

    # Query ESI for name
    esi_url = f"{ESI_BASE}/characters/{character_id}/"
    try:
        resp = requests.get(esi_url, headers=headers)
        resp.raise_for_status()
        char_data = resp.json()
        name = char_data["name"]
    except Exception as e:
        print(f"❌ Failed to get name for character {character_id}: {e}")
        return "Unknown"

    # Update cache
    updated = False
    for char in cache["characters"]:
        if char["id"] == character_id:
            char["name"] = name
            char["last_updated"] = today.isoformat()
            updated = True
            break
    if not updated:
        cache["characters"].append({
            "id": character_id,
            "name": name,
            "last_updated": today.isoformat()
        })

    # Write back to cache file immediately
    save_cache(cache, cache_file)

    return name

# Function - Cache Ore Type
def get_ore_name(ore_id, headers, cache_file="cache.json"):
    cache = load_cache(cache_file)
    today = datetime.now(UTC).date()

    # Search for existing ore type in cache
    for ore in cache["ore_type"]:
        if ore["id"] == ore_id:
            last_updated = datetime.strptime(ore["last_updated"], "%Y-%m-%d").date()
            if (today - last_updated).days < 180:
                return ore["name"]
            break  # Found but stale, will update below

    # Query ESI for ore type
    esi_url = f"{ESI_BASE}/universe/types/{ore_id}/"
    try:
        resp = requests.get(esi_url, headers=headers)
        resp.raise_for_status()
        ore_data = resp.json()
        name = ore_data["name"]
    except Exception as e:
        print(f"❌ Failed to get name for ore {ore_id}: {e}")
        return "Unknown"

    # Update cache
    updated = False
    for ore in cache["ore_type"]:
        if ore["id"] == ore_id:
            ore["name"] = name
            ore["last_updated"] = today.isoformat()
            updated = True
            break
    if not updated:
        cache["ore_type"].append({
            "id": ore_id,
            "name": name,
            "last_updated": today.isoformat()
        })

    # Write back to cache file immediately
    save_cache(cache, cache_file)

    return name

# Function - Get Character Name from Cache
def get_character_name_from_cache(character_id, headers, cache_file="cache.json"):
    print(f"Look up Character: {character_id}")
    cache = load_cache(cache_file)
    # Search for the character name in cache
    for char in cache["characters"]:
        if char["id"] == character_id:
            print(f"Character {character_id} found in cache as {char["name"]}")
            return char["name"]
    print(f"Character {character_id} not found in cache - looking up via ESI")
    return get_character_name(character_id, headers)

# Function - Get Ore Name from Cache
def get_ore_name_from_cache(type_id, headers, cache_file="cache.json"):
    print(f"Look up Ore: {type_id}")
    cache = load_cache(cache_file)
    # Search for the ore name in cache
    for ore in cache.get("ore_type", []):
        if ore["id"] == type_id:
            print(f"Ore {type_id} found in cache as {ore["name"]}")
            return ore["name"]
    print(f"Ore {type_id} not found in cache - looking up via ESI")
    return get_ore_name(type_id, headers)


## MAIN CODE

# Directories
script_dir = os.path.dirname(os.path.abspath(__file__))
refresh_token_path = os.path.join(script_dir, "refresh_token.txt")

# Constants
ESI_BASE = "https://esi.evetech.net/latest"
SSO_BASE = "https://login.eveonline.com/v2"
SCOPES = "esi-industry.read_corporation_mining.v1"
REDIRECT_URI = "eveauth-minerhelper://callback"
CACHE_PATH = os.path.join(script_dir, "cache.json")
CACHE_EXPIRY_DAYS = 14
state = str(uuid.uuid4())

# Args
parser = argparse.ArgumentParser()
parser.add_argument('--client_file', required=True, help='Path to JSON file with client_id and client_secret')
args = parser.parse_args()

# Load client info
with open(args.client_file) as f:
    creds = json.load(f)
client_id = creds["client_id"]
client_secret = creds["client_secret"]

# Load or request refresh token
refresh_token = ""
if os.path.exists(refresh_token_path):
    with open(refresh_token_path, 'r') as f:
        refresh_token = f.read().strip()

if not refresh_token:
    print("No refresh token found.")
    user_input = input("Paste your EVE Online Refresh Token here (leave blank if you don't have one): ").strip()
    print("-------------------------")
    if not user_input:
        print("Please authorize the app using the URL below:")
        auth_url = f"{SSO_BASE}/oauth/authorize?" + urlencode({
            'response_type': 'code',
            'redirect_uri': REDIRECT_URI,
            'client_id': client_id,
            'scope': SCOPES,
            'state': state
        })
        print(auth_url)
        print("\n🔗 Open this URL in your browser to log into EVE Online.")
        print("Once logged in, the browser will attempt to open a URL that looks like this:")
        print(f"   {REDIRECT_URI}?code=XXXXX&state=YYYYY")
        print("\n📋 To capture the URL, follow these steps in Chrome:")
        print("  1. Press F12 to open Developer Tools.")
        print("  2. Go to the 'Network' tab.")
        print("  3. Look for a request that includes your redirect URL (usually a 302 response).")
        print("  4. Click the request, and in the 'Headers' section, you will see the full redirected URL.")
        print("  5. Copy the full URL and paste it below.")
        
        redirected_url = input("Paste the full redirected URL here: ").strip()
        print("-------------------------")
        parsed = urlparse(redirected_url)
        query_params = parse_qs(parsed.query)
        code = query_params.get("code", [None])[0]

        if not code:
            print("❌ Could not find `code` in the URL. Try again.")
            exit(1)

        # Exchange code for tokens
        auth = (client_id, client_secret)
        try:
            token_resp = requests.post(
                f"{SSO_BASE}/oauth/token",
                auth=auth,
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': REDIRECT_URI
                }
            )
            token_resp.raise_for_status()
            token_resp = token_resp.json()
        except Exception as e:
            print("❌ Failed to exchange authorization code for token.")
            print("Error:", e)
            print("Response:", token_resp.text if 'token_resp' in locals() else "No response")
            exit(1)
    else:
        refresh_token = user_input
        token_resp = {}

# Refresh token flow
if refresh_token:
    auth = (client_id, client_secret)
    try:
        token_resp = requests.post(
            f"{SSO_BASE}/oauth/token",
            auth=auth,
            data={'grant_type': 'refresh_token', 'refresh_token': refresh_token}
        )
        token_resp.raise_for_status()
        token_resp = token_resp.json()
    except Exception as e:
        print("❌ Failed to refresh access token.")
        print("Error:", e)
        print("Response:", token_resp.text if 'token_resp' in locals() else "No response")
        exit(1)

access_token = token_resp.get("access_token")
refresh_token = token_resp.get("refresh_token")

if not access_token:
    print("❌ Failed to get access token from token response.")
    print("Response JSON:", json.dumps(token_resp, indent=4))
    exit(1)

print(f"\n✅ Access Token: {access_token}")
print(f"🔁 Refresh Token: {refresh_token}")
print("-------------------------")

# Save refresh token
with open(refresh_token_path, 'w') as f:
    f.write(refresh_token)

# Headers
headers = {
    "Authorization": f"Bearer {access_token}"
}

# Get character ID
try:
    whoami = requests.get("https://login.eveonline.com/oauth/verify", headers=headers)
    time.sleep(0.34)  # Limit of 3 requests/sec
    whoami.raise_for_status()
    whoami = whoami.json()
except Exception as e:
    print("❌ Failed to verify access token.")
    print("Error:", e)
    print("Response:", whoami.text if 'whoami' in locals() else "No response")
    exit(1)

char_id = whoami.get("CharacterID")
char_name = whoami.get("CharacterName")

print(f"\n🧑 Authenticated as {char_name} (ID: {char_id})")
print("-------------------------")

# Get corp ID
char_info = requests.get(f"{ESI_BASE}/characters/{char_id}/", headers=headers).json()
corp_id = char_info.get("corporation_id")
time.sleep(0.34)  # Limit of 3 requests/sec

# Dummy check
test_url = f"{ESI_BASE}/corporation/{corp_id}/mining/observers/"
test_resp = requests.get(test_url, headers=headers)
time.sleep(0.34)  # Limit of 3 requests/sec

if test_resp.status_code != 200:
    if test_resp.status_code in [403, 404]:
        print("❌ Access denied or data not found. Make sure you're a corp director and mining data exists.")
    else:
        print("❌ Failed to verify API access. Make sure you're a director in the corp.")
    print(test_resp.text)
    exit(1)

print("✅ API access verified.\n")
print("-------------------------")

# Get date inputs
from_date = input("Enter FROM date (YYYY-MM-DD): ").strip()
to_date = input("Enter TO date (YYYY-MM-DD): ").strip()
print("-------------------------")

# Validate dates
try:
    from_dt = datetime.strptime(from_date, "%Y-%m-%d").date()
    to_dt = datetime.strptime(to_date, "%Y-%m-%d").date()
except ValueError:
    print("❌ Invalid date format.")
    exit(1)

# Get observers - documentation here: https://esi.evetech.net/ui/#/Industry
observers = requests.get(test_url, headers=headers).json()
time.sleep(0.34)  # Limit of 3 requests/sec

# All valid entries go here
all_entries = []

# Step 1: Fetch and accumulate paginated results for each observer (Athanor/Tatara)
for obs in observers:
    observer_id = obs['observer_id']
    print(f"DEBUG - Reading data from Observer {observer_id}")
    page = 1
    while True:
        obs_url = f"{ESI_BASE}/corporation/{corp_id}/mining/observers/{observer_id}/"
        params = {
            "page": page,
            "datasource": "tranquility"
        }
        resp = requests.get(obs_url, headers=headers, params=params)
        time.sleep(0.34)  # Limit of 3 requests/sec

        if resp.status_code == 500 and "Requested page does not exist" in resp.text:
            # Treat this as a 404 - CCP seems to throw this for some reason when there are no more pages of data for a particular observer
            break
        elif resp.status_code != 200:
            print(f"ERROR {resp.status_code} on observer {observer_id}, page {page}")
            print(f"{resp.text}")
            break

        entries = resp.json()
        if not entries:
            break

        all_entries.extend(entries)
        page += 1

# Step 2: Filter entries based on last_updated (Only count the ores mined by characters during the specified time period)
filtered_entries = []
for entry in all_entries:
    last_updated = datetime.strptime(entry['last_updated'], "%Y-%m-%d").date()
    if from_dt <= last_updated <= to_dt:
        filtered_entries.append(entry)

# Step 3: Aggregate quantity by character name and ore name
aggregated = {}
for entry in filtered_entries:
    # Get character and ore names from cache
    character_name = get_character_name_from_cache(entry['character_id'], headers)
    ore_name = get_ore_name_from_cache(entry['type_id'], headers)

    if character_name and ore_name:
        # Use character name and ore name as the key in aggregation
        key = (character_name, ore_name)
        aggregated[key] = aggregated.get(key, 0) + entry['quantity']
    else:
        if not character_name:
            print(f"❌ Character ID {entry['character_id']} not found in cache")
        if not ore_name:
            print(f"❌ Ore type ID {entry['type_id']} not found in cache")

# Output results
print(aggregated)

with open(f"eve_mining_{to_date}_{from_date}", "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Character", "Ore Type", "Amount"])

    for (character, ore), amount in sorted(aggregated.items(), key=lambda x: (x[0][0], x[0][1])):
        writer.writerow([character, ore, amount])

# Format and output
#output = [{"pilot_name": p, "mined_ores": ores} for p, ores in pilot_data.items()]
#filename = f"eve_mining_report_{to_date}_{from_date}.json"
#filepath = os.path.join(script_dir, filename)

#with open(filepath, 'w') as f:
#    json.dump(output, f, indent=4)

#print("\n📄 Report saved to:", filename)
#print("\n📊 Report contents:\n")
#print(json.dumps(output, indent=4))
#print("-------------------------")

input("\n✅ Done! Press Enter to close this window.")
