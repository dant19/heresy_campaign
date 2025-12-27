import streamlit as st
from heresy.ui import title_plate, render_banner_once


def render():
    title_plate("Rules", "Mechanics enforced by the cogitator")
    render_banner_once()

    st.markdown(
        """
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

Draws: **no CP change**

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
"""
    )
