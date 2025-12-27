import sqlite3
from typing import List, Tuple, Optional

from heresy.config import CP_MIN, CP_MAX


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
    return {"heresy30k": 2, "legions_imperialis": 3, "adeptus_titanicus": 3, "gothic_armada": 2}[battle_type]


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
        row = cur.execute("SELECT is_planet, cp FROM territories WHERE q=? AND r=?", (nq, nr)).fetchone()
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


def apply_cp_delta(c: sqlite3.Connection, territory_id: int, delta: int, utc_now_iso_fn) -> None:
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

    if is_planet and abs(old_cp) == 6:
        old_s = cp_sign(old_cp)
        d_s = 1 if adjusted_delta > 0 else -1
        if d_s != old_s:
            enemy_s = d_s
            if not enemy_controls_adjacent_space(c, q, r, enemy_s):
                mag = abs(adjusted_delta)
                adjusted_delta = max(1, mag - 1) * d_s

    new_cp = clamp_cp(old_cp + adjusted_delta)

    if is_planet and abs(new_cp) == 6:
        new_s = cp_sign(new_cp)
        enemy_s = -new_s
        hostile_spaces = count_adjacent_enemy_space_control(c, q, r, enemy_s)
        if hostile_spaces >= 2:
            new_cp = 5 * new_s

    cur.execute("UPDATE territories SET cp=?, updated_at=? WHERE id=?", (new_cp, utc_now_iso_fn(), territory_id))


def resolve_battle(
    c: sqlite3.Connection,
    battle_type: str,
    location_id: int,
    winning_side: str,
    is_crushing: bool,
    splash_space_id: Optional[int],
    pressure_planet_id: Optional[int],
    utc_now_iso_fn,
) -> None:
    cur = c.cursor()
    loc = cur.execute("SELECT id,is_planet FROM territories WHERE id=?", (location_id,)).fetchone()
    if not loc:
        raise ValueError("Invalid location territory.")
    loc_is_planet = bool(int(loc["is_planet"]))

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
    apply_cp_delta(c, location_id, main_delta, utc_now_iso_fn)

    if battle_type == "gothic_armada":
        if pressure_planet_id is not None:
            apply_cp_delta(c, pressure_planet_id, 1 * side_sign(winning_side), utc_now_iso_fn)
    else:
        if splash_space_id is not None:
            apply_cp_delta(c, splash_space_id, 1 * side_sign(winning_side), utc_now_iso_fn)
