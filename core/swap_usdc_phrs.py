import asyncio
import random
import time
from web3 import Web3, HTTPProvider
from eth_account import Account
from eth_abi import encode
from config import RPC

TOKENS = {
    "PHRS": None,
    "WPHRS": Web3.to_checksum_address("0x76aaada469d23216be5f7c596fa25f282ff9b364"),
    "USDC": Web3.to_checksum_address("0xad902cf99c2de2f1ba5ec4d642fd7e49cae9ee37")
}

ROUTER = Web3.to_checksum_address("0x1a4de519154ae51200b0ad7c90f7fac75547888a")

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
]

ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "collectionAndSelfcalls", "type": "uint256"},
            {"internalType": "bytes[]", "name": "data", "type": "bytes[]"}
        ],
        "name": "multicall",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

def create_web3_with_proxy(proxy: str) -> Web3:
    if proxy:
        provider = HTTPProvider(RPC, request_kwargs={"proxies": {"http": proxy, "https": proxy}})
    else:
        provider = HTTPProvider(RPC)
    return Web3(provider)

def get_balance(w3: Web3, account: Account, token_symbol: str):
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
        w3.eth.wait_for_transaction_receipt(tx_hash)  # чекати receipt!
        print("[Approve] Done")

async def swap_usdc_to_phrs(private_key: str, proxy: str = None):
    try:
        w3 = create_web3_with_proxy(proxy)
        account = Account.from_key(private_key)
        address = account.address

        balance = get_balance(w3, account, "USDC")
        percent = random.uniform(1, 4)
        amount = round((balance / 10**18) * percent / 100, 4)
        amount_wei = int(amount * 10**18)

        if amount_wei == 0:
            msg = f"[Skip] 🔸 Недостатньо USDC для свапу → {address}"
            print(msg)
            return msg

        # 1. Approve USDC
        approve_if_needed(w3, account, TOKENS["USDC"], amount_wei)
        # 2. Оновити nonce після approve
        nonce = w3.eth.get_transaction_count(address, 'pending')

        # 3. Swap USDC → WPHRS через multicall
        router = w3.eth.contract(address=ROUTER, abi=ROUTER_ABI)
        encoded = encode(
            ["address", "address", "uint24", "address", "uint256", "uint256", "uint160"],
            [TOKENS["USDC"], TOKENS["WPHRS"], 500, address, amount_wei, 0, 0]
        )
        payload = b"\x04\xe4\x5a\xaf" + encoded

        tx = router.functions.multicall(int(time.time()), [payload]).build_transaction({
            "from": address,
            "nonce": nonce,
            "gas": 300000,
            "gasPrice": 0
        })
        signed_tx = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        w3.eth.wait_for_transaction_receipt(tx_hash)

        await asyncio.sleep(2)

        # 4. Unwrap WPHRS → PHRS
        unwrap_contract = w3.eth.contract(address=TOKENS["WPHRS"], abi=[{
            "inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}],
            "name": "withdraw",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        }])

        # nonce для unwrap — ще раз оновити
        unwrap_nonce = w3.eth.get_transaction_count(address, 'pending')
        tx2 = unwrap_contract.functions.withdraw(amount_wei).build_transaction({
            "from": address,
            "nonce": unwrap_nonce,
            "gas": 100000,
            "gasPrice": 0
        })
        signed2 = account.sign_transaction(tx2)
        unwrap_hash = w3.eth.send_raw_transaction(signed2.raw_transaction)
        w3.eth.wait_for_transaction_receipt(unwrap_hash)

        print(f"[Swap ✅] USDC → PHRS → {address}, TX: {w3.to_hex(unwrap_hash)}, сума: {amount} USDC")
        return True

    except Exception as e:
        print(f"[Error ❌] {address} → {str(e)}")
        return False
