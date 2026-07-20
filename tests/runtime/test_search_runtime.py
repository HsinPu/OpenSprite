import pytest

from opensprite.config.schema import (
    ChannelsConfig,
    Config,
    HistorySearchConfig,
    LLMsConfig,
    StorageConfig,
)
from opensprite.search.sqlite_store import SQLiteSearchStore
from opensprite.search.store_factory import create_history_search_store


def _config(tmp_path, *, storage_type="sqlite", enabled=True, history_top_k=5):
    return Config(
        llm=LLMsConfig(**Config.packaged_llm_flat_dict()),
        agent=Config.load_agent_template_config(),
        storage=StorageConfig(type=storage_type, path=str(tmp_path / "history.db")),
        channels=ChannelsConfig(),
        history_search=HistorySearchConfig(
            enabled=enabled,
            history_top_k=history_top_k,
        ),
    )


def test_history_search_requires_sqlite_storage(tmp_path):
    config = _config(tmp_path, storage_type="memory")

    with pytest.raises(
        ValueError,
        match='history_search requires storage.type="sqlite"',
    ):
        create_history_search_store(config)


def test_history_search_can_be_disabled(tmp_path):
    assert create_history_search_store(_config(tmp_path, enabled=False)) is None


def test_factory_builds_plain_sqlite_fts_store(tmp_path):
    store = create_history_search_store(_config(tmp_path, history_top_k=7))

    assert isinstance(store, SQLiteSearchStore)
    assert store.history_top_k == 7
    assert set(vars(store)) == {
        "path",
        "history_top_k",
        "chunk_size",
        "chunk_overlap",
        "_read_only",
        "_lock",
    }
