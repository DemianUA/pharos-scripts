import asyncio
import random
from decimal import Decimal
from web3 import Web3, HTTPProvider
from eth_account import Account
from config import RPC
from core.auth import get_jwt_token
from core.verify_retry import retry_verify_task

CHAIN_ID = 688688  # Pharos chain ID

def create_web3_with_proxy(proxy: str) -> Web3:
    if proxy:
        provider = HTTPProvider(RPC, request_kwargs={"proxies": {"http": proxy, "https": proxy}})
    else:
        provider = HTTPProvider(RPC)
    return Web3(provider)

async def send_phrs_to_self(private_key: str, proxy: str = None) -> bool:
    try:
        w3 = create_web3_with_proxy(proxy)
        account = Account.from_key(private_key)
        address = account.address

        balance_wei = w3.eth.get_balance(address)
        balance_phrs = Web3.from_wei(balance_wei, 'ether')

        if balance_phrs == 0:
            print(f"[Skip] 🔸 Нульовий баланс PHRS → {address}")
            return False

        percent = random.uniform(0.1, 0.3)
        send_amount = round(balance_phrs * Decimal(percent), 6)
        send_value_wei = Web3.to_wei(send_amount, 'ether')

        nonce = w3.eth.get_transaction_count(address, 'pending')

        tx = {
            'from': address,
            'to': address,
            'value': send_value_wei,
            'gas': 21000,
            'gasPrice': Web3.to_wei('1', 'gwei'),
            'nonce': nonce,
            'chainId': CHAIN_ID
        }

        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        w3.eth.wait_for_transaction_receipt(tx_hash)

        # ✅ Додано verify XP
        jwt = get_jwt_token(private_key, proxy)
        if jwt:
            await retry_verify_task(address, w3.to_hex(tx_hash), jwt, proxy)

        print(f"[Send ✅] {send_amount} PHRS → {address}, TX: {w3.to_hex(tx_hash)}")
        return True

    except Exception as e:
        print(f"[Error ❌] {address} → {str(e)}")
        return False
