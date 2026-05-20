from opensprite.config.schema import LogConfig
import opensprite.utils.log as log_module


def test_setup_log_respects_disabled_config(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(log_module, "_initialized", True)
    monkeypatch.setattr(log_module, "_current_signature", (True, "365 days", "INFO", True, str(tmp_path / "logs")))
    monkeypatch.setattr(log_module.logger, "remove", lambda: calls.append("remove"))
    monkeypatch.setattr(log_module.logger, "add", lambda *args, **kwargs: calls.append("add"))

    log_module.setup_log(LogConfig(enabled=False), console=True, app_home=tmp_path)

    assert calls == ["remove"]
    assert not (tmp_path / "logs").exists()
    assert log_module._current_signature == (False, "365 days", "INFO", True, str(tmp_path / "logs"))


def test_setup_log_reconfigures_level_and_retention(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(log_module, "_initialized", True)
    monkeypatch.setattr(log_module, "_current_signature", (True, "365 days", "INFO", True, str(tmp_path / "logs")))
    monkeypatch.setattr(log_module.logger, "remove", lambda: calls.append(("remove", None, None)))
    monkeypatch.setattr(log_module.logger, "add", lambda *args, **kwargs: calls.append(("add", args, kwargs)))

    log_module.setup_log(LogConfig(enabled=True, retention_days=7, level="debug"), console=False, app_home=tmp_path)

    add_calls = [call for call in calls if call[0] == "add"]
    assert len(add_calls) == 1
    assert (tmp_path / "logs").exists()
    assert add_calls[0][2]["retention"] == "7 days"
    assert add_calls[0][2]["level"] == "DEBUG"
    assert log_module._current_signature == (True, "7 days", "DEBUG", False, str(tmp_path / "logs"))
