import json
from datetime import datetime, timezone

from utils.audit_log import AuditLog


def lines(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def all_lines(path):
    total = 0
    for f in path.parent.glob(path.name + "*"):
        total += len(f.read_text(encoding="utf-8").splitlines())
    return total


def test_writes_one_json_line(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    assert log.write("cycle", outcome="NO_SIGNAL", price=750.5) is True
    rec = lines(tmp_path / "a.jsonl")
    assert len(rec) == 1
    assert rec[0]["event"] == "cycle" and rec[0]["outcome"] == "NO_SIGNAL"
    assert rec[0]["price"] == 750.5


def test_each_record_is_a_separate_valid_json_line(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    for i in range(5):
        log.write("x", n=i)
    assert [r["n"] for r in lines(tmp_path / "a.jsonl")] == [0, 1, 2, 3, 4]


def test_timestamp_is_parseable_utc(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    log.write("x")
    ts = datetime.fromisoformat(lines(tmp_path / "a.jsonl")[0]["ts"])
    assert ts.tzinfo is not None and ts.utcoffset().total_seconds() == 0


def test_datetime_is_iso(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    log.write("x", bar_ts=datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc))
    assert lines(tmp_path / "a.jsonl")[0]["bar_ts"] == "2026-11-16T15:00:00+00:00"


def test_non_finite_floats_become_null(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    assert log.write("x", a=float("nan"), b=float("inf")) is True
    rec = lines(tmp_path / "a.jsonl")[0]
    assert rec["a"] is None and rec["b"] is None


def test_long_strings_are_truncated(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    log.write("x", reason="a" * 1000)
    assert len(lines(tmp_path / "a.jsonl")[0]["reason"]) == 300


def test_newlines_are_collapsed(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    log.write("x", reason="a\nb\r\nc")
    assert lines(tmp_path / "a.jsonl")[0]["reason"] == "a b c"


def test_nested_values_are_cleaned(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    log.write("x", position={"qty": float("nan"), "items": [1, float("inf")]})
    rec = lines(tmp_path / "a.jsonl")[0]
    assert rec["position"] == {"qty": None, "items": [1, None]}


def test_reserved_keys_cannot_be_overridden(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    log.write("real_event", ts="bad")
    rec = lines(tmp_path / "a.jsonl")[0]
    assert rec["ts"] != "bad" and rec["event"] == "real_event"


def test_unserializable_object_becomes_string(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    assert log.write("x", thing=object()) is True
    assert lines(tmp_path / "a.jsonl")[0]["thing"].startswith("<object object")


def test_failure_returns_false_and_does_not_raise(tmp_path):
    log = AuditLog(tmp_path)          # a directory, so opening it for append fails
    assert log.write("x") is False


def test_creates_missing_directory(tmp_path):
    log = AuditLog(tmp_path / "new" / "sub" / "a.jsonl")
    assert log.write("x") is True


def test_rotation_keeps_at_most_backup_count_files(tmp_path):
    path = tmp_path / "a.jsonl"
    log = AuditLog(path, max_bytes=200, backup_count=2)
    for i in range(40):
        log.write("x", n=i, pad="p" * 40)
    assert (tmp_path / "a.jsonl.1").exists()
    assert (tmp_path / "a.jsonl.2").exists()
    assert not (tmp_path / "a.jsonl.3").exists()


def test_rotation_loses_nothing_under_capacity(tmp_path):
    path = tmp_path / "a.jsonl"
    log = AuditLog(path, max_bytes=300, backup_count=5)
    for i in range(6):
        log.write("x", n=i)
    assert all_lines(path) == 6