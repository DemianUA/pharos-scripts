# core/auth.py

import requests
import time
import jwt
from eth_account import Account
from eth_account.messages import encode_defunct

# Кеш токенів: {address: {"jwt": ..., "exp": ...}}
jwt_cache = {}

# Мінімальний буфер часу (в секундах), коли вважаємо токен "майже протухлим"
TOKEN_EXPIRY_BUFFER = 300  # 5 хвилин


def is_jwt_expired(exp_timestamp: int) -> bool:
    current_time = int(time.time())
    return current_time >= (exp_timestamp - TOKEN_EXPIRY_BUFFER)


def decode_jwt_exp(jwt_token: str) -> int | None:
    try:
        payload = jwt.decode(jwt_token, options={"verify_signature": False})
        return payload.get("exp")
    except Exception as e:
        print(f"[JWT Decode Error] {e}")
        return None


def get_jwt_token(private_key: str, proxy: str = None, user_agent: str = None) -> str | None:
    try:
        account = Account.from_key(private_key)
        address = account.address

        # Перевірка в кеші
        if address in jwt_cache:
            cached = jwt_cache[address]
            if "jwt" in cached and "exp" in cached and not is_jwt_expired(cached["exp"]):
                return cached["jwt"]

        # Підпис повідомлення
        message = encode_defunct(text="pharos")
        signed_message = Account.sign_message(message, private_key)
        signature = signed_message.signature.hex()

        headers = {
            "accept": "application/json, text/plain, */*",
            "user-agent": user_agent or "Mozilla/5.0",
            "referer": "https://testnet.pharosnetwork.xyz/",
            "authorization": "Bearer null"
        }

        session = requests.Session()
        proxies = {"http": proxy, "https": proxy} if proxy else None
        session.proxies = proxies

        login_url = f"https://api.pharosnetwork.xyz/user/login?address={address}&signature={signature}&invite_code=S6NGMzXSCDBxhnwo"
        response = session.post(login_url, headers=headers)
        data = response.json()

        if data.get("code") != 0 or "jwt" not in data.get("data", {}):
            print(f"[Login ❌] {address} → {data.get('msg', 'Unknown error')}")
            return None

        jwt_token = data["data"]["jwt"]
        exp = decode_jwt_exp(jwt_token)

        if not exp:
            print(f"[⚠️] JWT отримано, але не вдалося визначити exp: {jwt_token[:30]}...")
            return jwt_token

        # Кешуємо
        jwt_cache[address] = {"jwt": jwt_token, "exp": exp}

        print(f"[Login ✅] {address} → JWT отримано (дійсний до {time.strftime('%H:%M:%S', time.localtime(exp))})")
        return jwt_token

    except Exception as e:
        print(f"[JWT Error ❌] {private_key[:10]}... → {e}")
        return None
