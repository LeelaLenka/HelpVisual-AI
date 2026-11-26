"""The MongoDB mirror: data written, disk wiped (as on Render's free plan), restart, data back."""
import shutil

import mongomock
import mongomock.gridfs
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.persistence import MongoMirror

mongomock.gridfs.enable_gridfs_integration()


@pytest.fixture
def mongo():
    return mongomock.MongoClient()


def test_files_survive_a_wiped_disk(tmp_path, mongo):
    data = tmp_path / "data"
    (data / "guides").mkdir(parents=True)
    (data / "media" / "g1").mkdir(parents=True)
    (data / "guides" / "g1.json").write_text('{"id": "g1"}')
    (data / "media" / "g1" / "step_1.png").write_bytes(b"\x89PNG" + bytes(range(256)) * 400)  # ~100 kB image
    (data / "users.json").write_text("[]")
    (data / "guides" / "half-written.tmp").write_text("partial")  # temporary files are never mirrored

    mirror = MongoMirror("mongodb://unused", data, client=mongo)
    assert mirror.sync_once() == (3, 0)
    assert mirror.sync_once() == (0, 0)  # nothing changed: nothing uploaded again
    assert mirror.stored_bytes() > 100_000

    shutil.rmtree(data)  # the host restarts with an empty disk
    restored = MongoMirror("mongodb://unused", data, client=mongo)
    assert restored.restore() == 3
    assert (data / "guides" / "g1.json").read_text() == '{"id": "g1"}'
    assert (data / "media" / "g1" / "step_1.png").read_bytes()[:4] == b"\x89PNG"
    assert not (data / "guides" / "half-written.tmp").exists()
    assert restored.sync_once() == (0, 0)  # restored files are not uploaded again


def test_changes_and_deletions_are_mirrored(tmp_path, mongo):
    data = tmp_path / "data"
    data.mkdir()
    (data / "users.json").write_text("[]")
    (data / "kb.json").write_text("{}")
    mirror = MongoMirror("mongodb://unused", data, client=mongo)
    mirror.sync_once()
    (data / "users.json").write_text('[{"email": "demo@helpvisual.local"}]')
    (data / "kb.json").unlink()
    assert mirror.sync_once() == (1, 1)
    assert mongo["helpvisual"]["file_index"].count_documents({}) == 1
    assert len(list(mongo["helpvisual"]["files.files"].find())) == 1  # the replaced and deleted copies are gone

    shutil.rmtree(data)
    MongoMirror("mongodb://unused", data, client=mongo).restore()
    assert (data / "users.json").read_text() == '[{"email": "demo@helpvisual.local"}]'
    assert not (data / "kb.json").exists()


def test_accounts_survive_a_restart_of_the_whole_app(tmp_path, mongo, monkeypatch):
    """End to end: register on one 'Render instance', wipe the disk, start another, sign in."""
    import app.persistence as persistence

    real_init = persistence.MongoMirror.__init__

    def with_mock(self, uri, data_dir, interval=3.0, client=None, database="helpvisual"):
        real_init(self, uri, data_dir, interval=3600, client=mongo, database=database)

    monkeypatch.setattr(persistence.MongoMirror, "__init__", with_mock)
    from app.main import create_app

    data = tmp_path / "data"
    settings = Settings(data_dir=data, mongodb_uri="mongodb://atlas", _env_file=None)
    first = create_app(settings)
    with TestClient(first) as client:  # the context runs start-up and shutdown (final sync)
        assert client.get("/api/health").json()["storage"] == "mongodb"
        r = client.post("/api/auth/register", json={"name": "Demo", "email": "demo@helpvisual.local", "password": "Demo@12345"})
        assert r.status_code in (200, 201)

    shutil.rmtree(data)  # Render's free disk is wiped
    second = create_app(Settings(data_dir=data, mongodb_uri="mongodb://atlas", _env_file=None))
    with TestClient(second) as client:
        r = client.post("/api/auth/login", json={"email": "demo@helpvisual.local", "password": "Demo@12345"})
        assert r.status_code == 200, r.text


def test_without_a_connection_string_nothing_changes(tmp_path):
    from app.main import create_app

    app = create_app(Settings(data_dir=tmp_path / "data", _env_file=None))
    assert app.state.mirror is None
    assert TestClient(app).get("/api/health").json()["storage"] == "local disk"
