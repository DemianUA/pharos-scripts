# core/verify.py

import requests

def verify_task(address: str, tx_hash: str, jwt_token: str, proxy: str = None, task_id: int = 103) -> bool:
    """
    Повідомляє Pharos API, що транзакція виконана і її потрібно зарахувати до task_id.
    Повертає True, якщо верифікація пройшла успішно.
    """
    try:
        verify_url = (
            f"https://api.pharosnetwork.xyz/task/verify"
            f"?address={address}&task_id={task_id}&tx_hash={tx_hash}"
        )

        headers = {
            "accept": "application/json, text/plain, */*",
            "authorization": f"Bearer {jwt_token}",
            "user-agent": "Mozilla/5.0",
            "referer": "https://testnet.pharosnetwork.xyz/",
        }

        session = requests.Session()
        proxies = {"http": proxy, "https": proxy} if proxy else None
        session.proxies = proxies

        response = session.post(verify_url, headers=headers)
        data = response.json()

        if data.get("code") == 0 and data.get("data", {}).get("verified"):
            print(f"[✅ Verify OK] {tx_hash} → зараховано")
            return True
        else:
            print(f"[⚠️ Verify Fail] {tx_hash} → {data.get('msg', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"[❌ Verify Error] {tx_hash} → {e}")
        return False
