"""Parameterized SQLite queries over source-attributed public records.

Each run owns its database snapshot. Live observations cannot overwrite another
visitor's evidence or a historical approved report.
"""
import json
import sqlite3
from pathlib import Path

DATA = Path(__file__).parent / "data" / "catalog.json"


def catalog():
    return json.loads(DATA.read_text())


class Records:
    def __init__(self, campaign_id):
        data = catalog()
        self.campaign = next((c for c in data["campaigns"] if c["id"] == campaign_id), None)
        if self.campaign is None:
            raise ValueError("Unknown campaign")
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.execute("CREATE TABLE content(video_id TEXT PRIMARY KEY, title TEXT, author_name TEXT, author_url TEXT, http_status INTEGER, checked_at TEXT, observation_type TEXT, source_url TEXT)")
        for record in data["videos"]:
            if record["campaign_id"] == campaign_id:
                self.upsert(record)

    def upsert(self, row):
        self.db.execute("""INSERT INTO content VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(video_id) DO UPDATE SET title=excluded.title,
            author_name=excluded.author_name,author_url=excluded.author_url,
            http_status=excluded.http_status,checked_at=excluded.checked_at,
            observation_type=excluded.observation_type,source_url=excluded.source_url""",
            tuple(row.get(k) for k in ("video_id", "title", "author_name", "author_url", "http_status", "checked_at", "observation_type", "source_url")))
        self.db.commit()

    def rows(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM content ORDER BY video_id")]

    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM content").fetchone()[0]

    def close(self):
        self.db.close()


LIMITS = {
    "id": "limits",
    "text": "This collection contains a public campaign brief and page-linked YouTube content. It has no contracts, deadlines, creator fees, payments, orders, conversions, audience demographics or private campaign analytics. YouTube oEmbed provides title and publisher metadata, not views or sales. HTTP 200 verifies a metadata response only, not playback, content quality, sponsorship or contractual delivery. HTTP 404 or a request error means metadata was not verified in this check, not proof of deletion, non-delivery or wrongdoing. A page embed is a source-listed association, not a complete roster or proof of a paid partnership. Publishers may be brand channels. Historical campaign totals cannot be recalculated from current oEmbed metadata. Display names alone do not establish identity across platforms.",
    "source_url": "https://developers.google.com/youtube/data/reference/rest/v3/videos/list",
}
