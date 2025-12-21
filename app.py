# app.py
# Heresy Campaign Tracker — Planets & Void (Gothic sci-fi themed, editable battles + full recalculation)
#
# Run:
#   Windows:   py -m streamlit run app.py
#   macOS/Linux: python3 -m streamlit run app.py
#
# Notes:
# - SQLite file: campaign.db
# - Deleting battles triggers a full map recomputation by replaying remaining battles in order.
# - Deletion permissions:
#     - battle creator can delete their own entries, OR
#     - any email listed in ADMIN_EMAILS env var can delete anything (comma-separated).
#       Example: ADMIN_EMAILS="you@email.com,friend@email.com"

import os
import re
import hmac
import math
import sqlite3
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ============================
# App Config
# ============================
APP_TITLE = "Heresy Campaign Tracker — Planets & Void"
DB_PATH = "data/campaign.db"
CP_MIN, CP_MAX = -6, 6

# Ensure persistent data directory exists (for Docker/Synology)
os.makedirs("data", exist_ok=True)

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

BATTLE_TYPES = {
    "heresy30k": "Heresy (30k) — Planetary",
    "legions_imperialis": "Legions Imperialis — Planetary",
    "adeptus_titanicus": "Adeptus Titanicus — Planetary",
    "gothic_armada": "Gothic Armada — Void (Space)",
}
SIDE_LABELS = {"loyalist": "Loyalist", "traitor": "Traitor", "draw": "Draw"}



# ============================
# Time / DB
# ============================
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    c = conn()
    cur = c.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        display_name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS territories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        q INTEGER NOT NULL,
        r INTEGER NOT NULL,
        name TEXT NOT NULL,
        is_planet INTEGER NOT NULL DEFAULT 0,
        cp INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        UNIQUE(q, r)
    )
    """)

    # Ensure battles includes the targets used for replay/recalc
    cur.execute("""
    CREATE TABLE IF NOT EXISTS battles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        created_by_user_id INTEGER NOT NULL,
        created_by_email TEXT NOT NULL,

        battle_type TEXT NOT NULL,
        location_territory_id INTEGER NOT NULL,

        winning_side TEXT NOT NULL,
        is_crushing INTEGER NOT NULL DEFAULT 0,

        splash_target_territory_id INTEGER,
        pressure_target_territory_id INTEGER,

        notes TEXT,
        status TEXT NOT NULL DEFAULT 'approved',

        FOREIGN KEY(created_by_user_id) REFERENCES users(id),
        FOREIGN KEY(location_territory_id) REFERENCES territories(id)
    )
    """)

    c.commit()

    cur.execute("SELECT COUNT(*) AS n FROM territories")
    n = int(cur.fetchone()["n"])
    if n == 0:
        seed_default_map(c)

    c.close()


def seed_default_map(c: sqlite3.Connection, radius: int = 4) -> None:
    now = utc_now_iso()

    planets = {
        (0, 0): "Terra (Anchor)",
        (2, -1): "Cthonia",
        (-2, 1): "Isstvan System",
        (1, 2): "Paramar",
        (-3, 0): "Beta-Garmon",
        (0, -3): "Molech",
    }

    coords: List[Tuple[int, int]] = []
    for q in range(-radius, radius + 1):
        r1 = max(-radius, -q - radius)
        r2 = min(radius, -q + radius)
        for r in range(r1, r2 + 1):
            coords.append((q, r))

    cur = c.cursor()
    for q, r in coords:
        is_planet = 1 if (q, r) in planets else 0
        name = planets.get((q, r), f"Void {q},{r}")
        cur.execute(
            "INSERT INTO territories(q, r, name, is_planet, cp, updated_at) VALUES (?,?,?,?,?,?)",
            (q, r, name, is_planet, 0, now),
        )
    c.commit()


# ============================
# Gothic Theme + UI
# ============================
def apply_heresy_style() -> None:
    """
    Gothic dark theme + ivory text, but with a pragmatic dropdown fix:
    Streamlit/BaseWeb sometimes forces the dropdown menu background to white.
    So we FORCE dropdown option text to dark (readable) while keeping the closed
    select control styled dark/ivory.
    """
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;800&family=IM+Fell+English:ital@0;1&display=swap');

        :root{
          --bg0:#07070a;
          --panel:#10111a;

          --ink:#f0eadc;        /* ivory */
          --ink2:#d7cfbf;       /* muted ivory */

          --red:#b30000;
          --gold:#b89b5e;

          --border: rgba(184,155,94,.25);
          --shadow: 0 14px 40px rgba(0,0,0,.35);
          --glow: 0 0 0.6rem rgba(179,0,0,.25);
        }

        /* Remove / restyle Streamlit header bar (white strip) */
        [data-testid="stHeader"]{
          background: rgba(0,0,0,0) !important;
          box-shadow: none !important;
        }

        /* App background */
        .stApp{
          background:
            radial-gradient(1200px 700px at 30% 10%, rgba(179,0,0,.10), transparent 55%),
            radial-gradient(900px 500px at 85% 35%, rgba(184,155,94,.08), transparent 60%),
            linear-gradient(180deg, var(--bg0), #05050a 65%, #030308);
          color: var(--ink) !important;
        }

        /* Global text forcing (ivory) */
        html, body, p, span, div, li, label,
        .stMarkdown, .stMarkdown p, .stMarkdown span, .stMarkdown div,
        [data-testid="stMarkdownContainer"] *{
          color: var(--ink) !important;
        }
        .stCaption, [data-testid="stCaptionContainer"], small{
          color: var(--ink2) !important;
          opacity: 0.95 !important;
        }

        /* Typography */
        h1,h2,h3,h4,h5{
          font-family: "Cinzel", "Times New Roman", serif !important;
          letter-spacing: .6px;
          color: var(--ink) !important;
        }
        html, body, [class*="css"]{
          font-family: "IM Fell English", Georgia, serif !important;
        }

        /* Sidebar */
        section[data-testid="stSidebar"]{
          background: linear-gradient(180deg, #0b0c12, #07070a) !important;
          border-right: 1px solid rgba(184,155,94,.22) !important;
        }
        section[data-testid="stSidebar"] *{
          color: var(--ink) !important;
        }

        /* Containers */
        div[data-testid="stVerticalBlockBorderWrapper"]{
          border: 1px solid rgba(184,155,94,.18) !important;
          background: linear-gradient(180deg, rgba(16,17,26,.82), rgba(10,11,16,.82)) !important;
          box-shadow: var(--shadow) !important;
          border-radius: 14px !important;
        }

        /* Inputs */
        .stTextInput input, .stTextArea textarea{
          background: rgba(10,11,16,.90) !important;
          border: 1px solid var(--border) !important;
          color: var(--ink) !important;
          caret-color: var(--ink) !important;
          border-radius: 10px !important;
        }
        .stTextInput input::placeholder, .stTextArea textarea::placeholder{
          color: rgba(240,234,220,0.55) !important;
        }

        /* ======================================
           SELECTBOX (closed control): dark + ivory
           ====================================== */
        div[data-baseweb="select"] > div{
          background: rgba(10,11,16,.92) !important;
          border: 1px solid var(--border) !important;
          border-radius: 10px !important;
          box-shadow: 0 10px 25px rgba(0,0,0,.25) !important;
        }
        div[data-baseweb="select"] *{
          color: var(--ink) !important;
        }
        div[data-baseweb="select"] input{
          background: transparent !important;
          color: var(--ink) !important;
        }

        /* ===========================
        DROPDOWN FIX (DESKTOP)
        =========================== */
        @media (pointer: fine) {
        div[data-baseweb="popover"] li[role="option"],
        div[data-baseweb="popover"] li[role="option"] *,
        ul[role="listbox"] li,
        ul[role="listbox"] li * {
            color: #111 !important;
        }

        li[role="option"]:hover {
            background: rgba(0,0,0,0.08) !important;
        }

        li[aria-selected="true"] {
            background: rgba(0,0,0,0.12) !important;
        }
        }

        /* ===========================
        DROPDOWN FIX (MOBILE)
        =========================== */
        @media (pointer: coarse) {
        div[data-baseweb="popover"],
        ul[role="listbox"] {
            background: rgba(12,12,18,0.98) !important;
        }

        div[data-baseweb="popover"] li[role="option"],
        div[data-baseweb="popover"] li[role="option"] *,
        ul[role="listbox"] li,
        ul[role="listbox"] li * {
            color: #f0eadc !important;
        }

        li[role="option"]:hover,
        li[aria-selected="true"] {
            background: rgba(184,155,94,0.22) !important;
        }
        }


        /* Buttons */
        .stButton button{
          background: linear-gradient(180deg, #c20000, #7a0000) !important;
          border: 1px solid rgba(184,155,94,.35) !important;
          box-shadow: var(--glow) !important;
          border-radius: 12px !important;
          color: #fff !important;
          font-weight: 800 !important;
          letter-spacing: .4px !important;
        }
        .stButton button:hover{
          filter: brightness(1.06);
          transform: translateY(-1px);
        }

        /* Metrics */
        div[data-testid="stMetric"]{
          background: linear-gradient(180deg, rgba(16,17,26,.65), rgba(10,11,16,.75)) !important;
          border: 1px solid rgba(184,155,94,.22) !important;
          border-radius: 14px !important;
          padding: 10px 12px !important;
        }
        div[data-testid="stMetric"] *{
          color: var(--ink) !important;
        }

        /* Dataframes / tables */
        [data-testid="stDataFrame"] *{
          color: var(--ink) !important;
        }

        /* Divider */
        hr{
          border: none !important;
          height: 1px !important;
          background: linear-gradient(90deg, transparent, rgba(184,155,94,.55), transparent) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )




def title_plate(text: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div style="
          padding:14px 18px;
          border-radius:14px;
          border:1px solid rgba(184,155,94,.30);
          background: linear-gradient(90deg, rgba(179,0,0,.20), rgba(16,17,26,.65));
          box-shadow: 0 14px 40px rgba(0,0,0,.35);
          margin-bottom: 12px;">
          <div style="font-family:Cinzel, serif; font-weight:800; font-size:1.35rem; letter-spacing:.8px; color: #f0eadc;">
            {text}
          </div>
          <div style="opacity:.92; margin-top:2px; color: #d7cfbf;">
            {subtitle}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def set_banner(message: str, *, kind: str = "success") -> None:
    st.session_state["banner"] = {
        "message": message,
        "kind": kind,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def render_banner_once() -> None:
    payload = st.session_state.get("banner")
    if not payload:
        return

    msg = payload.get("message", "")
    kind = payload.get("kind", "info")
    icon = {"success": "✅", "error": "⛔", "info": "📣"}.get(kind, "📣")

    st.markdown(
        f"""
        <style>
        .heresy-banner {{
            position: relative;
            width: 100%;
            padding: 14px 18px;
            border-radius: 12px;
            color: #fff;
            border: 1px solid rgba(255,255,255,0.18);
            box-shadow: 0 10px 30px rgba(179,0,0,0.30);
            overflow: hidden;
            background:
              repeating-linear-gradient(
                45deg,
                #7a0000 0px,
                #7a0000 14px,
                #b30000 14px,
                #b30000 28px
              );
            animation: bannerDrop 380ms ease-out, bannerGlow 1200ms ease-in-out 1;
        }}
        .heresy-banner::before {{
            content: "";
            position: absolute;
            top: -60%;
            left: -30%;
            width: 60%;
            height: 220%;
            background: rgba(255,255,255,0.10);
            transform: rotate(25deg);
            animation: bannerSheen 1400ms ease-in-out 1;
        }}
        .heresy-banner::after {{
            content:"";
            position:absolute;
            inset:0;
            background: repeating-linear-gradient(
              180deg,
              rgba(255,255,255,0.04) 0px,
              rgba(255,255,255,0.04) 1px,
              transparent 2px,
              transparent 6px
            );
            mix-blend-mode: overlay;
            pointer-events:none;
        }}
        .heresy-banner .txt {{
            position: relative;
            font-size: 1.02rem;
            line-height: 1.25rem;
            font-weight: 900;
            letter-spacing: 0.4px;
            text-shadow: 0 2px 12px rgba(0,0,0,0.35);
        }}
        @keyframes bannerDrop {{
            from {{ transform: translateY(-12px); opacity: 0; }}
            to   {{ transform: translateY(0); opacity: 1; }}
        }}
        @keyframes bannerGlow {{
            0%   {{ filter: brightness(1); }}
            35%  {{ filter: brightness(1.25); }}
            100% {{ filter: brightness(1); }}
        }}
        @keyframes bannerSheen {{
            0%   {{ transform: translateX(-40%) rotate(25deg); opacity: 0; }}
            25%  {{ opacity: 1; }}
            100% {{ transform: translateX(220%) rotate(25deg); opacity: 0; }}
        }}
        </style>

        <div class="heresy-banner">
            <div class="txt">{icon} {msg}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    del st.session_state["banner"]


# ============================
# Auth
# ============================
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
    except sqlite3.IntegrityError:
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


def require_login_stop() -> None:
    if "user" not in st.session_state:
        st.warning("Please log in (or create an account) to do that.")
        st.stop()


def admin_emails() -> set:
    raw = os.environ.get("ADMIN_EMAILS", "").strip()
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def can_delete_battle(current_user_email: str, battle_created_by_email: str) -> bool:
    cu = (current_user_email or "").strip().lower()
    owner = (battle_created_by_email or "").strip().lower()
    if cu and cu == owner:
        return True
    return cu in admin_emails()


# ============================
# Campaign Rules
# ============================
def clamp_cp(x: int) -> int:
    return max(CP_MIN, min(CP_MAX, x))


def territory_neighbors(q: int, r: int) -> List[Tuple[int, int]]:
    return [(q + 1, r), (q - 1, r), (q, r + 1), (q, r - 1), (q + 1, r - 1), (q - 1, r + 1)]


def side_sign(side: str) -> int:
    if side == "loyalist":
        return +1
    if side == "traitor":
        return -1
    return 0


def status_from_cp(cp: int) -> str:
    a = abs(cp)
    if a <= 2:
        return "Contested"
    if a <= 5:
        return "Held"
    return "Secure"


def side_from_cp(cp: int) -> str:
    if cp > 0:
        return "Loyalist"
    if cp < 0:
        return "Traitor"
    return "Neutral"


def base_ip(battle_type: str) -> int:
    return {
        "heresy30k": 2,
        "legions_imperialis": 3,
        "adeptus_titanicus": 3,
        "gothic_armada": 2,
    }[battle_type]


def int_ip_with_crushing(base: int, is_crushing: bool) -> int:
    v = int(round(base * (1.5 if is_crushing else 1.0)))
    return max(1, v) if base > 0 else 0


def is_controlled(cp: int) -> bool:
    return abs(cp) >= 3


def cp_sign(cp: int) -> int:
    return 1 if cp > 0 else -1 if cp < 0 else 0


def count_adjacent_enemy_space_control(c: sqlite3.Connection, planet_q: int, planet_r: int, enemy_sign: int) -> int:
    cur = c.cursor()
    count = 0
    for nq, nr in territory_neighbors(planet_q, planet_r):
        row = cur.execute(
            "SELECT is_planet, cp FROM territories WHERE q=? AND r=?",
            (nq, nr),
        ).fetchone()
        if not row:
            continue
        if int(row["is_planet"]) == 1:
            continue
        cp = int(row["cp"])
        if is_controlled(cp) and cp_sign(cp) == enemy_sign:
            count += 1
    return count


def enemy_controls_adjacent_space(c: sqlite3.Connection, planet_q: int, planet_r: int, enemy_sign: int) -> bool:
    return count_adjacent_enemy_space_control(c, planet_q, planet_r, enemy_sign) >= 1


def apply_cp_delta(c: sqlite3.Connection, territory_id: int, delta: int) -> None:
    if delta == 0:
        return

    cur = c.cursor()
    t = cur.execute("SELECT id,q,r,is_planet,cp FROM territories WHERE id=?", (territory_id,)).fetchone()
    if not t:
        return

    q, r = int(t["q"]), int(t["r"])
    is_planet = bool(int(t["is_planet"]))
    old_cp = int(t["cp"])
    adjusted_delta = int(delta)

    # Secure resistance (planets only)
    if is_planet and abs(old_cp) == 6:
        old_s = cp_sign(old_cp)
        d_s = 1 if adjusted_delta > 0 else -1
        if d_s != old_s:
            enemy_s = d_s
            if not enemy_controls_adjacent_space(c, q, r, enemy_s):
                mag = abs(adjusted_delta)
                adjusted_delta = max(1, mag - 1) * d_s

    new_cp = clamp_cp(old_cp + adjusted_delta)

    # Orbital pressure block: cannot become Secure if enemy controls >=2 adjacent space tiles
    if is_planet and abs(new_cp) == 6:
        new_s = cp_sign(new_cp)
        enemy_s = -new_s
        hostile_spaces = count_adjacent_enemy_space_control(c, q, r, enemy_s)
        if hostile_spaces >= 2:
            new_cp = 5 * new_s

    cur.execute("UPDATE territories SET cp=?, updated_at=? WHERE id=?", (new_cp, utc_now_iso(), territory_id))


def resolve_battle(
    c: sqlite3.Connection,
    battle_type: str,
    location_id: int,
    winning_side: str,
    is_crushing: bool,
    splash_space_id: Optional[int],
    pressure_planet_id: Optional[int],
) -> None:
    cur = c.cursor()
    loc = cur.execute("SELECT id,is_planet FROM territories WHERE id=?", (location_id,)).fetchone()
    if not loc:
        raise ValueError("Invalid location territory.")
    loc_is_planet = bool(int(loc["is_planet"]))

    # placement rules
    if battle_type == "gothic_armada":
        if loc_is_planet:
            raise ValueError("Gothic Armada battles must be logged in a SPACE tile (void).")
    else:
        if not loc_is_planet:
            raise ValueError("Planetary battles must be logged on a PLANET.")

    if winning_side == "draw":
        return

    main_ip = int_ip_with_crushing(base_ip(battle_type), is_crushing)
    main_delta = main_ip * side_sign(winning_side)
    apply_cp_delta(c, location_id, main_delta)

    if battle_type == "gothic_armada":
        if pressure_planet_id is not None:
            apply_cp_delta(c, pressure_planet_id, 1 * side_sign(winning_side))
    else:
        if splash_space_id is not None:
            apply_cp_delta(c, splash_space_id, 1 * side_sign(winning_side))


# ============================
# Recalculation
# ============================
def reset_all_cp(c: sqlite3.Connection) -> None:
    c.execute("UPDATE territories SET cp=0, updated_at=?", (utc_now_iso(),))


def recalc_from_battles() -> None:
    """
    Recompute the entire map state by:
    - setting all territory CP to 0
    - replaying all approved battles in ascending id order
    """
    c = conn()
    try:
        c.execute("BEGIN")
        reset_all_cp(c)

        rows = c.execute(
            """
            SELECT
              id, battle_type, location_territory_id, winning_side, is_crushing,
              splash_target_territory_id, pressure_target_territory_id
            FROM battles
            WHERE status='approved'
            ORDER BY id ASC
            """
        ).fetchall()

        for r in rows:
            resolve_battle(
                c,
                battle_type=r["battle_type"],
                location_id=r["location_territory_id"],
                winning_side=r["winning_side"],
                is_crushing=bool(int(r["is_crushing"])),
                splash_space_id=r["splash_target_territory_id"],
                pressure_planet_id=r["pressure_target_territory_id"],
            )

        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


# ============================
# Reporting
# ============================
def df_territories() -> pd.DataFrame:
    c = conn()
    df = pd.read_sql_query("SELECT * FROM territories ORDER BY is_planet DESC, name ASC", c)
    c.close()
    return df


def df_battles(limit: int = 400) -> pd.DataFrame:
    c = conn()
    df = pd.read_sql_query(
        """
        SELECT
            b.id, b.created_at, b.created_by_email,
            b.battle_type, b.winning_side, b.is_crushing,
            t.name AS location_name,
            b.splash_target_territory_id, b.pressure_target_territory_id,
            b.notes
        FROM battles b
        JOIN territories t ON t.id = b.location_territory_id
        ORDER BY b.id DESC
        LIMIT ?
        """,
        c,
        params=(limit,),
    )
    c.close()
    return df


def campaign_score(df: pd.DataFrame) -> Dict[str, int]:
    loyal = 0
    traitor = 0

    for _, r in df.iterrows():
        cp = int(r["cp"])
        if abs(cp) < 3:
            continue
        is_planet = bool(r["is_planet"])
        status = status_from_cp(cp)

        pts = 0
        if is_planet:
            pts = 3 if status == "Secure" else 2
        else:
            pts = 2 if status == "Secure" else 1

        if cp > 0:
            loyal += pts
        else:
            traitor += pts

    return {"loyalist": loyal, "traitor": traitor, "lead": loyal - traitor}


# ============================
# Map (more readable + icons)
# ============================
@dataclass
class HexGeom:
    size: float = 1.0
    pointy_top: bool = True


def hex_to_xy(q: int, r: int, geom: HexGeom) -> Tuple[float, float]:
    s = geom.size
    if geom.pointy_top:
        x = s * math.sqrt(3) * (q + r / 2)
        y = s * 1.5 * r
    else:
        x = s * 1.5 * q
        y = s * math.sqrt(3) * (r + q / 2)
    return x, y


def hex_corners(x: float, y: float, geom: HexGeom) -> List[Tuple[float, float]]:
    s = geom.size
    pts = []
    for i in range(6):
        angle_deg = 60 * i - (30 if geom.pointy_top else 0)
        a = math.radians(angle_deg)
        pts.append((x + s * math.cos(a), y + s * math.sin(a)))
    return pts


def cp_color(cp: int) -> str:
    # Higher contrast for dark UI
    if cp == 0:
        return "rgb(26,28,40)"
    a = abs(cp) / 6.0
    a = max(0.18, a)  # keep visible even at low CP

    if cp > 0:
        # Loyalist: blue -> cyan
        r = int(35 + 25 * a)
        g = int(120 + 95 * a)
        b = int(190 + 55 * a)
        return f"rgb({r},{g},{b})"
    # Traitor: crimson -> hot red
    r = int(170 + 75 * a)
    g = int(55 + 40 * a)
    b = int(45 + 25 * a)
    return f"rgb({r},{g},{b})"


def tile_glyph(is_planet: bool) -> str:
    # Better readability than emojis across platforms
    return "◉" if is_planet else "✦"




def make_map(df: pd.DataFrame, geom: HexGeom) -> go.Figure:
    fig = go.Figure()
    SHOW_PLANET_NAMES = False

    for _, row in df.iterrows():
        q, r = int(row["q"]), int(row["r"])
        name = str(row["name"])
        is_planet = bool(row["is_planet"])
        cp = int(row["cp"])

        status = status_from_cp(cp)
        side = side_from_cp(cp)

        x, y = hex_to_xy(q, r, geom)
        corners = hex_corners(x, y, geom)
        xs = [p[0] for p in corners] + [corners[0][0]]
        ys = [p[1] for p in corners] + [corners[0][1]]

        if status == "Secure":
            dash = "solid"
            width = 3.2
            outline = "rgba(240,234,220,0.72)"   # ivory
        elif status == "Held":
            dash = "solid"
            width = 2.3
            outline = "rgba(209,184,122,0.58)"   # warm gold
        else:
            dash = "dash"
            width = 1.35
            outline = "rgba(240,234,220,0.35)"

        hover = (
            f"<b>{name}</b><br>"
            f"{'Planet' if is_planet else 'Void'}<br>"
            f"CP: {cp} ({side})<br>"
            f"Status: {status}<br>"
            f"Coord: ({q},{r})"
        )

        # Polygon
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                fill="toself",
                fillcolor=cp_color(cp),
                line=dict(width=width, dash=dash, color=outline),
                hoverinfo="text",
                text=hover,
                showlegend=False,
            )
        )

        # Inner marker(s)
        if is_planet:
            fig.add_trace(
                go.Scatter(
                    x=[x],
                    y=[y],
                    mode="markers+text",
                    marker=dict(
                        size=20,
                        color="rgba(12,12,18,0.25)",
                        line=dict(width=2.2, color="rgba(209,184,122,0.90)"),
                    ),
                    text=[tile_glyph(True)],
                    textfont=dict(size=18, color="rgba(240,234,220,0.97)"),
                    textposition="middle center",
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
            if SHOW_PLANET_NAMES:
                fig.add_trace(
                    go.Scatter(
                        x=[x],
                        y=[y - 0.36],
                        mode="text",
                        text=[name],
                        textfont=dict(size=11, color="rgba(240,234,220,0.92)"),
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )
        else:
            # A faint space glyph so void tiles read as "space"
            fig.add_trace(
                go.Scatter(
                    x=[x],
                    y=[y],
                    mode="text",
                    text=[tile_glyph(False)],
                    textfont=dict(size=12, color="rgba(240,234,220,0.35)"),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    fig.update_layout(
    dragmode=False,                 # disables box/lasso/zoom drag
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(visible=False, fixedrange=True),  # disables zoom/pan on x
    yaxis=dict(visible=False, fixedrange=True, scaleanchor="x", scaleratio=1),  # disables zoom/pan on y
    height=680,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#f0eadc"),
    )
    return fig


# ============================
# Pages
# ============================
def page_account():
    title_plate("Account", "Sanctioned identity • Vox-verified email required")
    render_banner_once()

    tab_login, tab_create = st.tabs(["Log in", "Create account"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Log in", use_container_width=True):
            ok, user = verify_login(email, password)
            if ok:
                st.session_state["user"] = user
                set_banner(f"Welcome, {user['display_name']}.", kind="success")
                st.rerun()
            else:
                set_banner("Login failed. Check your email/password.", kind="error")
                st.rerun()

    with tab_create:
        email2 = st.text_input("Email", key="create_email")
        name2 = st.text_input("Display name", key="create_name")
        pw2 = st.text_input("Password (min 8 chars)", type="password", key="create_pw")
        if st.button("Create account", use_container_width=True):
            ok, msg = create_user(email2, name2, pw2)
            set_banner(msg, kind="success" if ok else "error")
            st.rerun()

    if "user" in st.session_state:
        st.divider()
        st.write(f"Signed in as **{st.session_state['user']['display_name']}**")
        st.caption(st.session_state["user"]["email"])
        if st.button("Log out"):
            del st.session_state["user"]
            set_banner("Logged out.", kind="info")
            st.rerun()


def page_dashboard():
    title_plate("Campaign Dashboard", "Vox-verified control tallies • Planets & void lanes")
    render_banner_once()

    df = df_territories()
    score = campaign_score(df)

    c1, c2, c3 = st.columns(3)
    c1.metric("Loyalist Score", score["loyalist"])
    c2.metric("Traitor Score", score["traitor"])
    lead = score["lead"]
    c3.metric("Lead", lead, delta=("Loyalist" if lead > 0 else "Traitor" if lead < 0 else "Tied"))

    st.caption("Score weights planets higher than space. Control counts when Held/Secure (|CP| ≥ 3).")

    geom = HexGeom(size=1.0, pointy_top=True)
    fig = make_map(df, geom)
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "scrollZoom": False,          # disables scroll wheel / trackpad zoom.
            "doubleClick": False,         # disables double click zoom reset
            "displayModeBar": False,      # hides the modebar (less accidental taps)
            "responsive": True,
        },
)


    with st.expander("Territories table"):
        show = df.copy()
        show["side"] = show["cp"].apply(side_from_cp)
        show["status"] = show["cp"].apply(status_from_cp)
        st.dataframe(show[["name", "is_planet", "cp", "side", "status", "q", "r"]], use_container_width=True)


def page_rules():
    title_plate("Rules", "Mechanics enforced by the cogitator")
    render_banner_once()

    st.markdown("""
### Control Points (CP)
- Each tile (planet or space) has CP from **-6 to +6**
  - **Positive = Loyalist influence**
  - **Negative = Traitor influence**
- Status:
  - **|CP| ≤ 2** → Contested
  - **3–5** → Held
  - **6** → Secure

### Impact Points (IP)
Base IP:
- **Heresy (30k): 2** (planet)
- **Legions Imperialis: 3** (planet)
- **Adeptus Titanicus: 3** (planet)
- **Gothic Armada: 2** (space)

Crushing win: **×1.5** (rounded, minimum 1)

Draws: **no CP change** (clean, avoids fractional CP)

### Location rules
- Planetary battles must be logged on a **planet**.
- Gothic Armada battles must be logged on a **space tile**.

### Planetary battle effects
- Main IP goes to the planet.
- Optional **+1 splash** to one adjacent space tile.

### Void battle effects (Gothic Armada)
- Main IP goes to the space tile.
- Optional **+1 pressure** to one adjacent planet.

### Planet defense & orbit pressure
- If a planet is **Secure (±6)**, enemy IP is reduced by 1 (minimum 1),
  **unless** the attacker controls at least one adjacent space tile.
- A planet **cannot become Secure (±6)** if the enemy controls **2+ adjacent space tiles**;
  it is capped at **±5** until orbit is relieved.
""")


def page_log_battle():
    title_plate("Log a Battle", "Submit results • Cogitator updates control immediately")
    render_banner_once()
    require_login_stop()

    st.caption("Submit a result and the map updates immediately.")
    #if st.toggle("Auto-refresh this page every 10 seconds", value=False):
    #    st.autorefresh(interval=10_000, key="autorefresh_log")

    df = df_territories()

    battle_type = st.selectbox(
        "Battle type",
        list(BATTLE_TYPES.keys()),
        format_func=lambda k: BATTLE_TYPES[k],
    )

    if battle_type == "gothic_armada":
        st.info("Gothic Armada battles must be logged in a **space** tile.")
        choices = df[df["is_planet"] == 0]
    else:
        st.info("Planetary battles (30k/LI/AT) must be logged on a **planet** tile.")
        choices = df[df["is_planet"] == 1]

    location_name = st.selectbox("Location", choices["name"].tolist())
    loc = choices[choices["name"] == location_name].iloc[0]
    location_id = int(loc["id"])
    loc_q, loc_r = int(loc["q"]), int(loc["r"])

    winning_side = st.radio("Result", ["loyalist", "traitor", "draw"], horizontal=True)
    is_crushing = st.checkbox("Crushing win (major victory)", value=False, disabled=(winning_side == "draw"))
    notes = st.text_area("Notes (optional)")

    # adjacency targets
    c = conn()
    cur = c.cursor()
    neighbor_rows: List[Dict[str, Any]] = []
    for nq, nr in territory_neighbors(loc_q, loc_r):
        row = cur.execute("SELECT id,name,is_planet FROM territories WHERE q=? AND r=?", (nq, nr)).fetchone()
        if row:
            neighbor_rows.append(dict(row))
    c.close()

    splash_space_id = None
    pressure_planet_id = None

    if winning_side != "draw":
        if battle_type == "gothic_armada":
            adj_planets = [t for t in neighbor_rows if int(t["is_planet"]) == 1]
            if adj_planets:
                pick = st.selectbox(
                    "Void pressure target (optional): pick an adjacent planet to apply +1 pressure IP",
                    ["(none)"] + [t["name"] for t in adj_planets],
                )
                if pick != "(none)":
                    pressure_planet_id = int([t for t in adj_planets if t["name"] == pick][0]["id"])
            else:
                st.caption("No adjacent planets → no pressure IP available.")
        else:
            adj_space = [t for t in neighbor_rows if int(t["is_planet"]) == 0]
            if adj_space:
                pick = st.selectbox(
                    "Orbital splash target (optional): pick an adjacent space tile to apply +1 splash IP",
                    ["(none)"] + [t["name"] for t in adj_space],
                )
                if pick != "(none)":
                    splash_space_id = int([t for t in adj_space if t["name"] == pick][0]["id"])
            else:
                st.caption("No adjacent space tiles → no splash IP available.")
    else:
        st.caption("Draw selected → no CP movement, so no splash/pressure applies.")

    st.divider()

    if st.button("Log result", type="primary", use_container_width=True):
        user = st.session_state["user"]
        c = conn()
        try:
            c.execute("BEGIN")

            before_df = pd.read_sql_query("SELECT * FROM territories", c)
            before_score = campaign_score(before_df)

            c.execute(
                """
                INSERT INTO battles(
                    created_at, created_by_user_id, created_by_email,
                    battle_type, location_territory_id,
                    winning_side, is_crushing,
                    splash_target_territory_id, pressure_target_territory_id,
                    notes, status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    utc_now_iso(),
                    int(user["id"]),
                    str(user["email"]),
                    battle_type,
                    location_id,
                    winning_side,
                    1 if is_crushing else 0,
                    splash_space_id,
                    pressure_planet_id,
                    notes,
                    "approved",
                ),
            )

            resolve_battle(
                c,
                battle_type=battle_type,
                location_id=location_id,
                winning_side=winning_side,
                is_crushing=is_crushing,
                splash_space_id=splash_space_id,
                pressure_planet_id=pressure_planet_id,
            )

            after_df = pd.read_sql_query("SELECT * FROM territories", c)
            after_score = campaign_score(after_df)

            c.commit()

            d_loy = after_score["loyalist"] - before_score["loyalist"]
            d_tra = after_score["traitor"] - before_score["traitor"]
            d_lead = after_score["lead"] - before_score["lead"]

            def fmt_delta(x: int) -> str:
                return f"{x:+d}"

            msg = (
                f"Battle logged. Loyalist {fmt_delta(d_loy)} / Traitor {fmt_delta(d_tra)} "
                f"(Lead {fmt_delta(d_lead)}). New score: L{after_score['loyalist']}–T{after_score['traitor']}."
            )
            set_banner(msg, kind="success")
            st.rerun()

        except Exception as e:
            c.rollback()
            set_banner(f"Could not log battle: {e}", kind="error")
            st.rerun()
        finally:
            c.close()


def page_recent_battles():
    title_plate("Recent Battles", "Audit trail • Editable removals with full recalculation")
    render_banner_once()

    require_login_stop()
    current_email = st.session_state["user"]["email"]

    df = df_battles(limit=400)
    if df.empty:
        st.info("No battles logged yet.")
        return

    # Prettify
    show = df.copy()
    show["created_at"] = pd.to_datetime(show["created_at"], errors="coerce")
    show["battle_type"] = show["battle_type"].map(BATTLE_TYPES).fillna(show["battle_type"])
    show["winning_side"] = show["winning_side"].map(SIDE_LABELS).fillna(show["winning_side"])
    show["is_crushing"] = show["is_crushing"].astype(int).astype(bool)
    show.insert(0, "Delete?", False)

    st.caption(
        "To remove battles: tick rows → click **Delete selected & recalculate**. "
        "Only creators can delete their own entries unless you’re listed in ADMIN_EMAILS."
    )

    edited = st.data_editor(
        show[["Delete?", "id", "created_at", "created_by_email", "battle_type", "location_name", "winning_side", "is_crushing", "notes"]],
        use_container_width=True,
        hide_index=True,
        disabled=["id", "created_at", "created_by_email", "battle_type", "location_name", "winning_side", "is_crushing", "notes"],
        column_config={
            "Delete?": st.column_config.CheckboxColumn("Delete?", help="Mark battle for deletion", default=False),
            "id": st.column_config.NumberColumn("ID", format="%d"),
        },
        key="battles_editor",
    )

    to_delete = edited[edited["Delete?"] == True]["id"].tolist()  # noqa: E712

    colA, colB = st.columns([1, 1])
    with colA:
        st.write(f"Marked for deletion: **{len(to_delete)}**")
    with colB:
        confirm = st.checkbox("I understand this will recalculate all CP from remaining battles.", value=False)

    if st.button("Delete selected & recalculate", type="primary", use_container_width=True, disabled=(not to_delete or not confirm)):
        # Permission check per battle
        c = conn()
        try:
            c.execute("BEGIN")

            # Fetch owners for these ids
            qmarks = ",".join(["?"] * len(to_delete))
            rows = c.execute(
                f"SELECT id, created_by_email FROM battles WHERE id IN ({qmarks})",
                tuple(to_delete),
            ).fetchall()

            denied = []
            allowed_ids = []
            for r in rows:
                if can_delete_battle(current_email, r["created_by_email"]):
                    allowed_ids.append(int(r["id"]))
                else:
                    denied.append(int(r["id"]))

            if denied and not allowed_ids:
                c.rollback()
                set_banner(f"Deletion denied for battle IDs: {denied}. You can only delete your own battles.", kind="error")
                st.rerun()

            if denied and allowed_ids:
                # Continue but warn
                set_banner(f"Some deletions denied (IDs: {denied}). Deleting allowed selections and recalculating.", kind="info")

            if allowed_ids:
                qmarks2 = ",".join(["?"] * len(allowed_ids))

                # Score before
                before_df = pd.read_sql_query("SELECT * FROM territories", c)
                before_score = campaign_score(before_df)

                c.execute(f"DELETE FROM battles WHERE id IN ({qmarks2})", tuple(allowed_ids))

                # Recompute CP by replaying battles
                reset_all_cp(c)

                rows2 = c.execute(
                    """
                    SELECT
                      id, battle_type, location_territory_id, winning_side, is_crushing,
                      splash_target_territory_id, pressure_target_territory_id
                    FROM battles
                    WHERE status='approved'
                    ORDER BY id ASC
                    """
                ).fetchall()

                for r in rows2:
                    resolve_battle(
                        c,
                        battle_type=r["battle_type"],
                        location_id=r["location_territory_id"],
                        winning_side=r["winning_side"],
                        is_crushing=bool(int(r["is_crushing"])),
                        splash_space_id=r["splash_target_territory_id"],
                        pressure_planet_id=r["pressure_target_territory_id"],
                    )

                # Score after
                after_df = pd.read_sql_query("SELECT * FROM territories", c)
                after_score = campaign_score(after_df)

                c.commit()

                d_loy = after_score["loyalist"] - before_score["loyalist"]
                d_tra = after_score["traitor"] - before_score["traitor"]
                d_lead = after_score["lead"] - before_score["lead"]

                def fmt_delta(x: int) -> str:
                    return f"{x:+d}"

                msg = (
                    f"Deleted {len(allowed_ids)} battle(s) and recalculated. "
                    f"Loyalist {fmt_delta(d_loy)} / Traitor {fmt_delta(d_tra)} (Lead {fmt_delta(d_lead)}). "
                    f"New score: L{after_score['loyalist']}–T{after_score['traitor']}."
                )
                set_banner(msg, kind="success")
                st.rerun()

            c.commit()
            st.rerun()

        except Exception as e:
            c.rollback()
            set_banner(f"Delete/recalc failed: {e}", kind="error")
            st.rerun()
        finally:
            c.close()


# ============================
# Main
# ============================
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    apply_heresy_style()
    init_db()

    st.title(APP_TITLE)

    with st.sidebar:
        st.subheader("Navigation")
        page = st.radio(
            "Go to",
            ["Dashboard", "Log Battle", "Recent Battles", "Rules", "Account"],
            label_visibility="collapsed",
        )

        st.divider()
        if "user" in st.session_state:
            st.write(f"**Signed in:** {st.session_state['user']['display_name']}")
            st.caption(st.session_state["user"]["email"])
            if admin_emails() and st.session_state["user"]["email"].strip().lower() in admin_emails():
                st.caption("Role: Admin")
        else:
            st.write("**Signed in:** (not yet)")
            st.caption("Create an account to log results.")

        st.divider()
        st.caption("Tip: Set ADMIN_EMAILS to allow campaign admins to delete any battle.")

    if page == "Dashboard":
        page_dashboard()
    elif page == "Log Battle":
        page_log_battle()
    elif page == "Recent Battles":
        page_recent_battles()
    elif page == "Rules":
        page_rules()
    else:
        page_account()


if __name__ == "__main__":
    main()
