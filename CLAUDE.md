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
- **`ldm_kindler/crawler/sources/`** — uma classe por site (`NovelSource`): `illusia.py`, `central_novel.py`; `base.py` tem o contrato e os padrões (layout WordPress/Fictioneer), `__init__.py` o registro e a detecção pelo domínio.
- **`ldm_kindler/builder/`** — `epub.py`, `txt.py`, `cover.py` (geração de capa com Pillow).
- **`ldm_kindler/constants.py`** — Metadados dos livros, geração de nomes de arquivo.
- **`ldm_kindler/errors.py`** — Códigos de erro padronizados no formato `KM-AREA-NNN`.
- **`frontend/src/stores/jobs.js`** — Pinia store: fetch de jobs, criação, e subscribe via WebSocket.

### Fontes (sites)

Todo site usa o mesmo pipeline e as mesmas estratégias do `FetchClient`: URL por template `{id}`, overrides, link "próximo" do capítulo anterior (modo `start_url`), índice da obra e bloqueio de URLs de outra obra. O que muda por site fica numa subclasse de `NovelSource`:

| Método / atributo | Para quê |
|---|---|
| `hosts` | detecção automática pelo domínio do link |
| `derive_template(url)` | link de capítulo → `(template com {id}, id, prefixo da obra)` |
| `normalize_story_prefix(prefix)` | prefixo usado para rejeitar URLs de outra obra |
| `story_index_url(template)` / `parse_index(html, url)` | página da obra → `{id: url}` |
| `chapter_id_from_url` / `chapter_id_from_title` | validação do id (rejeita "próximo" que aponta para extras) |
| `title_selector`, `content_selector`, `prev_selector`, `next_selector`, `content_junk_selectors` | extração do capítulo |

Para adicionar um site: criar `ldm_kindler/crawler/sources/<site>.py` sobrescrevendo só o que difere dos padrões, registrar a instância em `_SOURCES` (`sources/__init__.py`) e adicionar testes com HTML de fixture (ver `tests/test_sources.py`). API (`source` no `JobRequest`, `GET /api/sources`), CLI (`--source`) e o seletor da interface passam a listar o site automaticamente.

### Cache e idempotência

Capítulos já em cache JSON pulam fetch e parse. O cache é isolado por fonte e obra: `ldm_kindler/cache/{json,html}/<fonte>/<host>-<obra>/{id}.{json,html}` (namespace vem de `NovelSource.cache_namespace`). Estatísticas e limpeza (`/api/cache`) contam todas as subpastas.

### Proxy dev (Vite)

Em desenvolvimento, o Vite (`frontend/vite.config.js`) faz proxy de `/api` e `/ws` para `127.0.0.1:8000`. Em produção, a FastAPI serve os arquivos estáticos do `frontend/dist/`.

## REST API

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/sources` | Lista os sites suportados |
| `POST` | `/api/jobs` | Cria job de crawl (retorna `job_id`) |
| `GET` | `/api/jobs` | Lista todos os jobs |
| `GET` | `/api/jobs/{id}` | Detalhes e logs do job |
| `WS` | `/ws/logs/{id}` | Stream de logs em tempo real |
| `GET` | `/api/library` | Lista arquivos gerados |
| `GET` | `/api/library/{filename}` | Download do arquivo |
