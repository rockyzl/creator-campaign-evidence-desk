import pytest
from fastapi.testclient import TestClient
from app.storage import Store, Conflict
import app.main as main


def report(passed=True):
    return {"id": "a" * 32, "status": "awaiting_review", "checks": {"passed": passed}, "review": None}


def test_review_persists_and_cannot_be_replaced(tmp_path):
    store = Store(tmp_path)
    store.save_report("visitor1", report())
    store.review("visitor1", "a"*32, "approved", "Checked the original source.")
    loaded, _ = Store(tmp_path).read_report("visitor1", "a"*32)
    assert loaded["status"] == "approved" and loaded["review"]["note"] == "Checked the original source."
    with pytest.raises(Conflict):
        store.review("visitor1", "a"*32, "follow_up", "Replace decision")
    assert store.read_report("visitor2", "a"*32)[0] is None


def test_failed_checks_cannot_be_approved(tmp_path):
    store = Store(tmp_path)
    store.save_report("visitor1", report(False))
    with pytest.raises(ValueError):
        store.review("visitor1", "a"*32, "approved", "Ignore checks")
    assert store.review("visitor1", "a"*32, "follow_up", "Recheck sources")["status"] == "follow_up"


def test_stale_generation_cannot_overwrite(tmp_path):
    store = Store(tmp_path)
    store.write("item", {"n": 1}, 0)
    _, generation = store.read("item")
    store.write("item", {"n": 2}, generation)
    with pytest.raises(Conflict):
        store.write("item", {"n": 3}, generation)
    assert store.read("item")[0]["n"] == 2


def test_budget_is_durable(tmp_path, monkeypatch):
    monkeypatch.setenv("DAILY_RUN_LIMIT", "2")
    store = Store(tmp_path)
    store.reserve_run("visitor1"); store.reserve_run("visitor2")
    with pytest.raises(ValueError):
        Store(tmp_path).reserve_run("visitor3")


def test_api_session_isolation_and_origin(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "store", Store(tmp_path))
    client = TestClient(main.app)
    assert client.get("/api/runs/" + "a"*32).status_code == 401
    assert client.get("/api/catalog").status_code == 200
    session = client.cookies.get("desk_session")
    main.store.save_report(session, report())
    assert client.get("/api/runs/" + "a"*32).status_code == 200
    other = TestClient(main.app); other.get("/api/catalog")
    assert other.get("/api/runs/" + "a"*32).status_code == 404
    endpoint = "/api/runs/" + "a"*32 + "/review"
    body = {"decision": "approved", "note": "Checked source"}
    assert client.post(endpoint, json=body).status_code == 403
    assert client.post(endpoint, json=body, headers={"X-Desk-Request": "1", "Origin": "https://foreign.example"}).status_code == 403
    assert client.post(endpoint, json=body, headers={"X-Desk-Request": "1"}).status_code == 200
    assert client.post(endpoint, json=body, headers={"X-Desk-Request": "1"}).status_code == 409
