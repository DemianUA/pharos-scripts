import random
import asyncio
import json
from eth_account import Account
from core.mint_nft import mint_nft


from config import (
    RETRIES_PER_ACTION,
    DELAY_BETWEEN_RETRIES,
    DELAY_BETWEEN_WALLETS,
    RANDOMIZE_WALLETS_ORDER
)

from core.account_loader import load_accounts, AccountContext
from core.checkin import perform_checkin, checkin_all_wallets
from core.send_tokens_async import send_phrs_to_self
from core.swap_phrs_usdc import swap_phrs_to_usdc
from core.swap_usdc_phrs import swap_usdc_to_phrs
from core.faucet import run_faucet_all_wallets
from core.stats import collect_stats
from core.generate_user_agents import generate_user_agents
from core.smartcontract_async import deploy_timer_all_wallets
from core.liquidity_async import add_liquidity_phrs_usdc
from core.all_in import run_all_in


async def retry_action(action_func, *args):
    for attempt in range(RETRIES_PER_ACTION):
        try:
            # 🔄 Якщо функція не async — запускати в окремому потоці
            if asyncio.iscoroutinefunction(action_func):
                result = await action_func(*args)
            else:
                result = await asyncio.to_thread(action_func, *args)

            if result:
                short_wallet = args[0][-8:] if args and isinstance(args[0], str) else ""
                print(f"[{short_wallet}] {result}")
            if isinstance(result, str) and "Недостатньо" in result:
                return
            if result is not False:
                return
            print(f"⚠️ Помилка, спроба {attempt + 1}/{RETRIES_PER_ACTION}")
        except Exception as e:
            print(f"❌ Виняток: {e}")
            if "TX_REPLAY_ATTACK" in str(e):
                delay = random.randint(15, 25)
                print(f"⏳ Затримка через TX_REPLAY_ATTACK: {delay}с")
                await asyncio.sleep(delay)
                continue
        if attempt < RETRIES_PER_ACTION - 1:
            delay = random.randint(*DELAY_BETWEEN_RETRIES)
            print(f"⏳ Затримка перед повтором: {delay}с")
            await asyncio.sleep(delay)


async def handle_account(account: AccountContext, action_id: str):
    print(f"\n🧾 Обробка акаунта: {account.private_key[:10]}...")

    if action_id == "1":
        await retry_action(swap_phrs_to_usdc, account.private_key, account.proxy)
    elif action_id == "2":
        await retry_action(swap_usdc_to_phrs, account.private_key, account.proxy)
    elif action_id == "3":
        await retry_action(send_phrs_to_self, account.private_key, account.proxy)
    elif action_id == "checkin":
        await retry_action(perform_checkin, account.private_key, account.proxy)
    else:
        print("❌ Невідома дія")


async def main():
    while True:
        print("\n=== Головне меню ===")
        print("1. 🔥 ALL IN ")
        print("2. ⚙️ Окремі ончейн дії")
        print("3. ✅ Check-in")
        print("4. 🚰 Отримати токени з крана")
        print("5. 📊 Зібрати статистику")
        print("6. 🧪 Згенерувати user-agent'и")
        print("0. 🚪 Вийти")

        choice = input("Оберіть опцію: ")

        if choice == "0":
            print("👋 До зустрічі!")
            break

        elif choice == "1":
            accounts = load_accounts()
            await run_all_in(accounts)
            continue

        elif choice == "2":
            while True:
                print("\n🔧 Ончейн дії:")
                print("1. 🔁 Свап PHRS → USDC")
                print("2. 🔁 Свап USDC → PHRS")
                print("3. 💸 Відправити PHRS самому собі")
                print("4. 🧱 Деплой смартконтракту Timer")
                print("5. 💧 Додати ліквідність у пул PHRS-USDC")
                print("6. 🖼️ Мінт NFT")
                print("0. 🔙 Назад")
                sub_choice = input("Оберіть дію: ")

                if sub_choice == "0":
                    break

                accounts = load_accounts()
                if RANDOMIZE_WALLETS_ORDER:
                    random.shuffle(accounts)

                for acc in accounts:
                    if sub_choice in ["1", "2", "3"]:
                        await handle_account(acc, sub_choice)
                    elif sub_choice == "4":
                        await deploy_timer_all_wallets()
                        break
                    elif sub_choice == "5":
                        await retry_action(add_liquidity_phrs_usdc, acc.private_key, acc.proxy)
                    elif sub_choice == "6":
                        await retry_action(mint_nft, acc.private_key, acc.proxy)

                    delay = random.randint(*DELAY_BETWEEN_WALLETS)
                    print(f"⏳ Затримка між акаунтами: {delay}с")
                    await asyncio.sleep(delay)

        elif choice == "3":
            accounts = load_accounts()
            if RANDOMIZE_WALLETS_ORDER:
                random.shuffle(accounts)
            for acc in accounts:
                await handle_account(acc, "checkin")
                delay = random.randint(*DELAY_BETWEEN_WALLETS)
                print(f"⏳ Затримка між акаунтами: {delay}с")
                await asyncio.sleep(delay)

        elif choice == "4":
            run_faucet_all_wallets()

        elif choice == "5":
            collect_stats()

        elif choice == "6":
            generate_user_agents()

        else:
            print("❌ Невірна опція")


if __name__ == "__main__":
    asyncio.run(main())
