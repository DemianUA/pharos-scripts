# generate_user_agents.py

import os
import json
import random

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIVATE_KEYS_FILE = os.path.join(BASE_DIR, "private_keys.txt")
USER_AGENTS_FILE = os.path.join(BASE_DIR, "data", "user_agents.json")

CHROME_VERSIONS = ["114", "115", "116", "117", "118", "119", "120", "121", "122", "123", "124", "125"]
OS_PLATFORMS = [
    "Windows NT 10.0; Win64; x64",
    "Macintosh; Intel Mac OS X 10_15_7",
    "X11; Linux x86_64"
]

def generate_random_user_agent():
    chrome_version = random.choice(CHROME_VERSIONS)
    platform = random.choice(OS_PLATFORMS)
    return f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version}.0.0.0 Safari/537.36"

def load_existing_user_agents():
    if os.path.exists(USER_AGENTS_FILE):
        with open(USER_AGENTS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_user_agents(data):
    os.makedirs(os.path.dirname(USER_AGENTS_FILE), exist_ok=True)
    with open(USER_AGENTS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def generate_user_agents():
    user_agents = load_existing_user_agents()

    if not os.path.exists(PRIVATE_KEYS_FILE):
        print("❌ private_keys.txt not found!")
        return

    with open(PRIVATE_KEYS_FILE, "r") as f:
        private_keys = [line.strip() for line in f if line.strip()]

    added = 0
    for pk in private_keys:
        if pk not in user_agents:
            user_agents[pk] = generate_random_user_agent()
            added += 1

    save_user_agents(user_agents)

    print(f"✅ Added {added} new user-agents.")
    if added == 0:
        print("ℹ️ All private keys already have a user-agent.")