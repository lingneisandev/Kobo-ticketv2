"""
Storage utility — Linuxx Ticketing
Dev: wmikon
"""
import json
import time
from pathlib import Path

DATA_DIR     = Path(__file__).parent.parent / "data"
CONFIGS_FILE = DATA_DIR / "configs.json"
TICKETS_FILE = DATA_DIR / "tickets.json"


def _ensure():
    DATA_DIR.mkdir(exist_ok=True)


# ── Guild Configs ──────────────────────────────────────────────

def _load_configs() -> dict:
    _ensure()
    if not CONFIGS_FILE.exists():
        return {}
    try:
        return json.loads(CONFIGS_FILE.read_text())
    except Exception:
        return {}


def _save_configs(data: dict):
    _ensure()
    CONFIGS_FILE.write_text(json.dumps(data, indent=2))


def get_config(guild_id: int) -> dict | None:
    return _load_configs().get(str(guild_id))


def set_config(guild_id: int, config: dict):
    all_c = _load_configs()
    all_c[str(guild_id)] = config
    _save_configs(all_c)


# ── Ticket Records ─────────────────────────────────────────────

def _load_tickets() -> dict:
    _ensure()
    if not TICKETS_FILE.exists():
        return {}
    try:
        return json.loads(TICKETS_FILE.read_text())
    except Exception:
        return {}


def _save_tickets(data: dict):
    _ensure()
    TICKETS_FILE.write_text(json.dumps(data, indent=2))


def get_ticket(channel_id: int) -> dict | None:
    return _load_tickets().get(str(channel_id))


def get_user_open_count(guild_id: int, user_id: int) -> int:
    tickets = _load_tickets()
    return sum(
        1 for t in tickets.values()
        if t["guild_id"] == str(guild_id)
        and t["author_id"] == str(user_id)
        and t["status"] == "open"
    )


def next_ticket_number(guild_id: int) -> int:
    tickets = _load_tickets()
    nums = [
        t.get("number", 0) for t in tickets.values()
        if t["guild_id"] == str(guild_id)
    ]
    return (max(nums) if nums else 0) + 1


def create_ticket(channel_id: int, data: dict):
    tickets = _load_tickets()
    tickets[str(channel_id)] = {**data, "status": "open", "created_at": time.time()}
    _save_tickets(tickets)


def update_ticket(channel_id: int, updates: dict):
    tickets = _load_tickets()
    key = str(channel_id)
    if key in tickets:
        tickets[key].update(updates)
        _save_tickets(tickets)


def delete_ticket(channel_id: int):
    tickets = _load_tickets()
    tickets.pop(str(channel_id), None)
    _save_tickets(tickets)
