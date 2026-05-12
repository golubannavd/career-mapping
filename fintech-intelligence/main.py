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
SECTIONS = ["meta_ads", "websites", "app_store", "news", "recommendations"]

SECTION_LABELS = {
    "meta_ads": "Meta Ads",
    "websites": "Websites",
    "app_store": "App Store",
    "news": "News",
    "recommendations": "Recommendations",
}


class GenerateRequest(BaseModel):
    competitors: list[str] = DEFAULT_COMPETITORS


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    async def event_stream():
        report = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "competitors": req.competitors,
            "sections": {},
            "raw": {},
        }

        # Progress callback for scrapers
        progress_events = asyncio.Queue()

        async def progress_cb(section: str, status: str):
            await progress_events.put((section, status))

        # Run scrapers in background
        scraper_task = asyncio.create_task(
            scrapers.run_all_scrapers(req.competitors, progress_cb)
        )

        # Stream scraper progress
        scraper_sections = ["meta_ads", "websites", "app_store", "news"]
        done_scraping = set()

        while len(done_scraping) < len(scraper_sections):
            try:
                section, status = await asyncio.wait_for(progress_events.get(), timeout=200)
                label = SECTION_LABELS.get(section, section)
                yield f"data: {json.dumps({'phase': 'scraping', 'section': section, 'label': label, 'status': status})}\n\n"
                if status == "done":
                    done_scraping.add(section)
            except asyncio.TimeoutError:
                break

        raw_data = await scraper_task
        report["raw"] = raw_data

        # Analyze each section
        yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'meta_ads', 'label': 'Meta Ads', 'status': 'loading'})}\n\n"
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, analyzer.analyze_meta_ads, raw_data.get("meta_ads", [])
            )
            report["sections"]["meta_ads"] = result
            yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'meta_ads', 'label': 'Meta Ads', 'status': 'done', 'data': result})}\n\n"
        except Exception as e:
            report["sections"]["meta_ads"] = {"error": str(e)}
            yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'meta_ads', 'status': 'error', 'error': str(e)})}\n\n"

        yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'websites', 'label': 'Websites', 'status': 'loading'})}\n\n"
        try:
            result = await loop.run_in_executor(
                None, analyzer.analyze_websites, raw_data.get("websites", [])
            )
            report["sections"]["websites"] = result
            yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'websites', 'label': 'Websites', 'status': 'done', 'data': result})}\n\n"
        except Exception as e:
            report["sections"]["websites"] = {"error": str(e)}
            yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'websites', 'status': 'error', 'error': str(e)})}\n\n"

        yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'app_store', 'label': 'App Store', 'status': 'loading'})}\n\n"
        try:
            result = await loop.run_in_executor(
                None, analyzer.analyze_app_store, raw_data.get("app_store", [])
            )
            report["sections"]["app_store"] = result
            yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'app_store', 'label': 'App Store', 'status': 'done', 'data': result})}\n\n"
        except Exception as e:
            report["sections"]["app_store"] = {"error": str(e)}
            yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'app_store', 'status': 'error', 'error': str(e)})}\n\n"

        yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'news', 'label': 'News', 'status': 'loading'})}\n\n"
        try:
            result = await loop.run_in_executor(
                None, analyzer.analyze_news, raw_data.get("news", [])
            )
            report["sections"]["news"] = result
            yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'news', 'label': 'News', 'status': 'done', 'data': result})}\n\n"
        except Exception as e:
            report["sections"]["news"] = {"error": str(e)}
            yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'news', 'status': 'error', 'error': str(e)})}\n\n"

        yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'recommendations', 'label': 'Recommendations', 'status': 'loading'})}\n\n"
        try:
            result = await loop.run_in_executor(
                None, analyzer.generate_recommendations, report["sections"], req.competitors
            )
            report["sections"]["recommendations"] = result
            yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'recommendations', 'label': 'Recommendations', 'status': 'done', 'data': result})}\n\n"
        except Exception as e:
            report["sections"]["recommendations"] = {"error": str(e)}
            yield f"data: {json.dumps({'phase': 'analyzing', 'section': 'recommendations', 'status': 'error', 'error': str(e)})}\n\n"

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
