"""FastAPI server expondo crawling, biblioteca e logs em tempo real."""
from __future__ import annotations

import asyncio
import json
import mimetypes
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Kindlemake API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BUILD_DIR = Path("./build")

# ── Estado em memória ──────────────────────────────────────────────────────────
_jobs: Dict[str, Dict[str, Any]] = {}
_job_queues: Dict[str, asyncio.Queue] = {}


# ── Schemas ────────────────────────────────────────────────────────────────────
class JobRequest(BaseModel):
    url_template: str
    start: int
    end: int
    series_title: Optional[str] = "Livro"
    author: Optional[str] = None
    output_format: str = "epub"
    cover_url: Optional[str] = None
    min_delay: float = 2.0
    max_delay: float = 5.0
    max_retries: int = 4
    strict_ids: bool = True


# ── Helpers ────────────────────────────────────────────────────────────────────
def _emit(job_id: str, level: str, message: str, **extra: Any) -> None:
    """Publica evento de log para o job especificado."""
    event = {"level": level, "message": message, "ts": datetime.utcnow().isoformat(), **extra}
    if job_id in _job_queues:
        try:
            _job_queues[job_id].put_nowait(event)
        except asyncio.QueueFull:
            pass
    _jobs[job_id].setdefault("logs", []).append(event)


# ── Runner do crawl em background ─────────────────────────────────────────────
async def _run_job(job_id: str, req: JobRequest) -> None:
    """Executa crawling + build em thread separada, emitindo logs via queue."""
    import requests as http_requests

    from ldm_kindler.builder.epub import EpubBuilder
    from ldm_kindler.builder.txt import TxtBuilder
    from ldm_kindler.constants import ensure_dirs, output_filename_single, output_txt_filename_single
    from ldm_kindler.crawler.clean import clean_html
    from ldm_kindler.crawler.fetch import FetchClient
    from ldm_kindler.crawler.parse import parse_chapter
    from ldm_kindler.crawler.persist import CacheStore

    base = Path(".")
    ensure_dirs(base)
    _jobs[job_id]["status"] = "running"

    chapter_ids = list(range(req.start, req.end + 1))
    total = len(chapter_ids)
    normalized_chapters: List[Dict[str, Any]] = []

    cache = CacheStore(base)
    fetcher = FetchClient(
        min_delay=req.min_delay,
        max_delay=req.max_delay,
        max_retries=req.max_retries,
        url_template=req.url_template,
    )

    loop = asyncio.get_event_loop()

    def _blocking_fetch(cid: int, url: str):
        return fetcher.fetch(cid, url)

    for idx, cid in enumerate(chapter_ids, start=1):
        _emit(job_id, "INFO", f"({idx}/{total}) fetch cid={cid}", chapter=cid, progress=idx, total=total)
        await asyncio.sleep(0)  # yield para eventos de rede

        existing = cache.load_json(cid)
        if existing is not None:
            _emit(job_id, "INFO", f"({idx}/{total}) cache hit cid={cid}", chapter=cid)
            normalized_chapters.append(existing)
            _jobs[job_id]["progress"] = idx
            continue

        url = fetcher.compose_url(cid)
        html = await loop.run_in_executor(None, _blocking_fetch, cid, url)

        if html is None:
            _emit(job_id, "WARN", f"({idx}/{total}) sem HTML cid={cid}", chapter=cid, status="skip_no_html")
            _jobs[job_id]["progress"] = idx
            continue

        cache.save_html(cid, html)
        _emit(job_id, "INFO", f"({idx}/{total}) parse cid={cid}", chapter=cid)

        parsed = parse_chapter(cid, url, html)
        parsed_id = parsed.get("id", cid)
        if parsed_id != cid:
            _emit(job_id, "WARN", f"ID mismatch cid={cid} parsed={parsed_id}", chapter=cid, status="chapter_id_mismatch")
            if req.strict_ids:
                _jobs[job_id]["progress"] = idx
                continue
            parsed["id"] = cid

        cleaned = clean_html(parsed)
        cache.save_json(cid, cleaned)
        _emit(job_id, "OK", f"({idx}/{total}) done cid={cid}", chapter=cid)
        normalized_chapters.append(cleaned)
        _jobs[job_id]["progress"] = idx

    if not normalized_chapters:
        _jobs[job_id]["status"] = "error"
        _emit(job_id, "ERROR", "Nenhum capítulo coletado.")
        _job_queues[job_id].put_nowait({"level": "DONE", "message": "job finalizado com erro"})
        return

    fmt = (req.output_format or "epub").lower().strip()
    by_id = {c["id"]: c for c in normalized_chapters}
    book_meta = {
        "book": 1,
        "title": req.series_title or "Livro",
        "start": min(by_id),
        "end": max(by_id),
    }
    group = [by_id[cid] for cid in sorted(by_id)]

    def _build():
        if fmt == "epub":
            filename = output_filename_single(req.series_title or "Livro", book_meta["start"], book_meta["end"])
            epub_builder = EpubBuilder(BUILD_DIR, series_title=req.series_title, author=req.author)
            cover_bytes = None
            if req.cover_url:
                try:
                    r = http_requests.get(req.cover_url, timeout=30)
                    r.raise_for_status()
                    cover_bytes = r.content
                except Exception as e:
                    _emit(job_id, "WARN", f"Falha ao baixar capa: {e}")
            epub_builder.build_epub(group, book_meta, cover_bytes=cover_bytes, override_filename=filename)
            return filename
        else:
            txt_builder = TxtBuilder(BUILD_DIR, series_title=req.series_title, author=req.author)
            filename = output_txt_filename_single(req.series_title or "Livro", book_meta["start"], book_meta["end"])
            txt_builder.build_txt_single(group, req.series_title or "Livro", book_meta["start"], book_meta["end"])
            return filename

    _emit(job_id, "INFO", f"Gerando arquivo {fmt.upper()}...")
    output_file = await loop.run_in_executor(None, _build)
    _emit(job_id, "OK", f"Arquivo gerado: {output_file}", filename=output_file)

    _jobs[job_id]["status"] = "done"
    _jobs[job_id]["output_file"] = output_file
    _job_queues[job_id].put_nowait({"level": "DONE", "message": "job concluído", "filename": output_file})


# ── Endpoints REST ─────────────────────────────────────────────────────────────
@app.post("/api/jobs", status_code=202)
async def create_job(req: JobRequest):
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "progress": 0,
        "total": req.end - req.start + 1,
        "created_at": datetime.utcnow().isoformat(),
        "request": req.model_dump(),
        "logs": [],
    }
    _job_queues[job_id] = asyncio.Queue(maxsize=2000)
    asyncio.create_task(_run_job(job_id, req))
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs")
async def list_jobs():
    return [
        {k: v for k, v in job.items() if k != "logs"}
        for job in reversed(list(_jobs.values()))
    ]


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return _jobs[job_id]


# ── WebSocket de logs ──────────────────────────────────────────────────────────
@app.websocket("/ws/logs/{job_id}")
async def ws_logs(websocket: WebSocket, job_id: str):
    if job_id not in _jobs:
        await websocket.close(code=4004)
        return

    await websocket.accept()

    # Envia logs já acumulados
    for log in _jobs[job_id].get("logs", []):
        await websocket.send_text(json.dumps(log))

    if _jobs[job_id]["status"] in ("done", "error"):
        await websocket.send_text(json.dumps({"level": "DONE", "message": "job já finalizado"}))
        await websocket.close()
        return

    queue = _job_queues.get(job_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_text(json.dumps(event))
                if event.get("level") == "DONE":
                    break
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"level": "PING"}))
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()


# ── Biblioteca ─────────────────────────────────────────────────────────────────
@app.get("/api/library")
async def list_library():
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(BUILD_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix in {".epub", ".txt"}:
            stat = f.stat()
            files.append({
                "filename": f.name,
                "size": stat.st_size,
                "modified_at": datetime.utcfromtimestamp(stat.st_mtime).isoformat(),
                "format": f.suffix.lstrip("."),
            })
    return files


@app.get("/api/library/{filename}")
async def download_file(filename: str):
    path = BUILD_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    # Impede path traversal
    try:
        path.resolve().relative_to(BUILD_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Caminho inválido")
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=filename)


# ── Servir SPA em produção ─────────────────────────────────────────────────────
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="spa")
