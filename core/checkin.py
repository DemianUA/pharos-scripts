# core/checkin.py

import json
import time
import random
import requests
from eth_account import Account
from web3 import Web3
from eth_account.messages import encode_defunct

from config import DELAY_BETWEEN_WALLETS
from core.account_loader import load_accounts  # повертає список об'єктів з полями: private_key, proxy

headers_template = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.8",
    "authorization": "Bearer null",
    "referer": "https://testnet.pharosnetwork.xyz/",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "sec-ch-ua": '"Chromium";v="136", "Brave";v="136", "Not.A/Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "sec-gpc": "1"
}

# Завантаження user-agents з папки data
with open("data/user_agents.json", "r") as f:
    USER_AGENTS = json.load(f)


def perform_checkin(private_key: str, proxy: str = None) -> bool:
    try:
        account = Account.from_key(private_key)
        address = account.address
        message = "pharos"
        message_encoded = encode_defunct(text=message)
        signed_message = Account.sign_message(message_encoded, private_key).signature.hex()

        headers = headers_template.copy()
        headers["user-agent"] = USER_AGENTS.get(private_key, "Mozilla/5.0")
        proxies = {"http": proxy, "https": proxy} if proxy else None

        login_url = f"https://api.pharosnetwork.xyz/user/login?address={address}&signature={signed_message}&invite_code=S6NGMzXSCDBxhnwo"
        login_response = requests.post(login_url, headers=headers, proxies=proxies)
        login_data = login_response.json()

        if login_data.get("code") != 0 or "jwt" not in login_data.get("data", {}):
            print(f"[Login Failed] {address} → {login_data.get('msg', 'Unknown error')}")
            return False

        jwt = login_data["data"]["jwt"]
        headers["authorization"] = f"Bearer {jwt}"

        checkin_url = f"https://api.pharosnetwork.xyz/sign/in?address={address}"
        checkin_response = requests.post(checkin_url, headers=headers, proxies=proxies)
        checkin_data = checkin_response.json()

        if checkin_data.get("code") == 0:
            print(f"[Check-in ✅] {address}")
            return True
        else:
            print(f"[Check-in ❌] {address} → {checkin_data.get('msg', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"[Error ❌] {private_key[:10]}... → {str(e)}")
        return False


def checkin_all_wallets():
    accounts = load_accounts()
    for acc in accounts:
        perform_checkin(acc.private_key, acc.proxy)
        delay = random.randint(*DELAY_BETWEEN_WALLETS)
        print(f"⏳ Затримка між акаунтами: {delay}с")
        time.sleep(delay)
