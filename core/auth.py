import os
import json
import hashlib
import hmac
import time
from typing import Optional, Dict

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "swarmdesk-superadmin-secret-key-999")

def ensure_users_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    target_password = os.getenv("SUPERADMIN_PASSWORD", "Myjobmail@1234")
    target_hash = hash_password(target_password)
    
    users = {}
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                users = json.load(f)
        except Exception:
            users = {}

    # Always ensure superadmin exists with the latest configured password
    default_delta_key = os.getenv("DELTA_INDIA_API_KEY", "Y3rkRCYcePZokLi0iBjqYFLwhSPoIa")
    default_delta_sec = os.getenv("DELTA_INDIA_API_SECRET", "NviyBnPIZkKmEh29h6pFe18Vp6jKRXDqUQnpnrvs2WTj9CxhP5I4LRHOf75F")
    default_delta_url = os.getenv("DELTA_INDIA_BASE_URL", "https://api.india.delta.exchange")

    if "superadmin" not in users:
        users["superadmin"] = {
            "username": "superadmin",
            "password_hash": target_hash,
            "role": "superadmin",
            "api_keys": {
                "delta": {
                    "api_key": default_delta_key,
                    "api_secret": default_delta_sec,
                    "base_url": default_delta_url
                }
            },
            "strategy": {
                "name": "Superadmin VWAP Growth",
                "min_rr": 3.2,
                "risk_per_trade_pct": 0.75,
                "min_consensus_score": 0.78,
                "vwap_window_hours": 6,
                "strategy_type": "vwap_bands"
            },
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    else:
        users["superadmin"]["password_hash"] = target_hash
        if "api_keys" not in users["superadmin"]:
            users["superadmin"]["api_keys"] = {}
        if "delta" not in users["superadmin"]["api_keys"] or not users["superadmin"]["api_keys"]["delta"].get("api_key"):
            users["superadmin"]["api_keys"]["delta"] = {
                "api_key": default_delta_key,
                "api_secret": default_delta_sec,
                "base_url": default_delta_url
            }
        if "strategy" not in users["superadmin"]:
            users["superadmin"]["strategy"] = {
                "name": "Superadmin VWAP Growth",
                "min_rr": 3.2,
                "risk_per_trade_pct": 0.75,
                "min_consensus_score": 0.78,
                "vwap_window_hours": 6,
                "strategy_type": "vwap_bands"
            }

    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def hash_password(password: str) -> str:
    return hashlib.sha256((password + SECRET_KEY).encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_password(password), hashed)

def get_users() -> Dict[str, dict]:
    ensure_users_file()
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def authenticate_user(username: str, password: str) -> Optional[dict]:
    users = get_users()
    user = users.get(username.lower().strip())
    if user and verify_password(password, user["password_hash"]):
        return user
    return None

def register_user(username: str, password: str, role: str = "trader") -> bool:
    users = get_users()
    uname = username.lower().strip()
    if uname in users:
        return False
    users[uname] = {
        "username": uname,
        "password_hash": hash_password(password),
        "role": role,
        "api_keys": {},
        "strategy": {
            "name": f"{uname}'s Alpha Strategy",
            "min_rr": 3.0,
            "risk_per_trade_pct": 0.75,
            "min_consensus_score": 0.78,
            "vwap_window_hours": 6,
            "strategy_type": "vwap_bands"
        },
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    save_users(users)
    return True

def get_user_data(username: str) -> Optional[dict]:
    users = get_users()
    return users.get(username.lower().strip())

def update_user_api_key(username: str, exchange: str, api_key: str, api_secret: str, base_url: str = "") -> bool:
    users = get_users()
    uname = username.lower().strip()
    if uname not in users:
        return False
    if "api_keys" not in users[uname]:
        users[uname]["api_keys"] = {}
    users[uname]["api_keys"][exchange.lower()] = {
        "api_key": api_key.strip(),
        "api_secret": api_secret.strip(),
        "base_url": base_url.strip(),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    save_users(users)
    return True

def update_user_strategy(username: str, strategy_data: dict) -> bool:
    users = get_users()
    uname = username.lower().strip()
    if uname not in users:
        return False
    users[uname]["strategy"] = strategy_data
    save_users(users)
    return True


def create_session_token(username: str) -> str:
    timestamp = str(int(time.time()))
    signature = hmac.new(SECRET_KEY.encode(), f"{username}:{timestamp}".encode(), hashlib.sha256).hexdigest()
    return f"{username}:{timestamp}:{signature}"

def verify_session_token(token: str) -> Optional[str]:
    if not token or ":" not in token:
        return None
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None
        username, timestamp, signature = parts
        # Session lasts 30 days
        if time.time() - int(timestamp) > 86400 * 30:
            return None
        expected = hmac.new(SECRET_KEY.encode(), f"{username}:{timestamp}".encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(signature, expected):
            return username
    except Exception:
        return None
    return None
