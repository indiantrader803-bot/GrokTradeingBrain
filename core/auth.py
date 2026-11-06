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
    if not os.path.exists(USERS_FILE):
        default_users = {
            "superadmin": {
                "username": "superadmin",
                "password_hash": hash_password("SuperAdmin@2026"),
                "role": "superadmin",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        with open(USERS_FILE, "w") as f:
            json.dump(default_users, f, indent=2)

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
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
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
