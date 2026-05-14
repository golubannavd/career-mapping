import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

import research
import storage

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

DEFAULT_COMPETITORS = ["GCash", "Maya", "Maribank", "Salmon", "Billease", "HomeCredit", "Gotyme"]
SECTIONS = ["news", "competitor", "social", "press", "messaging", "strategy"]


class GenerateRequest(BaseModel):
    competitors: list[str] = DEFAULT_COMPETITORS
    sections: list[str] = SECTIONS


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    async def event_stream():
        digest = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "competitors": req.competitors,
            "sections": {},
        }

        for section_id in req.sections:
            if section_id not in research.PROMPTS:
                continue

            yield f"data: {json.dumps({'section': section_id, 'status': 'loading'})}\n\n"
            await asyncio.sleep(0)  # flush

            try:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(
                    None, research.research_section, section_id, req.competitors
                )
                digest["sections"][section_id] = data
                yield f"data: {json.dumps({'section': section_id, 'status': 'done', 'data': data})}\n\n"
            except Exception as e:
                digest["sections"][section_id] = {"error": str(e)}
                yield f"data: {json.dumps({'section': section_id, 'status': 'error', 'error': str(e)})}\n\n"

            await asyncio.sleep(0)

        digest_id = storage.save_digest(digest)
        yield f"data: {json.dumps({'status': 'complete', 'digest_id': digest_id})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/digests")
async def get_digests():
    return storage.list_digests()


@app.get("/api/digests/{digest_id}")
async def get_digest(digest_id: str):
    digest = storage.load_digest(digest_id)
    if digest is None:
        raise HTTPException(status_code=404, detail="Digest not found")
    return digest


@app.delete("/api/digests/{digest_id}")
async def delete_digest(digest_id: str):
    if not storage.delete_digest(digest_id):
        raise HTTPException(status_code=404, detail="Digest not found")
    return {"ok": True}
