import base64
import json
import os
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple

import streamlit as st
import extra_streamlit_components as stx

from heresy.config import COOKIE_NAME, AUTH_SECRET, REMEMBER_DAYS_DEFAULT, EMAIL_RE, admin_emails
from heresy.db import conn
from heresy.ui import utc_now_iso


def is_admin_user() -> bool:
    if "user" not in st.session_state:
        return False
    return st.session_state["user"]["email"].strip().lower() in admin_emails()


def require_login_stop() -> None:
    if "user" not in st.session_state:
        st.warning("Please log in (or create an account) to do that.")
        st.stop()


def cookie_mgr():
    if "_cookie_mgr" not in st.session_state:
        st.session_state["_cookie_mgr"] = stx.CookieManager()
    return st.session_state["_cookie_mgr"]


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))


def _sign(payload: bytes) -> str:
    secret = AUTH_SECRET if AUTH_SECRET else "dev-insecure-secret"
    sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return _b64url_encode(sig)


def make_auth_token(user_id: int, email: str, *, remember_days: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=remember_days)
    data = {"uid": int(user_id), "email": str(email).strip().lower(), "exp": int(exp.timestamp())}
    payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return _b64url_encode(payload) + "." + _sign(payload)


def parse_auth_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        if not token or "." not in token:
            return None
        p1, p2 = token.split(".", 1)
        payload = _b64url_decode(p1)
        if not hmac.compare_digest(_sign(payload), p2):
            return None
        data = json.loads(payload.decode("utf-8"))
        if int(data.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            return None
        if "uid" not in data or "email" not in data:
            return None
        return data
    except Exception:
        return None


def load_user_from_cookie() -> None:
    if "user" in st.session_state:
        return
    cm = cookie_mgr()
    token = cm.get(COOKIE_NAME)
    parsed = parse_auth_token(token) if token else None
    if not parsed:
        return
    c = conn()
    row = c.execute("SELECT * FROM users WHERE id=? AND email=?", (int(parsed["uid"]), parsed["email"])).fetchone()
    c.close()
    if row:
        st.session_state["user"] = dict(row)


def set_login_cookie(user: Dict[str, Any], remember_days: int) -> None:
    cm = cookie_mgr()
    cm.set(COOKIE_NAME, make_auth_token(int(user["id"]), str(user["email"]), remember_days=remember_days))


def clear_login_cookie() -> None:
    cm = cookie_mgr()
    cm.delete(COOKIE_NAME)


def pbkdf2_hash(password: str, salt_hex: str, iterations: int = 200_000) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        iterations,
    )
    return dk.hex()


def create_user(email: str, display_name: str, password: str) -> Tuple[bool, str]:
    email = (email or "").strip().lower()
    display_name = (display_name or "").strip()

    if not EMAIL_RE.match(email):
        return False, "Please enter a valid email address."
    if len(display_name) < 2:
        return False, "Display name must be at least 2 characters."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."

    salt_hex = os.urandom(16).hex()
    pw_hash = pbkdf2_hash(password, salt_hex)

    c = conn()
    try:
        c.execute(
            "INSERT INTO users(email, display_name, password_hash, salt, created_at) VALUES (?,?,?,?,?)",
            (email, display_name, pw_hash, salt_hex, utc_now_iso()),
        )
        c.commit()
        return True, "Account created. You can log in now."
    except Exception:
        return False, "That email is already registered."
    finally:
        c.close()


def verify_login(email: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    email = (email or "").strip().lower()
    c = conn()
    row = c.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    c.close()
    if not row:
        return False, None

    expected = row["password_hash"]
    salt = row["salt"]
    got = pbkdf2_hash(password, salt)
    if hmac.compare_digest(expected, got):
        return True, dict(row)

    return False, None

def admin_emails() -> set[str]:
    raw = os.environ.get("ADMIN_EMAILS", "").strip()
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}

def is_admin() -> bool:
    if "user" not in st.session_state:
        return False
    email = (st.session_state["user"].get("email") or "").strip().lower()
    return email in admin_emails()