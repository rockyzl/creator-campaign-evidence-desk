"""Bounded, read-only requests. User/model inputs never become network URLs."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import time
import httpx


def now():
    return datetime.now(timezone.utc).isoformat()


def fetch_video(row, client=None):
    result = {**row, "title": None, "author_name": None, "author_url": None,
              "http_status": None, "checked_at": now(), "observation_type": "live"}
    own_client = client is None
    client = client or httpx.Client(timeout=15, follow_redirects=False)
    try:
        for attempt in range(2):
            try:
                response = client.get("https://www.youtube.com/oembed", params={
                    "url": "https://www.youtube.com/watch?v=" + row["video_id"], "format": "json"})
                result["http_status"] = response.status_code
                if response.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                    time.sleep(0.3)
                    continue
                if response.status_code == 200:
                    data = response.json()
                    if not isinstance(data, dict) or not isinstance(data.get("title"), str) or not isinstance(data.get("author_name"), str):
                        raise ValueError("Invalid metadata")
                    result.update({k: data.get(k) for k in ("title", "author_name", "author_url")})
                break
            except (httpx.HTTPError, ValueError):
                result["http_status"] = None
                if attempt == 0:
                    time.sleep(0.3)
    finally:
        if own_client:
            client.close()
    return result


def refresh(records):
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(fetch_video, records.rows()))
    for row in rows:
        records.upsert(row)
    return rows
