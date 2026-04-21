# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Kindlemake** é um crawler web e gerador de EPUB/TXT para coletar capítulos de sites de web novels. Suporta templates de URL customizáveis, cache de capítulos para idempotência, e expõe tanto uma CLI (Typer) quanto uma interface web (Vue 3 + FastAPI) com logs em tempo real via WebSocket.

## Commands

### Backend

```bash
# Instalar dependências
pip install -r requirements.txt

# Servidor de desenvolvimento (com reload automático)
.venv/Scripts/uvicorn ldm_kindler.api:app --reload --port 8000

# Testes
python -m pytest -q

# Teste único
python -m pytest ldm_kindler/tests/test_epub_builder.py -q
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # Vite dev server em http://localhost:5173
npm run build      # Build SPA para frontend/dist/
```

### Desenvolvimento completo (backend + frontend)

```bash
# Windows: executa ambos de uma vez
.\start_dev.bat
```

### CLI

```bash
python -m ldm_kindler.cli run \
  --range-str 1-50 \
  --url-template "https://exemplo.com/capitulo-{id}" \
  --series-title "Minha Série" \
  --author "Autor" \
  --format epub \
  --out ./build
```

## Architecture

### Pipeline principal

```
Input (CLI / Web Form)
  → FastAPI JobRequest → background task
  → FetchClient (throttle + robots.txt + backoff via Tenacity)
  → parse_chapter (CSS selectors → fallback readability-lxml)
  → clean_html (HTML → XHTML normalizado)
  → CacheStore (ldm_kindler/cache/html/ e cache/json/)
  → EpubBuilder / TxtBuilder → arquivo em build/
  → WebSocket stream → LogStream.vue (UI em tempo real)
```

### Módulos principais

- **`ldm_kindler/api.py`** — FastAPI: endpoints REST + WebSocket. Estado em memória (`_jobs`, `_job_queues`); reiniciar o servidor perde o histórico de jobs.
- **`ldm_kindler/cli.py`** — CLI com Typer, usa o mesmo pipeline do backend.
- **`ldm_kindler/crawler/`** — `fetch.py` (HTTP com throttle/backoff), `parse.py` (extração de conteúdo), `clean.py` (sanitização XHTML), `persist.py` (cache).
- **`ldm_kindler/builder/`** — `epub.py`, `txt.py`, `cover.py` (geração de capa com Pillow).
- **`ldm_kindler/constants.py`** — Metadados dos livros, geração de nomes de arquivo.
- **`ldm_kindler/errors.py`** — Códigos de erro padronizados no formato `KM-AREA-NNN`.
- **`frontend/src/stores/jobs.js`** — Pinia store: fetch de jobs, criação, e subscribe via WebSocket.

### Cache e idempotência

Capítulos já em `ldm_kindler/cache/json/{id}.json` pulam fetch e parse. O cache HTML fica em `ldm_kindler/cache/html/{id}.html`.

### Proxy dev (Vite)

Em desenvolvimento, o Vite (`frontend/vite.config.js`) faz proxy de `/api` e `/ws` para `127.0.0.1:8000`. Em produção, a FastAPI serve os arquivos estáticos do `frontend/dist/`.

## REST API

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/api/jobs` | Cria job de crawl (retorna `job_id`) |
| `GET` | `/api/jobs` | Lista todos os jobs |
| `GET` | `/api/jobs/{id}` | Detalhes e logs do job |
| `WS` | `/ws/logs/{id}` | Stream de logs em tempo real |
| `GET` | `/api/library` | Lista arquivos gerados |
| `GET` | `/api/library/{filename}` | Download do arquivo |
