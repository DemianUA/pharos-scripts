import json
import random
import time
from decimal import Decimal
from web3 import Web3, HTTPProvider
from eth_account import Account
from eth_abi import encode
from config import RPC
import asyncio

ROUTER = Web3.to_checksum_address("0xF8a1D4FF0f9b9Af7CE58E1fc1833688F3BFd6115")
USDC = Web3.to_checksum_address("0xad902cf99c2de2f1ba5ec4d642fd7e49cae9ee37")
WPHRS = Web3.to_checksum_address("0x76aaada469d23216be5f7c596fa25f282ff9b364")
POOL_PHRS_USDC = Web3.to_checksum_address("0xfe96fada81f089a4ca14550d89637a12bd8210e7")
FEE_TIER = 3000

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
]

ROUTER_ABI = [
    {
        "inputs": [{"internalType": "bytes[]", "name": "data", "type": "bytes[]"}],
        "name": "multicall",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    }
]

POOL_ABI = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"internalType": "int24", "name": "tick", "type": "int24"},
            {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
            {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
            {"internalType": "bool", "name": "unlocked", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

def create_web3_with_proxy(proxy: str) -> Web3:
    if proxy:
        provider = HTTPProvider(RPC, request_kwargs={"proxies": {"http": proxy, "https": proxy}})
    else:
        provider = HTTPProvider(RPC)
    return Web3(provider)

async def approve_if_needed(w3: Web3, account: Account, token: str, amount: int):
    contract = w3.eth.contract(address=token, abi=ERC20_ABI)
    allowance = await asyncio.to_thread(contract.functions.allowance(account.address, ROUTER).call)
    if allowance < amount:
        tx = contract.functions.approve(ROUTER, 2**256 - 1).build_transaction({
            "from": account.address,
            "nonce": await asyncio.to_thread(w3.eth.get_transaction_count, account.address, 'pending'),
            "gas": 100000,
            "gasPrice": 0
        })
        signed = account.sign_transaction(tx)
        tx_hash = await asyncio.to_thread(w3.eth.send_raw_transaction, signed.raw_transaction)
        await asyncio.to_thread(w3.eth.wait_for_transaction_receipt, tx_hash)
        print("[Approve] Done")

async def get_phrs_usdc_price_and_tick(w3: Web3):
    pool = w3.eth.contract(address=POOL_PHRS_USDC, abi=POOL_ABI)
    slot0 = await asyncio.to_thread(pool.functions.slot0().call)
    sqrtPriceX96 = slot0[0]
    tick = slot0[1]
    price = (sqrtPriceX96 ** 2) / (2 ** 192)
    return Decimal(str(price)), tick

async def add_liquidity_phrs_usdc(private_key: str, proxy: str):
    w3 = create_web3_with_proxy(proxy)
    account = Account.from_key(private_key)
    address = account.address

    balance_wei = await asyncio.to_thread(w3.eth.get_balance, address)
    balance_phrs = Web3.from_wei(balance_wei, 'ether')
    if balance_wei == 0:
        return "[Skip] Баланс PHRS нульовий"

    percent = random.uniform(2, 5)
    amount_phrs = round(balance_phrs * Decimal(percent / 100), 6)
    amount_wei = Web3.to_wei(amount_phrs, 'ether')

    if amount_wei == 0:
        return "[Skip] Замала сума для ліквідності"

    price, current_tick = await get_phrs_usdc_price_and_tick(w3)
    amount_usdc = amount_phrs * price
    amount_usdc_wei = int(amount_usdc * 10**18)

    usdc_contract = w3.eth.contract(address=USDC, abi=ERC20_ABI)
    usdc_balance_wei = await asyncio.to_thread(usdc_contract.functions.balanceOf(address).call)
    usdc_balance = usdc_balance_wei / 10 ** 18

    print(f"Гаманець: {address}")

    if usdc_balance_wei < amount_usdc_wei:
        return "[Skip] Недостатньо USDC"

    # NONCE завжди 'pending' для wrap!
    tx = w3.eth.contract(address=WPHRS, abi=[{"name": "deposit", "outputs": [], "stateMutability": "payable", "type": "function", "inputs": []}]) \
        .functions.deposit().build_transaction({
            "from": address,
            "value": amount_wei,
            "nonce": await asyncio.to_thread(w3.eth.get_transaction_count, address, 'pending'),
            "gas": 100000,
            "gasPrice": 0
        })
    signed = account.sign_transaction(tx)
    tx_hash_wrap = await asyncio.to_thread(w3.eth.send_raw_transaction, signed.raw_transaction)
    await asyncio.to_thread(w3.eth.wait_for_transaction_receipt, tx_hash_wrap)

    # Approve USDC
    await approve_if_needed(w3, account, USDC, amount_usdc_wei)
    # NONCE ще раз після approve
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
        "nonce": nonce_after_approve,  # після approve — nonce ще раз!
        "gas": 600000,
        "gasPrice": 0,
        "value": 0
    })
    signed2 = account.sign_transaction(tx2)
    tx_hash = await asyncio.to_thread(w3.eth.send_raw_transaction, signed2.raw_transaction)
    await asyncio.to_thread(w3.eth.wait_for_transaction_receipt, tx_hash)

    return f"[Liquidity ✅] {amount_phrs} WPHRS + {amount_usdc:.4f} USDC додано в пул. TX: {w3.to_hex(tx_hash)}"
