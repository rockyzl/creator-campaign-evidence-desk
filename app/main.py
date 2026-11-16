import json
import logging
import os
import queue
import re
import secrets
import threading
from pathlib import Path
from urllib.parse import urlparse
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .catalog import catalog
from .storage import Store, Conflict

app = FastAPI(title="Creator Campaign Evidence Desk")
ROOT = Path(__file__).parent
store = Store()
slots = threading.BoundedSemaphore(2)
log = logging.getLogger("creator_desk")


@app.middleware("http")
async def headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' https://i.ytimg.com; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def session(request):
    value = request.cookies.get("desk_session", "")
    if not re.fullmatch(r"[a-f0-9]{64}", value):
        raise HTTPException(401, "Reload the page to start a demo session.")
    if request.method == "POST":
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            raise HTTPException(403, "Cross-origin write rejected.")
        if request.headers.get("x-desk-request") != "1":
            raise HTTPException(403, "Missing request header.")
    return value


class RunInput(BaseModel):
    campaign_id: Literal["rtx-students", "shield-launch"]
    question: str = Field(min_length=5, max_length=1200)


class ReviewInput(BaseModel):
    decision: Literal["approved", "follow_up"]
    note: str = Field(min_length=1, max_length=1200)


@app.get("/")
def index():
    return FileResponse(ROOT / "static/index.html")


@app.get("/health")
def health():
    return {"ok": True, "version": "0.1.0", "model_provider": "vertex", "durable_store": "gcs" if store.bucket_name else "local", "scope": "process liveness; does not call external services"}


@app.get("/api/catalog")
def get_catalog(request: Request, response: Response):
    value = request.cookies.get("desk_session", "")
    if not re.fullmatch(r"[a-f0-9]{64}", value):
        response.set_cookie("desk_session", secrets.token_hex(32), httponly=True, secure=bool(os.getenv("K_SERVICE")), samesite="strict", max_age=60*60*24*30)
    return catalog()


@app.get("/api/example/{campaign_id}")
def example(campaign_id: Literal["rtx-students", "shield-launch"]):
    p = ROOT / "data" / ("example-" + campaign_id + ".json")
    if not p.exists():
        raise HTTPException(404, "No saved example yet. Run the agent to create a live report.")
    return json.loads(p.read_text())


@app.post("/api/runs")
def run(data: RunInput, request: Request):
    visitor = session(request)
    if not slots.acquire(blocking=False):
        raise HTTPException(429, "Two reports are already running. Try again shortly.")
    try:
        store.reserve_run(visitor)
    except (ValueError, Conflict) as e:
        slots.release()
        raise HTTPException(429, str(e))
    except Exception:
        slots.release()
        log.exception("Budget store unavailable")
        raise HTTPException(503, "Report storage is unavailable. Try again shortly.")
    events = queue.Queue()

    def work():
        try:
            from .agent import Agent
            result = Agent(data.campaign_id, emit=events.put).run(data.question)
            store.save_report(visitor, result)
            events.put({"type": "result", "result": result})
        except Exception as e:
            log.error("Run failed: %s", type(e).__name__)
            events.put({"type": "error", "message": "The report could not be completed. Try again or open the saved example. No report was approved."})
        finally:
            events.put(None)
            slots.release()

    threading.Thread(target=work, daemon=True).start()

    def stream():
        while True:
            try:
                item = events.get(timeout=15)
                if item is None:
                    break
                yield "data: " + json.dumps(item) + "\n\n"
            except queue.Empty:
                yield ": heartbeat\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, request: Request):
    visitor = session(request)
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise HTTPException(404)
    value, _ = store.read_report(visitor, run_id)
    if value is None:
        raise HTTPException(404, "Report not found in this browser session.")
    return value


@app.post("/api/runs/{run_id}/review")
def review(run_id: str, data: ReviewInput, request: Request):
    visitor = session(request)
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise HTTPException(404)
    try:
        return store.review(visitor, run_id, data.decision, data.note)
    except KeyError:
        raise HTTPException(404, "Report not found in this browser session.")
    except Conflict as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
