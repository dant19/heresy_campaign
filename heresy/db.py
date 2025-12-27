import sqlite3
from typing import List, Tuple

from heresy.config import DB_PATH
from heresy.ui import utc_now_iso


def conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


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
        for rr in range(r1, r2 + 1):
            coords.append((q, rr))

    cur = c.cursor()
    for q, r in coords:
        is_planet = 1 if (q, r) in planets else 0
        name = planets.get((q, r), f"Void {q},{r}")
        cur.execute(
            "INSERT INTO territories(q, r, name, is_planet, cp, updated_at) VALUES (?,?,?,?,?,?)",
            (q, r, name, is_planet, 0, now),
        )
    c.commit()


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

        campaign_id INTEGER,

        FOREIGN KEY(created_by_user_id) REFERENCES users(id),
        FOREIGN KEY(location_territory_id) REFERENCES territories(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',  -- active|ended|archived
        concluded_at TEXT,
        final_loyalist INTEGER,
        final_traitor INTEGER,
        final_lead INTEGER,
        created_at TEXT NOT NULL
    )
    """)

    # ensure campaign_id exists if older DB
    cols = [r["name"] for r in cur.execute("PRAGMA table_info(battles)").fetchall()]
    if "campaign_id" not in cols:
        cur.execute("ALTER TABLE battles ADD COLUMN campaign_id INTEGER")
        c.commit()

    # ensure an active campaign exists
    row = cur.execute("SELECT id FROM campaigns WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        cur.execute(
            "INSERT INTO campaigns(name,start_date,end_date,status,created_at) VALUES (?,?,?,?,?)",
            ("Campaign Season 1", "2026-01-01", "2026-03-31", "active", utc_now_iso()),
        )
        c.commit()

    # seed map if empty
    n = int(cur.execute("SELECT COUNT(*) AS n FROM territories").fetchone()["n"])
    if n == 0:
        seed_default_map(c)

    c.close()
