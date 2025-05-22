# faucet.py (оновлений)

import requests
import json
from eth_account import Account
from eth_account.messages import encode_defunct


def claim_faucet(private_key, proxy, user_agent):
    address = Account.from_key(private_key).address
    print(f"\n✨ Claiming faucet for {address}")

    message = encode_defunct(text="pharos")
    signed_message = Account.sign_message(message, private_key)
    signature = signed_message.signature.hex()

    headers = {
        "accept": "application/json, text/plain, */*",
        "user-agent": user_agent,
        "referer": "https://testnet.pharosnetwork.xyz/",
        "authorization": "Bearer null"
    }

    session = requests.Session()
    if proxy and proxy.count(':') == 3:
        host, port, user, pwd = proxy.split(':')
        proxy_url = f"http://{user}:{pwd}@{host}:{port}"
        session.proxies = {"http": proxy_url, "https": proxy_url}
    else:
        session.proxies = {"http": proxy, "https": proxy}

    login_url = f"https://api.pharosnetwork.xyz/user/login?address={address}&signature={signature}"
    r = session.post(login_url, headers=headers)
    res = r.json()
    if res.get("code") != 0 or "jwt" not in res.get("data", {}):
        print("[!] Login failed", res)
        return False

    jwt = res["data"]["jwt"]
    headers["authorization"] = f"Bearer {jwt}"

    status_url = f"https://api.pharosnetwork.xyz/faucet/status?address={address}"
    r = session.get(status_url, headers=headers)
    res = r.json()
    if not res.get("data", {}).get("is_able_to_faucet"):
        print("[!] Faucet not available yet")
        return False

    claim_url = f"https://api.pharosnetwork.xyz/faucet/daily?address={address}"
    r = session.post(claim_url, headers=headers)
    res = r.json()
    if res.get("code") == 0:
        print("[+] Faucet claimed successfully!")
        return True
    else:
        print("[!] Faucet claim failed", res)
        return False


def can_claim_today(private_key, proxy, user_agent):
    address = Account.from_key(private_key).address
    message = encode_defunct(text="pharos")
    signed_message = Account.sign_message(message, private_key)
    signature = signed_message.signature.hex()

    headers = {
        "user-agent": user_agent,
        "referer": "https://testnet.pharosnetwork.xyz/",
        "accept": "application/json, text/plain, */*",
        "authorization": "Bearer null"
    }

    session = requests.Session()
    if proxy and proxy.count(':') == 3:
        host, port, user, pwd = proxy.split(':')
        proxy_url = f"http://{user}:{pwd}@{host}:{port}"
        session.proxies = {"http": proxy_url, "https": proxy_url}
    else:
        session.proxies = {"http": proxy, "https": proxy}

    try:
        login_url = f"https://api.pharosnetwork.xyz/user/login?address={address}&signature={signature}"
        r = session.post(login_url, headers=headers)
        res = r.json()
        if res.get("code") != 0 or "jwt" not in res.get("data", {}):
            print(f"[!] Login failed in status check: {res}")
            return False

        jwt = res["data"]["jwt"]
        headers["authorization"] = f"Bearer {jwt}"

        status_url = f"https://api.pharosnetwork.xyz/faucet/status?address={address}"
        r = session.get(status_url, headers=headers)
        res = r.json()

        return res.get("data", {}).get("is_able_to_faucet", False)

    except Exception as e:
        print(f"[!] Неможливо перевірити статус faucet: {e}")
        return False


# нова функція для запуску з main.py

def run_faucet_all_wallets():
    from config import RETRIES_PER_ACTION, DELAY_BETWEEN_RETRIES, DELAY_BETWEEN_WALLETS, RANDOMIZE_WALLETS_ORDER
    import json, random, time

    with open("private_keys.txt", "r") as f:
        private_keys = [line.strip() for line in f if line.strip()]

    with open("proxies.txt", "r") as f:
        proxies = [line.strip() for line in f if line.strip()]

    with open("data/user_agents.json", "r") as f:
        user_agents = json.load(f)

    combined = list(zip(private_keys, proxies))
    if RANDOMIZE_WALLETS_ORDER:
        random.shuffle(combined)

    for i, (private_key, proxy) in enumerate(combined):
        user_agent = user_agents.get(private_key)
        if not user_agent:
            print(f"[!] User-Agent not found for {private_key}")
            continue

        wallet_address = Account.from_key(private_key).address
        print(f"\n🧾 Обробка акаунта: {wallet_address}")

        if not can_claim_today(private_key, proxy, user_agent):
            print("[🔒] Сьогодні вже забрано або faucet неактивний")
            continue

        for attempt in range(1, RETRIES_PER_ACTION + 1):
            print(f"🔁 Спроба #{attempt}")
            if claim_faucet(private_key, proxy, user_agent):
                break
            delay_retry = random.randint(*DELAY_BETWEEN_RETRIES)
            print(f"⏳ Повтор через: {delay_retry}с")
            time.sleep(delay_retry)

        delay_next = random.randint(*DELAY_BETWEEN_WALLETS)
        print(f"⏭️ Затримка перед наступним акаунтом: {delay_next}с")
        time.sleep(delay_next)
