"""
Persistent rule management for PRGI publication title verification.

The JSON file at config/rules_config.json is the single source of truth for
disallowed words, restricted prefixes, and restricted suffix/periodicity terms.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any


CONFIG_DIR = Path(__file__).resolve().parent / "config"
CONFIG_FILE = CONFIG_DIR / "rules_config.json"
CONFIG_PATH_ENV = "PRGI_RULES_CONFIG_PATH"
DEFAULT_DATE = "2026-08-18"

DEFAULT_RULES: dict[str, list[Any]] = {
    "disallowed_words": [
        {"word": "police", "category": "Law Enforcement", "date_added": DEFAULT_DATE},
        {"word": "crime", "category": "Law Enforcement", "date_added": DEFAULT_DATE},
        {"word": "corruption", "category": "Anti-Corruption", "date_added": DEFAULT_DATE},
        {"word": "cbi", "category": "Investigation Agencies", "date_added": DEFAULT_DATE},
        {"word": "cid", "category": "Investigation Agencies", "date_added": DEFAULT_DATE},
        {"word": "army", "category": "Defense & Armed Forces", "date_added": DEFAULT_DATE},
        {"word": "military", "category": "Defense & Armed Forces", "date_added": DEFAULT_DATE},
        {"word": "intelligence", "category": "Investigation Agencies", "date_added": DEFAULT_DATE},
        {"word": "anti-terror", "category": "Defense & Armed Forces", "date_added": DEFAULT_DATE},
        {"word": "encounter", "category": "Law Enforcement", "date_added": DEFAULT_DATE},
        {"word": "emblem", "category": "National Symbols", "date_added": DEFAULT_DATE},
    ],
    "restricted_prefixes": [
        "the",
        "india",
        "new",
        "national",
        "united",
    ],
    "restricted_suffixes": [
        "daily",
        "weekly",
        "monthly",
        "today",
        "live",
        "report",
        "journal",
        "bulletin",
        "update",
        "saptahik",
        "dainik",
        "masik",
    ],
}

_last_error: str | None = None


def _config_path() -> Path:
    override = os.environ.get(CONFIG_PATH_ENV)
    if override:
        return Path(override)
    return CONFIG_FILE


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def _set_error(message: str | None) -> None:
    global _last_error
    _last_error = message


def get_last_error() -> str | None:
    """Return the last non-fatal rule-store error, if any."""
    return _last_error


def _default_rules_copy() -> dict[str, list[Any]]:
    return copy.deepcopy(DEFAULT_RULES)


def _normalize_rules(data: dict[str, Any]) -> dict[str, list[Any]]:
    normalized = _default_rules_copy()

    words: list[dict[str, str]] = []
    seen_words: set[str] = set()
    for item in data.get("disallowed_words", []):
        if isinstance(item, dict):
            word = _normalize_text(item.get("word"))
            category = str(item.get("category") or "Custom").strip() or "Custom"
            date_added = str(item.get("date_added") or DEFAULT_DATE).strip() or DEFAULT_DATE
        else:
            word = _normalize_text(str(item))
            category = "Custom"
            date_added = DEFAULT_DATE
        if word and word not in seen_words:
            words.append({"word": word, "category": category, "date_added": date_added})
            seen_words.add(word)

    prefixes: list[str] = []
    seen_prefixes: set[str] = set()
    for prefix in data.get("restricted_prefixes", []):
        clean = _normalize_text(str(prefix))
        if clean and clean not in seen_prefixes:
            prefixes.append(clean)
            seen_prefixes.add(clean)

    suffixes: list[str] = []
    seen_suffixes: set[str] = set()
    for suffix in data.get("restricted_suffixes", []):
        clean = _normalize_text(str(suffix))
        if clean and clean not in seen_suffixes:
            suffixes.append(clean)
            seen_suffixes.add(clean)

    if words:
        normalized["disallowed_words"] = words
    if prefixes:
        normalized["restricted_prefixes"] = prefixes
    if suffixes:
        normalized["restricted_suffixes"] = suffixes
    return normalized


def _atomic_save(data: dict[str, Any], path: Path | None = None) -> None:
    target = path or _config_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
            json.dump(_normalize_rules(data), temp_file, indent=2, ensure_ascii=False)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_name, target)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _load_rules() -> dict[str, list[Any]]:
    path = _config_path()
    if not path.exists():
        defaults = _default_rules_copy()
        try:
            _atomic_save(defaults, path)
            _set_error(None)
        except OSError as exc:
            _set_error(f"Could not create rules configuration: {exc}")
        return defaults

    try:
        with path.open("r", encoding="utf-8") as rules_file:
            data = json.load(rules_file)
        if not isinstance(data, dict):
            raise ValueError("rules configuration must be a JSON object")
        _set_error(None)
        return _normalize_rules(data)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        if path.exists():
            backup_path = path.with_name(
                f"{path.name}.{datetime.now().strftime('%Y%m%d%H%M%S')}.invalid"
            )
            try:
                shutil.copy2(path, backup_path)
            except OSError:
                pass
        _set_error(f"Could not load rules from {path}: {exc}")
        return _default_rules_copy()


def _save_rules(data: dict[str, Any]) -> bool:
    try:
        _atomic_save(data)
        _set_error(None)
        return True
    except OSError as exc:
        _set_error(f"Could not save rules configuration: {exc}")
        return False


def get_rules() -> dict[str, list[Any]]:
    """Return the complete normalized rule configuration."""
    return _load_rules()


def get_disallowed_words() -> set[str]:
    return {item["word"] for item in _load_rules()["disallowed_words"]}


def get_disallowed_words_detailed() -> list[dict[str, str]]:
    return list(_load_rules()["disallowed_words"])


def add_disallowed_word(word: str, category: str) -> bool:
    clean_word = _normalize_text(word)
    clean_category = str(category or "Custom").strip() or "Custom"
    if not clean_word:
        _set_error("Disallowed word cannot be empty.")
        return False

    data = _load_rules()
    if clean_word in {item["word"] for item in data["disallowed_words"]}:
        _set_error(f"Disallowed word '{clean_word}' already exists.")
        return False

    data["disallowed_words"].append(
        {
            "word": clean_word,
            "category": clean_category,
            "date_added": date.today().isoformat(),
        }
    )
    return _save_rules(data)


def remove_disallowed_word(word: str) -> bool:
    clean_word = _normalize_text(word)
    if not clean_word:
        _set_error("Disallowed word cannot be empty.")
        return False

    data = _load_rules()
    original_count = len(data["disallowed_words"])
    data["disallowed_words"] = [
        item for item in data["disallowed_words"] if item["word"] != clean_word
    ]
    if len(data["disallowed_words"]) == original_count:
        _set_error(f"Disallowed word '{clean_word}' was not found.")
        return False
    return _save_rules(data)


def get_prefixes() -> set[str]:
    return set(_load_rules()["restricted_prefixes"])


def add_prefix(prefix: str) -> bool:
    clean = _normalize_text(prefix)
    if not clean:
        _set_error("Prefix cannot be empty.")
        return False

    data = _load_rules()
    if clean in set(data["restricted_prefixes"]):
        _set_error(f"Prefix '{clean}' already exists.")
        return False
    data["restricted_prefixes"].append(clean)
    return _save_rules(data)


def remove_prefix(prefix: str) -> bool:
    clean = _normalize_text(prefix)
    if not clean:
        _set_error("Prefix cannot be empty.")
        return False

    data = _load_rules()
    if clean not in set(data["restricted_prefixes"]):
        _set_error(f"Prefix '{clean}' was not found.")
        return False
    data["restricted_prefixes"] = [item for item in data["restricted_prefixes"] if item != clean]
    return _save_rules(data)


def get_suffixes() -> set[str]:
    return set(_load_rules()["restricted_suffixes"])


def add_suffix(suffix: str) -> bool:
    clean = _normalize_text(suffix)
    if not clean:
        _set_error("Suffix cannot be empty.")
        return False

    data = _load_rules()
    if clean in set(data["restricted_suffixes"]):
        _set_error(f"Suffix '{clean}' already exists.")
        return False
    data["restricted_suffixes"].append(clean)
    return _save_rules(data)


def remove_suffix(suffix: str) -> bool:
    clean = _normalize_text(suffix)
    if not clean:
        _set_error("Suffix cannot be empty.")
        return False

    data = _load_rules()
    if clean not in set(data["restricted_suffixes"]):
        _set_error(f"Suffix '{clean}' was not found.")
        return False
    data["restricted_suffixes"] = [item for item in data["restricted_suffixes"] if item != clean]
    return _save_rules(data)


def reset_to_defaults() -> bool:
    return _save_rules(_default_rules_copy())


def ensure_config() -> bool:
    """Create the rules configuration file if it is missing."""
    _load_rules()
    return get_last_error() is None


ensure_config()
