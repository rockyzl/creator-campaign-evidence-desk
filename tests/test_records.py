import httpx
import pytest
from app.catalog import Records
from app.sources import fetch_video
from app.agent import mechanical_checks


def test_repeat_import_preserves_unique_video_identity():
    db = Records("rtx-students")
    rows = db.rows()
    for _ in range(3):
        for row in rows:
            db.upsert(row)
    assert db.count() == 2
    db.close()


def test_campaigns_have_disjoint_content():
    a, b = Records("rtx-students"), Records("shield-launch")
    assert not {r["video_id"] for r in a.rows()} & {r["video_id"] for r in b.rows()}
    a.close(); b.close()
    with pytest.raises(ValueError):
        Records("unknown")


def test_failed_refresh_does_not_keep_old_metadata_as_live():
    row = Records("rtx-students").rows()[0]
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404)))
    result = fetch_video(row, client)
    assert result["http_status"] == 404
    assert result["title"] is None and result["author_name"] is None
    assert result["observation_type"] == "live"


def test_transient_failure_is_retried_once():
    calls = []
    def response(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"title": "Test metadata", "author_name": "Test publisher", "author_url": "https://www.youtube.com/@test"})
    result = fetch_video(Records("rtx-students").rows()[0], httpx.Client(transport=httpx.MockTransport(response)))
    assert len(calls) == 2 and result["http_status"] == 200
    assert all(r.url.host == "www.youtube.com" for r in calls)


def test_unreturned_citation_fails_checks():
    report = {"findings": [{"evidence_ids": ["invented"]}]}
    assert mechanical_checks(report, [{"id": "brief"}], ["read_campaign", "list_public_content", "read_data_limits"])


def test_malformed_success_response_is_unverified():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[])))
    result = fetch_video(Records("rtx-students").rows()[0], client)
    assert result["http_status"] is None and result["title"] is None


def test_missing_required_context_fails_checks():
    assert mechanical_checks({"findings": [{"evidence_ids": ["brief"]}]}, [{"id": "brief"}], ["read_campaign"])
