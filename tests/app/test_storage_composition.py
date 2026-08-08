"""Application storage composition tests."""

from types import SimpleNamespace

from opensprite.app.storage import create_storage
from opensprite.integrations.persistence.sqlite.storage import SQLiteStorage


def test_storage_factory_builds_canonical_sqlite_adapter(tmp_path):
    db_path = tmp_path / "factory.db"
    config = SimpleNamespace(storage=SimpleNamespace(type="sqlite", path=str(db_path)))

    storage = create_storage(config)

    assert type(storage) is SQLiteStorage
    assert storage.db_path == db_path
    assert db_path.is_file()
