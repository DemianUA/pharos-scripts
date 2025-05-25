import os
import json
from typing import List, Dict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIVATE_KEYS_FILE = os.path.join(BASE_DIR, "private_keys.txt")
PROXIES_FILE = os.path.join(BASE_DIR, "proxies.txt")
USER_AGENTS_FILE = os.path.join(BASE_DIR, "data", "user_agents.json")


class AccountContext:
    def __init__(self, private_key: str, proxy: str, user_agent: str):
        self.private_key = private_key
        self.proxy = proxy
        self.user_agent = user_agent

    def as_dict(self):
        return {
            "private_key": self.private_key,
            "proxy": self.proxy,
            "user_agent": self.user_agent
        }


def load_private_keys() -> List[str]:
    with open(PRIVATE_KEYS_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]


def load_proxies() -> List[str | None]:
    with open(PROXIES_FILE, "r") as f:
        proxies = []
        for line in f:
            raw = line.strip()
            if not raw or raw.lower() == "none":
                proxies.append(None)  # для пустих або "None"
            elif raw.count(":") == 3:
                ip, port, user, pwd = raw.split(":")
                proxy_url = f"http://{user}:{pwd}@{ip}:{port}"
                proxies.append(proxy_url)
            else:
                proxies.append(raw)
        return proxies



def load_user_agents() -> Dict[str, str]:
    if not os.path.exists(USER_AGENTS_FILE):
        return {}
    with open(USER_AGENTS_FILE, "r") as f:
        return json.load(f)


def load_accounts() -> List[AccountContext]:
    private_keys = load_private_keys()
    proxies = load_proxies()
    user_agents = load_user_agents()

    accounts = []
    for i, pk in enumerate(private_keys):
        proxy = proxies[i] if i < len(proxies) else None
        user_agent = user_agents.get(pk, "")
        accounts.append(AccountContext(pk, proxy, user_agent))

    return accounts
