import asyncio
import random
import time
from web3 import Web3, HTTPProvider
from eth_account import Account
from eth_abi import encode
from config import RPC
from core.auth import get_jwt_token
from core.verify_retry import retry_verify_task

USDC = Web3.to_checksum_address("0xad902cf99c2de2f1ba5ec4d642fd7e49cae9ee37")
WPHRS = Web3.to_checksum_address("0x76aaada469d23216be5f7c596fa25f282ff9b364")
ROUTER = Web3.to_checksum_address("0xF8a1D4FF0f9b9Af7CE58E1fc1833688F3BFd6115")
POOL_PHRS_USDC = Web3.to_checksum_address("0xfe96fada81f089a4ca14550d89637a12bd8210e7")
FEE_TIER = 3000

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
]

ROUTER_ABI = [{
    "inputs": [{"internalType": "bytes[]", "name": "data", "type": "bytes[]"}],
    "name": "multicall",
    "outputs": [],
    "stateMutability": "payable",
    "type": "function"
}]

def create_web3_with_proxy(proxy: str) -> Web3:
    provider = HTTPProvider(RPC, request_kwargs={"proxies": {"http": proxy, "https": proxy}}) if proxy else HTTPProvider(RPC)
    return Web3(provider)

async def get_phrs_usdc_price_and_tick(w3: Web3):
    abi = [{"inputs": [], "name": "slot0", "outputs": [{"name": "sqrtPriceX96", "type": "uint160"}, {"name": "tick", "type": "int24"}], "stateMutability": "view", "type": "function"}]
    contract = w3.eth.contract(address=POOL_PHRS_USDC, abi=abi)
    sqrt_price_x96, tick = await asyncio.to_thread(contract.functions.slot0().call)
    price = (sqrt_price_x96 / 2 ** 96) ** 2
    return price, tick

async def approve_if_needed(w3: Web3, account: Account, token_address: str, amount: int):
    contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    allowance = await asyncio.to_thread(contract.functions.allowance(account.address, ROUTER).call)
    if allowance < amount:
        tx = contract.functions.approve(ROUTER, 2**256 - 1).build_transaction({
            "from": account.address,
            "nonce": await asyncio.to_thread(w3.eth.get_transaction_count, account.address, 'pending'),
            "gas": 100000,
            "gasPrice": Web3.to_wei("1", "gwei")
        })
        signed_tx = account.sign_transaction(tx)
        tx_hash = await asyncio.to_thread(w3.eth.send_raw_transaction, signed_tx.raw_transaction)
        await asyncio.to_thread(w3.eth.wait_for_transaction_receipt, tx_hash)
        print("[Approve ✅]")

async def add_liquidity_phrs_usdc(private_key: str, proxy: str):
    w3 = create_web3_with_proxy(proxy)
    account = Account.from_key(private_key)
    address = account.address

    balance_wei = await asyncio.to_thread(w3.eth.get_balance, address)
    balance_phrs = balance_wei / 10 ** 18
    if balance_wei == 0:
        return "[Skip] Баланс PHRS нульовий"

    percent = random.uniform(3, 10)
    amount_phrs = round(balance_phrs * percent / 100, 6)
    amount_wei = int(amount_phrs * 10 ** 18)

    if amount_wei == 0:
        return "[Skip] Замала сума для ліквідності"

    price, current_tick = await get_phrs_usdc_price_and_tick(w3)
    amount_usdc = amount_phrs * price
    amount_usdc_wei = int(amount_usdc * 10 ** 18)

    usdc_contract = w3.eth.contract(address=USDC, abi=ERC20_ABI)
    usdc_balance_wei = await asyncio.to_thread(usdc_contract.functions.balanceOf(address).call)
    usdc_balance = usdc_balance_wei / 10 ** 18

    print(f"Гаманець: {address}")

    if usdc_balance_wei < amount_usdc_wei:
        return "[Skip] Недостатньо USDC"

    # 🟢 Wrap PHRS → WPHRS
    tx = w3.eth.contract(address=WPHRS, abi=[{
        "name": "deposit",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
        "inputs": []
    }]).functions.deposit().build_transaction({
        "from": address,
        "value": amount_wei,
        "nonce": await asyncio.to_thread(w3.eth.get_transaction_count, address, 'pending'),
        "gas": 100000,
        "gasPrice": Web3.to_wei("1", "gwei")
    })
    signed = account.sign_transaction(tx)
    tx_hash_wrap = await asyncio.to_thread(w3.eth.send_raw_transaction, signed.raw_transaction)
    await asyncio.to_thread(w3.eth.wait_for_transaction_receipt, tx_hash_wrap)

    # ✅ Approve USDC
    await approve_if_needed(w3, account, USDC, amount_usdc_wei)
    nonce_after_approve = await asyncio.to_thread(w3.eth.get_transaction_count, address, 'pending')

    TICK_SPACING = 60
    tick_lower = ((current_tick - 9600) // TICK_SPACING) * TICK_SPACING
    tick_upper = ((current_tick + 9600) // TICK_SPACING) * TICK_SPACING

    encoded_mint = encode([
        "address", "address", "uint24", "int24", "int24",
        "uint256", "uint256", "uint256", "uint256", "address", "uint256"
    ], [
        WPHRS, USDC, FEE_TIER,
        tick_lower, tick_upper,
        amount_wei, amount_usdc_wei, 0, 0,
        address, int(time.time()) + 600
    ])
    payload = b"\x88\x31\x64\x56" + encoded_mint

    router = w3.eth.contract(address=ROUTER, abi=ROUTER_ABI)
    tx2 = router.functions.multicall([payload]).build_transaction({
        "from": address,
        "nonce": nonce_after_approve,
        "gas": 600000,
        "gasPrice": Web3.to_wei("1", "gwei"),
        "value": 0
    })
    signed2 = account.sign_transaction(tx2)
    tx_hash = await asyncio.to_thread(w3.eth.send_raw_transaction, signed2.raw_transaction)
    await asyncio.to_thread(w3.eth.wait_for_transaction_receipt, tx_hash)

    # ✅ VERIFY XP
    jwt = get_jwt_token(private_key, proxy)
    if jwt:
        await retry_verify_task(address, w3.to_hex(tx_hash), jwt, proxy)

    return f"[Liquidity ✅] {amount_phrs} WPHRS + {amount_usdc:.4f} USDC додано в пул. TX: {w3.to_hex(tx_hash)}"
