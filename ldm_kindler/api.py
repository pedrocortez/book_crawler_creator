"""FastAPI server expondo crawling, biblioteca e logs em tempo real."""
from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator, model_validator

from ldm_kindler.errors import (
    ErrorCode,
    LOGGER_NAME,
    api_error_body,
    get_logger,
    log_error,
)

_log = get_logger(f"{LOGGER_NAME}.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=True,
    )
    _log.info("API iniciada (Kindlemake).")
    yield
    _log.info("API encerrando.")


app = FastAPI(title="Kindlemake API", version="1.0.0", lifespan=lifespan)

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


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    log_error(
        _log,
        ErrorCode.API_VALIDATION_FAILED,
        "Validação da requisição falhou",
        extra={"path": str(request.url.path), "errors": exc.errors()},
    )
    return JSONResponse(
        status_code=422,
        content=api_error_body(
            ErrorCode.API_VALIDATION_FAILED,
            "Dados da requisição inválidos.",
            errors=exc.errors(),
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Garante JSON com código mesmo em falhas inesperadas (evita corpo vazio no cliente).

    HTTPException e RequestValidationError têm handlers mais específicos e não entram aqui.
    """
    log_error(
        _log,
        ErrorCode.API_INTERNAL,
        "Exceção não tratada",
        extra={"path": str(request.url.path)},
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content=api_error_body(
            ErrorCode.API_INTERNAL,
            "Erro interno inesperado. Confira o terminal do uvicorn para o traceback.",
        ),
    )


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

    @field_validator("start", "end")
    @classmethod
    def positive_chapters(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Número de capítulo deve ser >= 1")
        return v

    @model_validator(mode="after")
    def range_ok(self) -> "JobRequest":
        if self.end < self.start:
            raise ValueError("O capítulo final deve ser maior ou igual ao inicial")
        return self


# ── Helpers ────────────────────────────────────────────────────────────────────
def _emit(
    job_id: str,
    level: str,
    message: str,
    *,
    error_code: Optional[str] = None,
    **extra: Any,
) -> None:
    """Publica evento de log para o job especificado."""
    event: Dict[str, Any] = {
        "level": level,
        "message": message,
        "ts": datetime.utcnow().isoformat(),
        **extra,
    }
    if error_code is not None:
        event["error_code"] = error_code
    if job_id in _job_queues:
        try:
            _job_queues[job_id].put_nowait(event)
        except asyncio.QueueFull:
            log_error(
                _log,
                ErrorCode.API_INTERNAL,
                "Fila de logs do job cheia; evento descartado",
                extra={"job_id": job_id},
            )
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

    _log.info("Job id=%s iniciado (capítulos %s–%s)", job_id, req.start, req.end)

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

    try:
        for idx, cid in enumerate(chapter_ids, start=1):
            try:
                _emit(job_id, "INFO", f"({idx}/{total}) fetch cid={cid}", chapter=cid, progress=idx, total=total)
                await asyncio.sleep(0)

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
                    _emit(
                        job_id,
                        "WARN",
                        f"ID mismatch cid={cid} parsed={parsed_id}",
                        chapter=cid,
                        status="chapter_id_mismatch",
                    )
                    if req.strict_ids:
                        _jobs[job_id]["progress"] = idx
                        continue
                    parsed["id"] = cid

                cleaned = clean_html(parsed)
                cache.save_json(cid, cleaned)
                _emit(job_id, "OK", f"({idx}/{total}) done cid={cid}", chapter=cid)
                normalized_chapters.append(cleaned)
                _jobs[job_id]["progress"] = idx

            except Exception as e:
                log_error(
                    _log,
                    ErrorCode.JOB_CHAPTER_FAILED,
                    f"Falha ao processar capítulo {cid}",
                    extra={"job_id": job_id},
                    exc_info=e,
                )
                _jobs[job_id]["status"] = "error"
                _emit(
                    job_id,
                    "ERROR",
                    f"Falha ao processar capítulo {cid}: {e}",
                    error_code=ErrorCode.JOB_CHAPTER_FAILED,
                    chapter=cid,
                )
                await _job_queues[job_id].put({"level": "DONE", "message": "job finalizado com erro"})
                return

        if not normalized_chapters:
            _jobs[job_id]["status"] = "error"
            msg = "Nenhum capítulo coletado."
            log_error(_log, ErrorCode.JOB_NO_CHAPTERS, msg, extra={"job_id": job_id})
            _emit(job_id, "ERROR", f"[{ErrorCode.JOB_NO_CHAPTERS}] {msg}", error_code=ErrorCode.JOB_NO_CHAPTERS)
            await _job_queues[job_id].put({"level": "DONE", "message": "job finalizado com erro"})
            return

        fmt = (req.output_format or "epub").lower().strip()
        if fmt not in {"epub", "txt"}:
            _jobs[job_id]["status"] = "error"
            log_error(_log, ErrorCode.JOB_BUILD_FAILED, f"Formato inválido: {fmt}", extra={"job_id": job_id})
            _emit(
                job_id,
                "ERROR",
                f"[{ErrorCode.JOB_BUILD_FAILED}] Formato inválido: {fmt}",
                error_code=ErrorCode.JOB_BUILD_FAILED,
            )
            await _job_queues[job_id].put({"level": "DONE", "message": "job finalizado com erro"})
            return

        by_id = {c["id"]: c for c in normalized_chapters}
        book_meta = {
            "book": 1,
            "title": req.series_title or "Livro",
            "start": min(by_id),
            "end": max(by_id),
        }
        group = [by_id[cid] for cid in sorted(by_id)]

        def _build() -> str:
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
                        log_error(
                            _log,
                            ErrorCode.JOB_COVER_FETCH_FAILED,
                            "Falha ao baixar imagem de capa",
                            extra={"job_id": job_id, "cover_url": req.cover_url},
                            exc_info=e,
                        )
                        _emit(
                            job_id,
                            "WARN",
                            f"Capa não aplicada: {e}",
                            error_code=ErrorCode.JOB_COVER_FETCH_FAILED,
                        )
                epub_builder.build_epub(group, book_meta, cover_bytes=cover_bytes, override_filename=filename)
                return filename
            txt_builder = TxtBuilder(BUILD_DIR, series_title=req.series_title, author=req.author)
            filename = output_txt_filename_single(req.series_title or "Livro", book_meta["start"], book_meta["end"])
            txt_builder.build_txt_single(group, req.series_title or "Livro", book_meta["start"], book_meta["end"])
            return filename

        _emit(job_id, "INFO", f"Gerando arquivo {fmt.upper()}...")
        try:
            output_file = await loop.run_in_executor(None, _build)
        except Exception as e:
            log_error(_log, ErrorCode.JOB_BUILD_FAILED, "Falha ao gerar EPUB/TXT", extra={"job_id": job_id}, exc_info=e)
            _jobs[job_id]["status"] = "error"
            _emit(
                job_id,
                "ERROR",
                f"[{ErrorCode.JOB_BUILD_FAILED}] Erro ao montar o arquivo: {e}",
                error_code=ErrorCode.JOB_BUILD_FAILED,
            )
            await _job_queues[job_id].put({"level": "DONE", "message": "job finalizado com erro"})
            return

        _emit(job_id, "OK", f"Arquivo gerado: {output_file}", filename=output_file)
        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["output_file"] = output_file
        _job_queues[job_id].put_nowait({"level": "DONE", "message": "job concluído", "filename": output_file})

    except Exception as e:
        log_error(_log, ErrorCode.JOB_UNEXPECTED, "Erro inesperado no job", extra={"job_id": job_id}, exc_info=e)
        _jobs[job_id]["status"] = "error"
        _emit(
            job_id,
            "ERROR",
            f"[{ErrorCode.JOB_UNEXPECTED}] {e}",
            error_code=ErrorCode.JOB_UNEXPECTED,
        )
        try:
            await _job_queues[job_id].put({"level": "DONE", "message": "job finalizado com erro"})
        except Exception:
            log_error(_log, ErrorCode.API_INTERNAL, "Não foi possível sinalizar fim do job na fila", extra={"job_id": job_id})


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
    _log.info("Job enfileirado id=%s", job_id)
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
        log_error(_log, ErrorCode.API_JOB_NOT_FOUND, "GET job inexistente", extra={"job_id": job_id})
        raise HTTPException(
            status_code=404,
            detail=api_error_body(ErrorCode.API_JOB_NOT_FOUND, "Job não encontrado."),
        )
    return _jobs[job_id]


# ── WebSocket de logs ──────────────────────────────────────────────────────────
@app.websocket("/ws/logs/{job_id}")
async def ws_logs(websocket: WebSocket, job_id: str):
    if job_id not in _jobs:
        log_error(_log, ErrorCode.WS_JOB_NOT_FOUND, "WebSocket para job inexistente", extra={"job_id": job_id})
        await websocket.close(code=4004)
        return

    await websocket.accept()

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
    try:
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
    except OSError as e:
        log_error(_log, ErrorCode.API_LIBRARY_LIST_FAILED, "Falha ao listar biblioteca", exc_info=e)
        raise HTTPException(
            status_code=500,
            detail=api_error_body(
                ErrorCode.API_LIBRARY_LIST_FAILED,
                "Não foi possível listar os arquivos em build/.",
            ),
        )


@app.get("/api/library/{filename}")
async def download_file(filename: str):
    path = BUILD_DIR / filename
    if not path.exists() or not path.is_file():
        log_error(_log, ErrorCode.API_FILE_NOT_FOUND, "Download inexistente", extra={"filename": filename})
        raise HTTPException(
            status_code=404,
            detail=api_error_body(ErrorCode.API_FILE_NOT_FOUND, "Arquivo não encontrado."),
        )
    try:
        path.resolve().relative_to(BUILD_DIR.resolve())
    except ValueError:
        log_error(_log, ErrorCode.API_PATH_INVALID, "Tentativa de path traversal", extra={"filename": filename})
        raise HTTPException(
            status_code=400,
            detail=api_error_body(ErrorCode.API_PATH_INVALID, "Caminho inválido."),
        )
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=filename)


# ── Servir SPA em produção ─────────────────────────────────────────────────────
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="spa")
