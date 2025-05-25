import asyncio
from core.verify import verify_task

async def retry_verify_task(address: str, tx_hash: str, jwt_token: str, proxy: str = None, retries: int = 5, delay: int = 8) -> bool:
    """
    Робить кілька спроб верифікувати транзакцію в Pharos, якщо API ще не бачить TX.
    """
    for attempt in range(1, retries + 1):
        success = verify_task(address, tx_hash, jwt_token, proxy)
        if success:
            return True
        print(f"[⏳ Retry {attempt}] TX ще не доступна для verify. Чекаю {delay}с...")
        await asyncio.sleep(delay)
    print(f"[❌] Не вдалося верифікувати TX після {retries} спроб → {tx_hash}")
    return False
