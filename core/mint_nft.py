# core/mint_nft.py

import random
from web3 import Web3, HTTPProvider
from eth_account import Account
from config import RPC
from core.auth import get_jwt_token
from core.verify_retry import retry_verify_task

CHAIN_ID = 688688
CONTRACT = Web3.to_checksum_address("0x0000000038f050528452D6Da1E7AACFA7B3Ec0a8")
FUNC_SELECTOR = "0x5b70ea9f"  # mint() без параметрів

def create_web3_with_proxy(proxy: str) -> Web3:
    if proxy:
        provider = HTTPProvider(RPC, request_kwargs={"proxies": {"http": proxy, "https": proxy}})
    else:
        provider = HTTPProvider(RPC)
    return Web3(provider)

async def mint_nft(private_key: str, proxy: str = None) -> bool:
    try:
        w3 = create_web3_with_proxy(proxy)
        account = Account.from_key(private_key)
        address = account.address

        nonce = w3.eth.get_transaction_count(address, "pending")

        tx = {
            "from": address,
            "to": CONTRACT,
            "value": 0,
            "gas": 1_000_000,
            "gasPrice": Web3.to_wei("1", "gwei"),
            "nonce": nonce,
            "chainId": CHAIN_ID,
            "data": FUNC_SELECTOR,
        }

        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)  # ✅ саме так!
        w3.eth.wait_for_transaction_receipt(tx_hash)

        print(f"[Mint ✅] NFT → {address}, TX: {w3.to_hex(tx_hash)}")

        jwt = get_jwt_token(private_key, proxy)
        if jwt:
            await retry_verify_task(address, w3.to_hex(tx_hash), jwt, proxy)

        return True

    except Exception as e:
        print(f"[Mint ❌] {address} → {e}")
        return False
