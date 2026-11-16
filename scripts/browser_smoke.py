"""Real browser workflow check. Makes one live model run and demo review."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

p = argparse.ArgumentParser()
p.add_argument("--url", default="http://127.0.0.1:8194")
p.add_argument("--label", default="local")
args = p.parse_args()
errors = []
with sync_playwright() as pw:
    options = {"headless": True}
    if os.getenv("DESK_CHROMIUM_PATH"):
        options["executable_path"] = os.environ["DESK_CHROMIUM_PATH"]
    browser = pw.chromium.launch(**options)
    context = browser.new_context(viewport={"width": 1440, "height": 1100}, reduced_motion="reduce")
    page = context.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(args.url, wait_until="networkidle")
    expect(page.locator(".content-row")).to_have_count(2)
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    # Inspect the rendered controls before using them.
    controls = page.get_by_role("button").all_text_contents()
    assert any("Run agent" in text for text in controls)
    page.get_by_role("button", name="Or explore a saved real run").click()
    expect(page.locator("#report-section")).to_be_visible()
    expect(page.locator("#report-section")).to_contain_text("Saved real run")
    assert page.locator("#review-form").count() == 0
    page.locator('[data-campaign="shield-launch"]').click()
    expect(page.locator(".content-row")).to_have_count(5)
    page.locator('[data-campaign="rtx-students"]').click()
    page.get_by_role("button", name="Run agent").click()
    expect(page.locator("#report-section")).to_be_visible(timeout=180000)
    expect(page.locator("#report-section")).to_contain_text("Awaiting your review")
    expect(page.locator("#review-form")).to_be_visible()
    page.locator("#review-note").fill("Demo verification: checked the source records and kept unavailable metadata distinct from delivery status.")
    page.get_by_role("button", name="Approve report", exact=True).click()
    expect(page.locator(".review-outcome")).to_contain_text("Report approved", timeout=30000)
    run_id = page.evaluate("localStorage.getItem('desk-report-rtx-students')")
    page.reload(wait_until="networkidle")
    expect(page.locator(".review-outcome")).to_contain_text("Report approved", timeout=30000)
    run = context.request.get(args.url + "/api/runs/" + run_id).json()
    assert run["status"] == "approved" and run["review"]["note"].startswith("Demo verification")
    assert run["checks"]["passed"] and run["trace"] and run["model"].startswith("google/")
    assert run["live_refresh"]
    page.locator("#report-section").scroll_into_view_if_needed()
    page.screenshot(path=f"reports/{args.label}-report-desktop.png", full_page=True, timeout=20000)
    page.set_viewport_size({"width": 390, "height": 844})
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    page.screenshot(path=f"reports/{args.label}-report-mobile.png", full_page=True, timeout=20000)
    other = browser.new_context()
    other.request.get(args.url + "/api/catalog")
    isolation = other.request.get(args.url + "/api/runs/" + run_id).status
    assert isolation == 404
    other.close()
    assert not errors, errors
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "url": args.url,
              "real_model": run["model"], "run_id": run_id, "run_seconds": run["seconds"],
              "saved_example_labeled": True, "campaign_switch": True,
              "live_run": True, "review_persisted_after_reload": True,
              "other_visitor_http_status": isolation, "desktop_overflow": False,
              "mobile_overflow": False, "page_errors": errors,
              "live_metadata_http_statuses": [r["http_status"] for r in run["observations"]],
              "tool_calls": [t["tool"] for t in run["trace"]]}
    Path(f"reports/{args.label}-browser-smoke.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    browser.close()
