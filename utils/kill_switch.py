"""
Filename: kill_switch.py
Description: File-based kill switch. If a file named KILL_SWITCH exists in the
    repo root, trading is halted. Fail-closed: if the check itself errors,
    trading is halted.
      Halt:    New-Item KILL_SWITCH -ItemType File     (PowerShell, repo root)
      Resume:  Remove-Item KILL_SWITCH
"""

from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "KILL_SWITCH"


def is_trading_halted(path=DEFAULT_PATH):
    """Returns (halted: bool, reason: str)."""
    try:
        if path.exists():
            return True, f"kill switch file present ({path.name})"
    except Exception as e:
        return True, f"kill switch check failed ({type(e).__name__}); halting"
    return False, "OK"