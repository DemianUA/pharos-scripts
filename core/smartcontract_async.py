import os
import json
import random
import asyncio
from web3 import Web3, HTTPProvider
from eth_account import Account
from eth_account.signers.local import LocalAccount
from config import RPC, DELAY_BETWEEN_WALLETS, RANDOMIZE_WALLETS_ORDER
from core.account_loader import load_accounts

TO_ADDRESS = "0xFaA3792Ee585E9d4D77A4220daF41D83282e8AaF"
RAW_DATA_TIMER = "0xcc6212f2000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000001ac6080604052348015600f57600080fd5b5061018d8061001f6000396000f3fe608060405234801561001057600080fd5b50600436106100365760003560e01c8063557ed1ba1461003b578063d09de08a14610059575b600080fd5b610043610063565b60405161005091906100d9565b60405180910390f35b61006161006c565b005b60008054905090565b600160008082825461007e9190610123565b925050819055507f3912982a97a34e42bab8ea0e99df061a563ce1fe3333c5e14386fd4c940ef6bc6000546040516100b691906100d9565b60405180910390a1565b6000819050919050565b6100d3816100c0565b82525050565b60006020820190506100ee60008301846100ca565b92915050565b7f4e487b7100000000000000000000000000000000000000000000000000000000600052601160045260246000fd5b600061012e826100c0565b9150610139836100c0565b9250828201905080821115610151576101506100f4565b5b9291505056fea2646970667358221220801aef4e99d827a7630c9f3ce9c8c00d708b58053b756fed98cd9f2f5928d10f64736f6c634300081c00330000000000000000000000000000000000000000"
RAW_VALUE = Web3.to_wei(0.005, "ether")
GAS_LIMIT = 236679
GAS_PRICE = 1200000000
USER_AGENTS_PATH = os.path.join("data", "user_agents.json")

def get_web3_with_proxy(proxy: str, user_agent: str) -> Web3:
    try:
        if proxy.startswith("http://"):
            proxy_url = proxy.strip()
        else:
            host, port, username, password = proxy.strip().split(":")
            proxy_url = f"http://{username}:{password}@{host}:{port}"
        proxies = {"http": proxy_url, "https": proxy_url}
    except Exception:
        proxies = None

    provider = HTTPProvider(
        RPC,
        request_kwargs={
            "proxies": proxies,
            "headers": {"User-Agent": user_agent},
            "timeout": 15
        }
    )
    return Web3(provider)

async def deploy_timer(private_key: str, proxy: str = None):
    with open(USER_AGENTS_PATH, "r") as f:
        user_agents = json.load(f)

    user_agent = user_agents.get(private_key)
    if not user_agent:
        return

    w3 = get_web3_with_proxy(proxy, user_agent)
    account: LocalAccount = Account.from_key(private_key)

    try:
        # БЕРЕМО NONCE З 'pending'
        nonce = w3.eth.get_transaction_count(account.address, 'pending')
        tx = {
            "to": Web3.to_checksum_address(TO_ADDRESS),
            "value": RAW_VALUE,
            "data": RAW_DATA_TIMER,
            "gas": GAS_LIMIT,
            "gasPrice": GAS_PRICE,
            "nonce": nonce,
            "chainId": w3.eth.chain_id
        }

        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        # ЧЕКАЄМО ОБОВʼЯЗКОВО ПІДТВЕРДЖЕННЯ!
        w3.eth.wait_for_transaction_receipt(tx_hash)

        print(f"[Deploy ✅] TX: {w3.to_hex(tx_hash)}")
    except Exception as e:
        print(f"[Error ❌] {account.address} → {e}")


async def deploy_timer_all_wallets():
    accounts = load_accounts()
    if RANDOMIZE_WALLETS_ORDER:
        random.shuffle(accounts)

    for acc in accounts:
        print(f"\n🚀 Деплой смартконтракту: {acc.private_key[:10]}...")
        await deploy_timer(acc.private_key, acc.proxy)
        delay = random.randint(*DELAY_BETWEEN_WALLETS)
        print(f"⏳ Затримка між акаунтами: {delay}с")
        await asyncio.sleep(delay)
