"""
Source management.
- Built-in sources: defined in config.py, can be disabled but not deleted.
- Custom sources:   stored in sources.json, can be added and deleted.
- Disabled list:    stored in sources.json alongside custom sources.
"""
import json
import logging
from typing import Optional
from pathlib import Path
from config import SITES

logger = logging.getLogger(__name__)
DATA_FILE = Path(__file__).parent / "sources.json"


# ─── Persistence ──────────────────────────────────────────────────────────────

def _load() -> dict:
    if not DATA_FILE.exists():
        return {"custom": [], "disabled": []}
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        # migrate old format (plain list)
        if isinstance(data, list):
            data = {"custom": data, "disabled": []}
        data.setdefault("custom", [])
        data.setdefault("disabled", [])
        return data
    except Exception as e:
        logger.error(f"Failed to load {DATA_FILE}: {e}")
        return {"custom": [], "disabled": []}


def _save(data: dict) -> None:
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ─── Public API ───────────────────────────────────────────────────────────────

def get_all_sites() -> list:
    """All sources (built-in + custom), regardless of enabled state."""
    return SITES + _load()["custom"]


def get_active_sites() -> list:
    """Only enabled sources — used for news fetching."""
    data = _load()
    disabled = set(data["disabled"])
    return [s for s in get_all_sites() if s["name"] not in disabled]


def get_custom_sources() -> list:
    return _load()["custom"]


def get_disabled_names() -> set:
    return set(_load()["disabled"])


def is_builtin(name: str) -> bool:
    return any(s["name"] == name for s in SITES)


def is_disabled(name: str) -> bool:
    return name in get_disabled_names()


def toggle_source(name: str) -> bool:
    """Enable if disabled, disable if enabled. Returns new state (True = enabled)."""
    data = _load()
    if name in data["disabled"]:
        data["disabled"].remove(name)
        _save(data)
        return True   # now enabled
    else:
        data["disabled"].append(name)
        _save(data)
        return False  # now disabled


def add_source(name: str, url: str, rss: Optional[str] = None) -> bool:
    """Add a custom source. Returns False if duplicate."""
    all_sites = get_all_sites()
    if any(s["name"].lower() == name.lower() or s["url"] == url for s in all_sites):
        return False
    data = _load()
    data["custom"].append({"name": name, "url": url, "rss": rss})
    _save(data)
    return True


def delete_source(name: str) -> bool:
    """Delete a custom source. Built-ins cannot be deleted (use toggle instead)."""
    if is_builtin(name):
        return False
    data = _load()
    new_custom = [s for s in data["custom"] if s["name"] != name]
    if len(new_custom) == len(data["custom"]):
        return False
    data["custom"] = new_custom
    # also remove from disabled if was there
    data["disabled"] = [d for d in data["disabled"] if d != name]
    _save(data)
    return True
