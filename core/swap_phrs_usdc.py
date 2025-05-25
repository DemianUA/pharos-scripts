import asyncio
import random
import time
from web3 import Web3, HTTPProvider
from eth_account import Account
from eth_abi import encode
from config import RPC
from core.auth import get_jwt_token
from core.verify import verify_task
from core.verify_retry import retry_verify_task

TOKENS = {
    "PHRS": None,
    "WPHRS": Web3.to_checksum_address("0x76aaada469d23216be5f7c596fa25f282ff9b364"),
    "USDC": Web3.to_checksum_address("0xad902cf99c2de2f1ba5ec4d642fd7e49cae9ee37"),
    "USDT": Web3.to_checksum_address("0x7011b885196af5de63f11e7f5467b929eb675257")
}

ROUTER = Web3.to_checksum_address("0x1a4de519154ae51200b0ad7c90f7fac75547888a")

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
]

ROUTER_ABI = [{
    "inputs": [{"internalType": "uint256", "name": "collectionAndSelfcalls", "type": "uint256"},
               {"internalType": "bytes[]", "name": "data", "type": "bytes[]"}],
    "name": "multicall",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
}]


def create_web3_with_proxy(proxy: str) -> Web3:
    if proxy:
        provider = HTTPProvider(RPC, request_kwargs={"proxies": {"http": proxy, "https": proxy}})
    else:
        provider = HTTPProvider(RPC)
    return Web3(provider)


def get_balance(w3: Web3, account: Account, token_symbol: str):
    if token_symbol == "PHRS":
        return w3.eth.get_balance(account.address)
    contract = w3.eth.contract(address=TOKENS[token_symbol], abi=ERC20_ABI)
    return contract.functions.balanceOf(account.address).call()


def approve_if_needed(w3: Web3, account: Account, token_address: str, amount: int):
    contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    allowance = contract.functions.allowance(account.address, ROUTER).call()
    if allowance < amount:
        tx = contract.functions.approve(ROUTER, 2**256 - 1).build_transaction({
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address, 'pending'),
            "gas": 100000,
            "gasPrice": 0
        })
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        w3.eth.wait_for_transaction_receipt(tx_hash)
        print("[Approve] Done")


async def swap_phrs_to_usdc(private_key: str, proxy: str = None):
    try:
        w3 = create_web3_with_proxy(proxy)
        account = Account.from_key(private_key)
        address = account.address

        native_balance = get_balance(w3, account, "PHRS")
        percent = random.uniform(1, 4)
        raw_amount = (native_balance / 10**18) * percent / 100
        amount_eth = round(max(raw_amount, 0.0001), 4)
        amount_wei = int(amount_eth * 10**18)

        if amount_wei == 0:
            msg = f"[Skip] 🔸 Недостатньо PHRS для свапу → {address}"
            print(msg)
            return msg

        nonce = w3.eth.get_transaction_count(address, 'pending')

        # Wrap PHRS → WPHRS
        wrap_contract = w3.eth.contract(address=TOKENS["WPHRS"], abi=[{
            "inputs": [], "name": "deposit", "outputs": [], "stateMutability": "payable", "type": "function"
        }])
        tx = wrap_contract.functions.deposit().build_transaction({
            "from": address,
            "value": amount_wei,
            "nonce": nonce,
            "gas": 100000,
            "gasPrice": 0
        })
        signed_tx = account.sign_transaction(tx)
        tx_hash_1 = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        w3.eth.wait_for_transaction_receipt(tx_hash_1)
        print(f"[Wrap] PHRS → WPHRS для {address}")
        await asyncio.sleep(3)

        # Approve if needed
        approve_if_needed(w3, account, TOKENS["WPHRS"], amount_wei)

        nonce = w3.eth.get_transaction_count(address, 'pending')

        router = w3.eth.contract(address=ROUTER, abi=ROUTER_ABI)
        encoded = encode(
            ["address", "address", "uint24", "address", "uint256", "uint256", "uint160"],
            [TOKENS["WPHRS"], TOKENS["USDC"], 500, address, amount_wei, 0, 0]
        )
        payload = b"\x04\xe4\x5a\xaf" + encoded

        tx2 = router.functions.multicall(
            int(time.time()), [payload]
        ).build_transaction({
            "from": address,
            "nonce": nonce,
            "gas": 300000,
            "gasPrice": 0
        })
        signed2 = account.sign_transaction(tx2)
        tx_hash_2 = w3.eth.send_raw_transaction(signed2.raw_transaction)
        w3.eth.wait_for_transaction_receipt(tx_hash_2)

        # ✅ verify_task XP
        jwt = get_jwt_token(private_key, proxy)
        if jwt:
            await retry_verify_task(address, w3.to_hex(tx_hash_2), jwt, proxy)

        print(f"[Swap ✅] Виконано свап для {address}, TX: {w3.to_hex(tx_hash_2)}, сума: {amount_eth} PHRS")
        return True

    except Exception as e:
        print(f"[Error ❌] {address} → {str(e)}")
        return False
