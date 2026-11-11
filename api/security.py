"""密碼雜湊與登入 token。只用 Python 內建模組，不必另外安裝套件。

密碼存法：pbkdf2_sha256$迭代次數$salt$雜湊值（約 100 字元，放得進 UserPasswordHash 的 255 字元）
登入 token：使用者編號.到期時間.簽章（用 SECRET_KEY 簽名，伺服器不用另外存 session）
"""
import base64
import hashlib
import hmac
import os
import pathlib
import secrets
import time

ITERATIONS = 200_000
TOKEN_TTL_SECONDS = 7 * 24 * 3600

def _load_secret_key() -> bytes:
    """簽章金鑰：優先用環境變數 EVENT_SECRET_KEY；沒有的話第一次執行時隨機產生，
    存在 api/.secret_key（已列在 .gitignore，不會上傳）。金鑰換掉後，舊的登入會失效。"""
    if os.environ.get("EVENT_SECRET_KEY"):
        return os.environ["EVENT_SECRET_KEY"].encode()
    path = pathlib.Path(__file__).with_name(".secret_key")
    if not path.exists():
        path.write_text(secrets.token_urlsafe(32), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip().encode()


SECRET_KEY = _load_secret_key()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, digest = stored.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt), int(iterations))
    return hmac.compare_digest(candidate, _unb64(digest))


def _sign(payload: str) -> str:
    return _b64(hmac.new(SECRET_KEY, payload.encode(), hashlib.sha256).digest())


def make_token(user_id: int) -> str:
    payload = f"{user_id}.{int(time.time()) + TOKEN_TTL_SECONDS}"
    return f"{payload}.{_sign(payload)}"


def read_token(token: str) -> int | None:
    """回傳 token 裡的使用者編號；token 無效或過期時回傳 None。"""
    try:
        user_id, expires, signature = token.split(".")
    except ValueError:
        return None
    # 比對位元組：compare_digest 遇到含非 ASCII 字元的字串會丟 TypeError，偽造的 token 要當成無效，不是 500
    if not hmac.compare_digest(signature.encode(), _sign(f"{user_id}.{expires}").encode()):
        return None
    if int(expires) < time.time():
        return None
    return int(user_id)
