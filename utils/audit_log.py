"""
Filename: audit_log.py
Description: Append-only JSON-lines audit trail with size-based rotation.
    Logging must NEVER break trading: write() never raises and returns
    True/False. Callers pass only explicit fields (never secrets).
"""

import json
import math
import os
from datetime import date, datetime, timezone
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "audit.jsonl"
MAX_STR = 300


def _clean(value, depth=0):
    if depth > 5:
        return "<too deep>"
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k)[:60]: _clean(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v, depth + 1) for v in list(value)[:50]]
    return " ".join(str(value).split())[:MAX_STR]


class AuditLog:
    def __init__(self, path=LOG_FILE, max_bytes=5_000_000, backup_count=5):
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.backup_count = max(1, int(backup_count))

    def _rotate_if_needed(self):
        if not self.path.exists() or self.path.stat().st_size < self.max_bytes:
            return
        for i in range(self.backup_count - 1, 0, -1):
            src = self.path.with_name(f"{self.path.name}.{i}")
            if src.exists():
                os.replace(src, self.path.with_name(f"{self.path.name}.{i + 1}"))
        os.replace(self.path, self.path.with_name(f"{self.path.name}.1"))

    def write(self, event, **fields):
        """Appends one record. Returns True on success, False on any failure."""
        try:
            record = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": str(event)[:60],
            }
            for key, value in fields.items():
                if key not in record:          # ts / event cannot be overridden
                    record[key] = _clean(value)
            line = json.dumps(record, allow_nan=False)

            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_if_needed()
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            return True
        except Exception as e:
            print(f"[AUDIT ERROR] {type(e).__name__}")
            return False


audit = AuditLog()


def audit_event(event, **fields):
    return audit.write(event, **fields)