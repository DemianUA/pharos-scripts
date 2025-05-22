import json
import os
from eth_account import Account
from web3 import Web3, HTTPProvider
from config import RPC
from time import sleep
import random

USDC = Web3.to_checksum_address("0xad902cf99c2de2f1ba5ec4d642fd7e49cae9ee37")
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
]

def create_web3_with_proxy(proxy: str) -> Web3:
    if proxy and proxy.count(':') == 3:
        host, port, user, pwd = proxy.split(':')
        proxy_url = f"http://{user}:{pwd}@{host}:{port}"
        provider = HTTPProvider(RPC, request_kwargs={"proxies": {"http": proxy_url, "https": proxy_url}})
    elif proxy:
        provider = HTTPProvider(RPC, request_kwargs={"proxies": {"http": proxy, "https": proxy}})
    else:
        provider = HTTPProvider(RPC)
    return Web3(provider)

def collect_stats():
    print("🔄 Обробка даних...")

    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    with open(os.path.join(BASE_DIR, "private_keys.txt"), "r") as f:
        private_keys = [line.strip() for line in f if line.strip()]

    with open(os.path.join(BASE_DIR, "proxies.txt"), "r") as f:
        proxies = [line.strip() for line in f if line.strip()]

    with open(os.path.join(BASE_DIR, "data", "user_agents.json"), "r") as f:
        user_agents = json.load(f)

    output_path = os.path.join(BASE_DIR, "data", "stats.txt")

    with open(output_path, "w", encoding="utf-8") as out:
        # Шапка таблиці (додаємо USDC)
        out.write(f"{'Гаманець':<44} | {'Баланс PHRS':>14} | {'Баланс USDC':>14} | {'Tx Count':>10}\n")
        out.write(f"{'-' * 44} | {'-' * 14} | {'-' * 14} | {'-' * 10}\n")

        for i, private_key in enumerate(private_keys):
            try:
                account = Account.from_key(private_key)
                address = Web3.to_checksum_address(account.address)
                proxy = proxies[i] if i < len(proxies) else None
                user_agent = user_agents.get(private_key)

                if not user_agent:
                    out.write(f"{address:<44} | {'[Немає UA]':>14} | {'-':>14} | {'-':>10}\n")
                    continue

                w3 = create_web3_with_proxy(proxy)

                # Баланс PHRS
                balance_wei = w3.eth.get_balance(address)
                balance_phrs = balance_wei / 10 ** 18

                # Баланс USDC (ERC20)
                usdc_contract = w3.eth.contract(address=USDC, abi=ERC20_ABI)
                balance_usdc_wei = usdc_contract.functions.balanceOf(address).call()
                balance_usdc = balance_usdc_wei / 10 ** 18

                tx_count = w3.eth.get_transaction_count(address)

                out.write(f"{address:<44} | {balance_phrs:>14.6f} | {balance_usdc:>14.6f} | {tx_count:>10}\n")
                sleep(random.uniform(1, 2))

            except Exception as e:
                out.write(f"{address:<44} | {'[❌]':>14} | {'[❌]':>14} | {'ERROR':>10}\n")

    print("✅ Статистика збережена в data/stats.txt")
