import os

from opensprite.config import Config, NetworkConfig
from opensprite.integrations.network.environment import apply_network_environment


def test_apply_network_environment_sets_proxy_variables(monkeypatch, tmp_path):
    for key in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy"):
        monkeypatch.delenv(key, raising=False)

    config_path = tmp_path / "opensprite.json"
    Config.copy_template(config_path)
    config = Config.from_json(config_path)
    config.network = NetworkConfig(
        http_proxy="http://proxy.local:8080",
        https_proxy="http://proxy.local:8443",
        no_proxy="127.0.0.1,localhost,.internal",
    )

    apply_network_environment(config)

    assert os.environ["HTTP_PROXY"] == "http://proxy.local:8080"
    assert os.environ["http_proxy"] == "http://proxy.local:8080"
    assert os.environ["HTTPS_PROXY"] == "http://proxy.local:8443"
    assert os.environ["https_proxy"] == "http://proxy.local:8443"
    assert os.environ["NO_PROXY"] == "127.0.0.1,localhost,.internal"
    assert os.environ["no_proxy"] == "127.0.0.1,localhost,.internal"


def test_apply_network_environment_preserves_blank_proxy_variables(monkeypatch, tmp_path):
    monkeypatch.setenv("HTTPS_PROXY", "http://old-proxy.local:8443")
    monkeypatch.setenv("https_proxy", "http://old-proxy.local:8443")

    config_path = tmp_path / "opensprite.json"
    Config.copy_template(config_path)
    config = Config.from_json(config_path)
    config.network = NetworkConfig(https_proxy="")

    apply_network_environment(config)

    assert os.environ["HTTPS_PROXY"] == "http://old-proxy.local:8443"
    assert os.environ["https_proxy"] == "http://old-proxy.local:8443"


def test_apply_network_environment_can_clear_blank_proxy_variables(monkeypatch, tmp_path):
    monkeypatch.setenv("HTTPS_PROXY", "http://old-proxy.local:8443")
    monkeypatch.setenv("https_proxy", "http://old-proxy.local:8443")

    config_path = tmp_path / "opensprite.json"
    Config.copy_template(config_path)
    config = Config.from_json(config_path)
    config.network = NetworkConfig(https_proxy="")

    apply_network_environment(config, clear_blank=True)

    assert "HTTPS_PROXY" not in os.environ
    assert "https_proxy" not in os.environ
