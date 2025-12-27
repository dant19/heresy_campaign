import sqlite3
from typing import Dict

import pandas as pd

from heresy.db import conn
from heresy.ui import utc_now_iso
from heresy.rules import status_from_cp, resolve_battle


def reset_all_cp(c: sqlite3.Connection) -> None:
    c.execute("UPDATE territories SET cp=0, updated_at=?", (utc_now_iso(),))


def df_territories() -> pd.DataFrame:
    c = conn()
    df = pd.read_sql_query("SELECT * FROM territories ORDER BY is_planet DESC, name ASC", c)
    c.close()
    return df


def df_battles(campaign_id: int, limit: int = 400) -> pd.DataFrame:
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
        WHERE b.status='approved' AND b.campaign_id=?
        ORDER BY b.id DESC
        LIMIT ?
        """,
        c,
        params=(campaign_id, limit),
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
        pts = (3 if status == "Secure" else 2) if is_planet else (2 if status == "Secure" else 1)
        if cp > 0:
            loyal += pts
        else:
            traitor += pts
    return {"loyalist": loyal, "traitor": traitor, "lead": loyal - traitor}


def recalc_from_battles(campaign_id: int) -> None:
    c = conn()
    try:
        c.execute("BEGIN")
        reset_all_cp(c)

        rows = c.execute(
            """
            SELECT
              battle_type, location_territory_id, winning_side, is_crushing,
              splash_target_territory_id, pressure_target_territory_id
            FROM battles
            WHERE status='approved' AND campaign_id=?
            ORDER BY id ASC
            """,
            (campaign_id,),
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
                utc_now_iso_fn=utc_now_iso,
            )

        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
