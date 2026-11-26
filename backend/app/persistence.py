"""Keeps the data folder safe on hosts whose disk is wiped on restart (such as Render's free plan).

The application stores everything as files under data/ (guides, accounts, images, knowledge base,
events, settings). This module mirrors that folder into MongoDB (for example a free MongoDB Atlas
cluster), so nothing else in the application changes:

- restore(): at start-up, every stored file is written back into data/;
- sync_once(): new and changed files are uploaded (GridFS, so large images are fine) and files
  deleted locally are deleted in MongoDB; a background thread runs it every few seconds;
- stop(): a final sync when the server shuts down.

A file is uploaded only when its content changed (SHA-1), not just its timestamp. Writes made in the
last few seconds before a hard crash can be lost; a normal shutdown or sleep runs a final sync.
"""
from __future__ import annotations

import hashlib
import logging
import threading
from pathlib import Path

log = logging.getLogger("helpvisual.persistence")
SKIP_SUFFIXES = (".tmp", ".lock", ".part")


class MongoMirror:
    def __init__(self, uri: str, data_dir: Path, interval: float = 3.0, client=None, database: str = "helpvisual"):
        import gridfs
        from pymongo import MongoClient

        self.client = client or MongoClient(uri, serverSelectionTimeoutMS=15000)
        try:
            db = self.client.get_default_database()
        except Exception:  # the URI names no database
            db = self.client[database]
        self.db = db
        self.fs = gridfs.GridFS(db, collection="files")
        self.index = db["file_index"]  # one document per file: _id = path inside data/, sha1, size, file_id
        self.data_dir = Path(data_dir)
        self.interval = interval
        self._seen: dict[str, tuple[int, int, str]] = {}  # path -> (size, mtime_ns, sha1) as last synced
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def _files(self):
        for path in self.data_dir.rglob("*"):
            if path.is_file() and not path.name.endswith(SKIP_SUFFIXES):
                yield path.relative_to(self.data_dir).as_posix(), path

    def restore(self) -> int:
        """Writes every stored file into data/. Returns how many files were restored."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for doc in self.index.find():
            target = self.data_dir / doc["_id"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.fs.get(doc["file_id"]).read())
            stat = target.stat()
            self._seen[doc["_id"]] = (stat.st_size, stat.st_mtime_ns, doc["sha1"])
            count += 1
        log.info("Restored %d files from MongoDB", count)
        return count

    def sync_once(self) -> tuple[int, int]:
        """Uploads changed files and removes deleted ones. Returns (uploaded, deleted)."""
        with self._lock:
            uploaded = deleted = 0
            present = set()
            for rel, path in self._files():
                present.add(rel)
                try:
                    stat = path.stat()
                except FileNotFoundError:
                    continue
                known = self._seen.get(rel)
                if known and known[0] == stat.st_size and known[1] == stat.st_mtime_ns:
                    continue  # unchanged since the last sync
                data = path.read_bytes()
                sha1 = hashlib.sha1(data).hexdigest()
                if known and known[2] == sha1:
                    self._seen[rel] = (stat.st_size, stat.st_mtime_ns, sha1)  # touched, same content
                    continue
                old = self.index.find_one({"_id": rel})
                file_id = self.fs.put(data, filename=rel)
                self.index.replace_one({"_id": rel}, {"_id": rel, "sha1": sha1, "size": len(data), "file_id": file_id},
                                       upsert=True)
                if old:
                    self.fs.delete(old["file_id"])
                self._seen[rel] = (stat.st_size, stat.st_mtime_ns, sha1)
                uploaded += 1
            for rel in [r for r in self._seen if r not in present]:
                old = self.index.find_one({"_id": rel})
                if old:
                    self.index.delete_one({"_id": rel})
                    self.fs.delete(old["file_id"])
                del self._seen[rel]
                deleted += 1
            if uploaded or deleted:
                log.info("MongoDB sync: %d uploaded, %d deleted", uploaded, deleted)
            return uploaded, deleted

    def stored_bytes(self) -> int:
        return sum(d.get("size", 0) for d in self.index.find({}, {"size": 1}))

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.sync_once()
            except Exception:  # keep the server running; the next round retries
                log.exception("MongoDB sync failed; retrying")

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="mongo-mirror", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            self.sync_once()
        except Exception:
            log.exception("Final MongoDB sync failed")
