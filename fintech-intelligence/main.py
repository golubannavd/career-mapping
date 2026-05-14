import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

import scrapers
import analyzer
import storage

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

DEFAULT_COMPETITORS = ["GCash", "Maya", "Maribank", "Salmon", "Billease", "HomeCredit"]
SECTIONS = ["meta_ads", "websites", "app_store", "news", "social", "recommendations"]

SECTION_LABELS = {
    "meta_ads": "Meta Ads",
    "websites": "Websites",
    "app_store": "App Store",
    "news": "News",
    "social": "Social Media",
    "recommendations": "Recommendations",
}


class GenerateRequest(BaseModel):
    competitors: list[str] = DEFAULT_COMPETITORS


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/api/test")
async def test_claude():
    """Diagnostic endpoint to verify Claude API works."""
    try:
        import anthropic
        c = anthropic.AsyncAnthropic()
        resp = await c.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=50,
            messages=[{"role": "user", "content": "Say: OK"}],
        )
        return {"ok": True, "response": resp.content[0].text}
    except Exception as e:
        import traceback
        return {"ok": False, "error": str(e), "traceback": traceback.format_exc()}


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    async def event_stream():
        report = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "competitors": req.competitors,
            "sections": {},
        }

        # Scraping phase
        progress_events: asyncio.Queue = asyncio.Queue()

        async def progress_cb(section: str, status: str):
            await progress_events.put((section, status))

        scraper_task = asyncio.create_task(
            scrapers.run_all_scrapers(req.competitors, progress_cb)
        )

        scraper_sections = ["meta_ads", "websites", "app_store", "news", "social"]
        done_scraping: set = set()
        while len(done_scraping) < len(scraper_sections):
            try:
                section, status = await asyncio.wait_for(progress_events.get(), timeout=300)
                label = SECTION_LABELS.get(section, section)
                yield f"data: {json.dumps({'phase': 'scraping', 'section': section, 'label': label, 'status': status})}\n\n"
                if status == "done":
                    done_scraping.add(section)
            except asyncio.TimeoutError:
                break

        raw_data = await scraper_task

        # Analysis phase — direct async calls, no thread pool
        analysis_tasks = [
            ("meta_ads", analyzer.analyze_meta_ads(raw_data.get("meta_ads", []))),
            ("websites", analyzer.analyze_websites(raw_data.get("websites", []))),
            ("app_store", analyzer.analyze_app_store(raw_data.get("app_store", []))),
            ("news", analyzer.analyze_news(raw_data.get("news", []))),
            ("social", analyzer.analyze_social_posts(raw_data.get("social", []))),
        ]

        for section_id, coro in analysis_tasks:
            label = SECTION_LABELS[section_id]
            yield f"data: {json.dumps({'phase': 'analyzing', 'section': section_id, 'label': label, 'status': 'loading'})}\n\n"
            try:
                result = await coro
                if section_id == "social":
                    raw_posts = raw_data.get("social", [])
                    result["_raw_posts"] = raw_posts
                    result["_scrape_count"] = len([p for p in raw_posts if not p.get("error")])
                    result["_scrape_errors"] = list({p["error"] for p in raw_posts if p.get("error")})
                report["sections"][section_id] = result
                yield f"data: {json.dumps({'phase': 'analyzing', 'section': section_id, 'label': label, 'status': 'done', 'data': result})}\n\n"
            except Exception as e:
                report["sections"][section_id] = {"error": str(e)}
                yield f"data: {json.dumps({'phase': 'analyzing', 'section': section_id, 'label': label, 'status': 'error', 'error': str(e)})}\n\n"
            await asyncio.sleep(5)  # rate limit buffer between Claude API calls

        # Recommendations
        label = SECTION_LABELS["recommendations"]
        yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'recommendations', 'label': label, 'status': 'loading'})}\n\n"
        try:
            result = await analyzer.generate_recommendations(report["sections"], req.competitors)
            report["sections"]["recommendations"] = result
            yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'recommendations', 'label': label, 'status': 'done', 'data': result})}\n\n"
        except Exception as e:
            report["sections"]["recommendations"] = {"error": str(e)}
            yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'recommendations', 'label': label, 'status': 'error', 'error': str(e)})}\n\n"

        report_id = storage.save_report(report)
        yield f"data: {json.dumps({'status': 'complete', 'report_id': report_id})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/reports")
async def get_reports():
    return storage.list_reports()


@app.get("/api/reports/{report_id}")
async def get_report(report_id: str):
    report = storage.load_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.delete("/api/reports/{report_id}")
async def delete_report(report_id: str):
    if not storage.delete_report(report_id):
        raise HTTPException(status_code=404, detail="Report not found")
    return {"ok": True}
