from utils.kill_switch import DEFAULT_PATH, is_trading_halted


def test_not_halted_when_file_absent(tmp_path):
    assert is_trading_halted(tmp_path / "KILL_SWITCH") == (False, "OK")


def test_halted_when_file_present(tmp_path):
    f = tmp_path / "KILL_SWITCH"
    f.write_text("")
    halted, reason = is_trading_halted(f)
    assert halted is True and "present" in reason


def test_halted_when_directory_present(tmp_path):
    d = tmp_path / "KILL_SWITCH"
    d.mkdir()
    assert is_trading_halted(d)[0] is True


def test_check_failure_halts():
    class Broken:
        name = "KILL_SWITCH"
        def exists(self):
            raise OSError("disk error")
    halted, reason = is_trading_halted(Broken())
    assert halted is True and "failed" in reason


def test_default_path_is_anchored_to_repo_root():
    assert DEFAULT_PATH.name == "KILL_SWITCH"
    assert (DEFAULT_PATH.parent / "main.py").exists()