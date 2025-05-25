import json
import os
import requests
from eth_account import Account
from web3 import Web3, HTTPProvider
from config import RPC
from time import sleep
import random
from core.auth import get_jwt_token
from core.account_loader import load_proxies

USDC = Web3.to_checksum_address("0xad902cf99c2de2f1ba5ec4d642fd7e49cae9ee37")
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
]

def create_web3_with_proxy(proxy: str) -> Web3:
    kwargs = {"timeout": 15}
    if proxy:
        kwargs["proxies"] = {"http": proxy, "https": proxy}
    return Web3(HTTPProvider(RPC, request_kwargs=kwargs))

def collect_stats():
    print("🔄 Обробка даних...")

    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    with open(os.path.join(BASE_DIR, "private_keys.txt"), "r") as f:
        private_keys = [line.strip() for line in f if line.strip()]

    proxies = load_proxies()

    with open(os.path.join(BASE_DIR, "data", "user_agents.json"), "r") as f:
        user_agents = json.load(f)

    output_path = os.path.join(BASE_DIR, "data", "stats.txt")

    with open(output_path, "w", encoding="utf-8") as out:
        out.write(f"{'Гаманець':<44} | {'PHRS':>10} | {'USDC':>10} | {'Tx':>5} | {'XP':>8}\n")
        out.write(f"{'-'*44} | {'-'*10} | {'-'*10} | {'-'*5} | {'-'*8}\n")

        for i, private_key in enumerate(private_keys):
            try:
                account = Account.from_key(private_key)
                address = Web3.to_checksum_address(account.address)
                proxy = proxies[i] if i < len(proxies) else None
                user_agent = user_agents.get(private_key)

                if not user_agent:
                    out.write(f"{address:<44} | {'[Немає UA]':>10} | {'-':>10} | {'-':>5} | {'-':>8}\n")
                    continue

                w3 = create_web3_with_proxy(proxy)

                balance_wei = w3.eth.get_balance(address)
                balance_phrs = balance_wei / 10 ** 18

                usdc_contract = w3.eth.contract(address=USDC, abi=ERC20_ABI)
                balance_usdc_wei = usdc_contract.functions.balanceOf(address).call()
                balance_usdc = balance_usdc_wei / 10 ** 18

                tx_count = w3.eth.get_transaction_count(address)

                jwt = get_jwt_token(private_key, proxy, user_agent)
                total_points = "-"

                if jwt:
                    try:
                        headers = {
                            "authorization": f"Bearer {jwt}",
                            "user-agent": user_agent or "Mozilla/5.0",
                            "referer": "https://testnet.pharosnetwork.xyz/experience"
                        }
                        url = f"https://api.pharosnetwork.xyz/user/profile?address={address}"
                        proxy_dict = {"http": proxy, "https": proxy} if proxy else None

                        response = requests.get(url, headers=headers, proxies=proxy_dict, timeout=15)
                        data = response.json()
                        if data.get("code") == 0:
                            info = data["data"]["user_info"]
                            total_points = info.get("TotalPoints", "-")
                    except Exception as e:
                        print(f"[⚠️] Не вдалося отримати XP для {address}: {e}")

                out.write(f"{address:<44} | {balance_phrs:>10.4f} | {balance_usdc:>10.4f} | {tx_count:>5} | {total_points:>8}\n")
                sleep(random.uniform(1, 2))

            except Exception as e:
                out.write(f"{address:<44} | {'[X]':>10} | {'[X]':>10} | {'ERR':>5} | {'-':>8}\n")

    print("✅ Статистика збережена в data/stats.txt")
