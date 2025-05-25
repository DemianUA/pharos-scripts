import os
import json
import random
import asyncio
from datetime import datetime
from config import (
    ALL_IN_SETTINGS,
    DELAY_BETWEEN_ACTIONS,
    DELAY_BETWEEN_WALLETS,
)

from core.swap_phrs_usdc import swap_phrs_to_usdc
from core.swap_usdc_phrs import swap_usdc_to_phrs
from core.send_tokens_async import send_phrs_to_self
from core.liquidity_async import add_liquidity_phrs_usdc
from core.smartcontract_async import deploy_timer
from core.checkin import perform_checkin

STATS_PATH = "data/all_in_stats.json"

def load_all_in_stats():
    if not os.path.exists(STATS_PATH):
        return {}
    with open(STATS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_all_in_stats(stats):
    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

def reset_stats_if_new_day(stats):
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in stats:
        return {today: {}}
    return stats

def get_wallet_key(acc):
    if hasattr(acc, "address"):
        return str(acc.address)
    if hasattr(acc, "wallet_address"):
        return str(acc.wallet_address)
    if hasattr(acc, "private_key"):
        return str(acc.private_key)[:16]
    return str(acc)

# Ліміти - завжди максимум із конфігу (без рандомізації!)
def get_limits_for_account():
    limits = {}
    for k, v in ALL_IN_SETTINGS.items():
        if k == "checkin":
            if v:         # <-- якщо в конфігу checkin: False, тоді не додає!
                limits[k] = True
        else:
            limits[k] = v[1]
    return limits

def get_remaining_actions(wallet_key, stats, today, limits):
    actions_plan = []
    wallet_stats = stats.get(today, {}).get(wallet_key, {})
    for action, max_count in limits.items():
        if action == "checkin":
            if not wallet_stats.get(action, False):
                actions_plan.append(action)
        else:
            done = wallet_stats.get(action, 0)
            left = max_count - done
            if left > 0:
                actions_plan.extend([action]*left)
    random.shuffle(actions_plan)
    return actions_plan

# Реальні асинхронні функції під Pharos
ACTION_FUNCS = {
    "swap_phrs_to_usdc": swap_phrs_to_usdc,
    "swap_usdc_to_phrs": swap_usdc_to_phrs,
    "send_to_self": send_phrs_to_self,
    "add_liquidity": add_liquidity_phrs_usdc,
    "deploy_contract": deploy_timer,
    "checkin": perform_checkin,
}

async def run_actions_for_wallet(acc, actions_plan, stats, date_key):
    wallet_key = get_wallet_key(acc)
    for action in actions_plan:
        try:
            if action == "checkin":
                result = await asyncio.to_thread(ACTION_FUNCS[action], acc.private_key, acc.proxy)
            else:
                result = await ACTION_FUNCS[action](acc.private_key, acc.proxy)

            if result:
                print(result)

        except Exception as e:
            print(f"[{wallet_key}] ❌ Помилка при виконанні {action}: {e}")

        if wallet_key not in stats[date_key]:
            stats[date_key][wallet_key] = {}

        if action == "checkin":
            stats[date_key][wallet_key][action] = True
        else:
            stats[date_key][wallet_key][action] = stats[date_key][wallet_key].get(action, 0) + 1

        save_all_in_stats(stats)

        delay = random.randint(*DELAY_BETWEEN_ACTIONS)
        print(f"[{wallet_key}] Затримка між діями: {delay}с")
        await asyncio.sleep(delay)



async def run_wallet_with_delay(acc, actions_plan, stats, date_key, delay, idx):
    wallet_key = get_wallet_key(acc)
    if delay > 0:
        print(f"[{wallet_key}] Затримка перед стартом гаманця #{idx+1}: {delay}с")
        await asyncio.sleep(delay)
    await run_actions_for_wallet(acc, actions_plan, stats, date_key)

async def run_all_in(accounts):
    stats = load_all_in_stats()
    today = datetime.now().strftime("%Y-%m-%d")
    stats = reset_stats_if_new_day(stats)
    if today not in stats:
        stats[today] = {}
    tasks = []
    for i, acc in enumerate(accounts):
        wallet_key = get_wallet_key(acc)
        limits = get_limits_for_account()
        actions_plan = get_remaining_actions(wallet_key, stats, today, limits)
        if not actions_plan:
            print(f"[{wallet_key}] ВСІ дії на сьогодні вже виконані. Пропуск.")
            continue
        delay = random.randint(*DELAY_BETWEEN_WALLETS)
        tasks.append(run_wallet_with_delay(acc, actions_plan, stats, today, delay, i))
    if not tasks:
        print("✅ Для всіх гаманців всі дії на сьогодні вже виконані.")
        return
    await asyncio.gather(*tasks)
    save_all_in_stats(stats)
    print("✅ ALL IN: всі дії виконані!")

# --- Тестування (dummy) ---
if __name__ == "__main__":
    class DummyAcc:
        def __init__(self, address, private_key, proxy):
            self.address = address
            self.private_key = private_key
            self.proxy = proxy
    test_accounts = [DummyAcc(f"0xTest{i:02d}", "privkey"+str(i), f"proxy{i}") for i in range(1, 4)]
    asyncio.run(run_all_in(test_accounts))
