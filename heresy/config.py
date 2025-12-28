import os
import re

APP_TITLE = "Ashes Across the Void"
DB_PATH = "data/campaign.db"
CP_MIN, CP_MAX = -6, 6

os.makedirs("data", exist_ok=True)

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

BATTLE_TYPES = {
    "heresy30k": "Heresy (30k) — Planetary",
    "legions_imperialis": "Legions Imperialis — Planetary",
    "adeptus_titanicus": "Adeptus Titanicus — Planetary",
    "gothic_armada": "Gothic Armada — Void (Space)",
}
SIDE_LABELS = {"loyalist": "Loyalist", "traitor": "Traitor", "draw": "Draw"}

COOKIE_NAME = "heresy_auth"
AUTH_SECRET = os.environ.get("AUTH_SECRET", "").strip()
REMEMBER_DAYS_DEFAULT = 7


def admin_emails() -> set:
    raw = os.environ.get("ADMIN_EMAILS", "").strip()
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}
