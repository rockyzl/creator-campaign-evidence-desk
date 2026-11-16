"""Durable visitor-scoped reports, optimistic review updates and daily budgets.

GCS object generations prevent lost writes and quota races across instances.
Local development uses atomic file replacement under a process lock.
"""
import json
import os
import threading
from pathlib import Path
from datetime import datetime, timezone


class Conflict(Exception):
    pass


class Store:
    def __init__(self, root=None):
        self.root = Path(root or os.getenv("LOCAL_DATA_DIR", ".local"))
        self.lock = threading.RLock()
        self.bucket_name = os.getenv("REPORT_BUCKET", "") if root is None else ""
        self._bucket = None

    @property
    def bucket(self):
        if self._bucket is None:
            from google.cloud import storage
            self._bucket = storage.Client().bucket(self.bucket_name)
        return self._bucket

    def read(self, key):
        with self.lock:
            if self.bucket_name:
                from google.api_core.exceptions import NotFound, PreconditionFailed
                b = self.bucket.blob(key + ".json")
                for _ in range(4):
                    try:
                        b.reload()
                        generation = int(b.generation)
                        return json.loads(b.download_as_bytes(if_generation_match=generation)), generation
                    except NotFound:
                        return None, 0
                    except PreconditionFailed:
                        continue
                raise Conflict("Record changed; try again")
            p = self.root / (key + ".json")
            if not p.exists():
                return None, 0
            data = json.loads(p.read_text())
            return data["value"], data["generation"]

    def write(self, key, value, generation):
        with self.lock:
            if self.bucket_name:
                from google.api_core.exceptions import PreconditionFailed
                try:
                    self.bucket.blob(key + ".json").upload_from_string(json.dumps(value), content_type="application/json", if_generation_match=generation)
                except PreconditionFailed as e:
                    raise Conflict("Record changed; refresh before reviewing") from e
                return
            _, actual = self.read(key)
            if actual != generation:
                raise Conflict("Record changed; refresh before reviewing")
            p = self.root / (key + ".json")
            p.parent.mkdir(parents=True, exist_ok=True)
            temp = p.with_suffix(".tmp")
            temp.write_text(json.dumps({"generation": generation + 1, "value": value}))
            temp.replace(p)

    def reserve_run(self, session):
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = "budgets/" + day
        for _ in range(6):
            value, generation = self.read(key)
            value = value or {"total": 0, "visitors": {}}
            if value["total"] >= int(os.getenv("DAILY_RUN_LIMIT", "60")) or value["visitors"].get(session, 0) >= 10:
                raise ValueError("Today's live-run allowance has been reached. The example report is still available.")
            value["total"] += 1
            value["visitors"][session] = value["visitors"].get(session, 0) + 1
            try:
                self.write(key, value, generation)
                return
            except Conflict:
                continue
        raise Conflict("The desk is busy. Try again shortly.")

    def save_report(self, session, run):
        self.write("reports/" + session + "/" + run["id"], run, 0)

    def read_report(self, session, run_id):
        return self.read("reports/" + session + "/" + run_id)

    def review(self, session, run_id, decision, note):
        key = "reports/" + session + "/" + run_id
        run, generation = self.read(key)
        if run is None:
            raise KeyError("Report not found in this browser session")
        if run["status"] != "awaiting_review":
            raise Conflict("This report has already been reviewed")
        if decision == "approved" and not run["checks"]["passed"]:
            raise ValueError("This report did not pass its evidence checks")
        run["status"] = decision
        run["review"] = {"decision": decision, "note": note, "reviewed_at": datetime.now(timezone.utc).isoformat(), "reviewer": "Demo visitor"}
        self.write(key, run, generation)
        return run
