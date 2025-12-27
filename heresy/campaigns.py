from datetime import datetime, timezone, date
import pandas as pd
import sqlite3

from heresy.db import conn
from heresy.ui import utc_now_iso
from heresy.data import campaign_score, reset_all_cp


def get_active_campaign(c: sqlite3.Connection) -> sqlite3.Row:
    row = c.execute("SELECT * FROM campaigns WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        raise RuntimeError("No active campaign configured.")
    return row


def campaign_has_ended(camp: sqlite3.Row) -> bool:
    end_d = datetime.fromisoformat(camp["end_date"]).date()
    return datetime.now(timezone.utc).date() > end_d


def campaign_time_banner(camp: sqlite3.Row) -> str:
    start = camp["start_date"]
    end = camp["end_date"]
    today = datetime.now(timezone.utc).date()
    end_d = datetime.fromisoformat(end).date()
    remaining = (end_d - today).days
    if camp["status"] != "active" or remaining < 0:
        return f"Campaign ended (ran {start} → {end})."
    return f"Campaign running {start} → {end}. **{remaining} day(s) remaining.**"


def ensure_campaign_status(c: sqlite3.Connection) -> None:
    camp = get_active_campaign(c)
    if camp["status"] != "active":
        return
    if not campaign_has_ended(camp):
        return

    df = pd.read_sql_query("SELECT * FROM territories", c)
    score = campaign_score(df)
    c.execute(
        """
        UPDATE campaigns
        SET status='ended',
            concluded_at=?,
            final_loyalist=?,
            final_traitor=?,
            final_lead=?
        WHERE id=?
        """,
        (utc_now_iso(), score["loyalist"], score["traitor"], score["lead"], int(camp["id"])),
    )
    c.commit()


def admin_reset_campaign(new_name: str, start_date: str, end_date: str) -> None:
    c = conn()
    try:
        c.execute("BEGIN")
        c.execute("UPDATE campaigns SET status='archived' WHERE status='ended'")
        c.execute(
            "INSERT INTO campaigns(name,start_date,end_date,status,created_at) VALUES (?,?,?,?,?)",
            (new_name, start_date, end_date, "active", utc_now_iso()),
        )
        reset_all_cp(c)
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
