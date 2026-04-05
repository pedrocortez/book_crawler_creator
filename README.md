### Book Crawler Creator – Crawler, Gerador de EPUB e Interface Web

Projeto em Python 3.11+ para coletar capítulos de romances da web via URL template (com `{id}`), higienizar o HTML, normalizar em JSON e empacotar saídas em EPUB/TXT. Conta agora com uma **interface web moderna** (Vue 3 + FastAPI) para operar tudo via navegador.

## Sumário
- **Objetivos**
- **Arquitetura**
- **Instalação**
- **Interface Web (recomendado)**
- **Uso (CLI)**
- **Cache, idempotência e retomada**
- **Regras de ética e robustez**
- **Geração de EPUB**
- **Testes**
- **Estrutura de pastas**

## Objetivos
- **Coletar**: capítulos a partir de um template de URL (`--url-template` com `{id}`).
- **Normalizar**: salvar HTML bruto e JSON por capítulo, com limpeza para XHTML.
- **Empacotar**: gerar um arquivo único por execução (EPUB ou TXT) com a faixa escolhida.
- **Visualizar**: acompanhar jobs, logs em tempo real e gerenciar a biblioteca via interface web.

## Arquitetura

```
┌──────────────────────────────────┐
│   Interface Web (Vue 3 + Vite)   │
│  CrawlView · JobView · Library   │
└──────────┬────────────┬──────────┘
           │ REST       │ WebSocket
┌──────────▼────────────▼──────────┐
│        FastAPI (api.py)          │
│  POST /api/jobs  GET /api/library│
│  WS   /ws/logs/{job_id}         │
└──────────────────┬───────────────┘
                   │ asyncio tasks
┌──────────────────▼───────────────┐
│         ldm_kindler (core)       │
│  crawler/  ·  builder/  ·  cli  │
└──────────────────────────────────┘
```

- **crawler/fetch.py** — requests com user‑agent próprio, validação de `robots.txt`, throttle (min/max delay) e backoff exponencial (429/5xx).
- **crawler/parse.py** — extrai título, corpo, prev/next; detecta número do capítulo via regex; fallback `readability-lxml`.
- **crawler/clean.py** — higieniza HTML para XHTML simples; normaliza espaços/quebras; adiciona `word_count`.
- **crawler/persist.py** — cache idempotente (HTML bruto e JSON normalizado por capítulo).
- **builder/epub.py** — monta EPUB com metadados, TOC, spine, CSS e capa.
- **builder/cover.py** — gera capa simples via Pillow.
- **api.py** — servidor FastAPI com endpoints REST, WebSocket de logs e serve o frontend em produção.
- **cli.py** — CLI (Typer) para uso direto no terminal.

## Instalação

```powershell
cd C:\Users\pedra\Documents\workspace\kindlemake
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Instalar dependências do frontend (necessário apenas uma vez):

```powershell
cd frontend
npm install
```

## Interface Web (recomendado)

### Modo desenvolvimento

Execute o script de atalho na raiz do projeto:

```powershell
.\start_dev.bat
```

Ou inicie manualmente em dois terminais:

```powershell
# Terminal 1 – backend
.\.venv\Scripts\uvicorn ldm_kindler.api:app --reload --port 8000

# Terminal 2 – frontend
cd frontend
npm run dev
```

Acesse **http://localhost:5173** no navegador.

### Modo produção (frontend embutido no backend)

```powershell
cd frontend
npm run build

# Servir tudo pelo FastAPI
.\.venv\Scripts\uvicorn ldm_kindler.api:app --port 8000
```

Acesse **http://localhost:8000**.

### Telas disponíveis

| Tela | Descrição |
|---|---|
| **Crawl** | Formulário completo para iniciar um novo job de coleta |
| **Jobs** | Lista de todos os jobs com status e progresso |
| **Job detalhe** | Barra de progresso, console de logs em tempo real (WebSocket) e download do arquivo |
| **Biblioteca** | Grid de EPUBs/TXTs gerados com filtro por formato e download direto |

### API REST

| Método | Endpoint | Descrição |
|---|---|---|
| `POST` | `/api/jobs` | Inicia um crawl em background |
| `GET` | `/api/jobs` | Lista todos os jobs |
| `GET` | `/api/jobs/{id}` | Detalhe e logs de um job |
| `WS` | `/ws/logs/{id}` | Stream de logs em tempo real |
| `GET` | `/api/library` | Lista arquivos gerados |
| `GET` | `/api/library/{filename}` | Download do arquivo |

## Uso (CLI)

Todos os exemplos assumem a venv ativada.

- **Faixa específica com URL template**:
```powershell
.\.venv\Scripts\python.exe -m ldm_kindler.cli run `
  --range-str 1-50 `
  --url-template "https://exemplo.com/romance/capitulo-{id}" `
  --series-title "Minha Série" `
  --author "Autor Desconhecido" `
  --format epub `
  --out .\build
```

- **Dry‑run (valida sem salvar)**:
```powershell
.\.venv\Scripts\python.exe -m ldm_kindler.cli --dry-run --start 441 --end 450
```

- **Somente capítulos específicos**:
```powershell
.\.venv\Scripts\python.exe -m ldm_kindler.cli --only 534,535,536
```

- **Execução guiada (.bat)**:
```powershell
.\run_book.bat
```

**Saídas:**
- EPUBs/TXTs: `./build`
- Cache HTML: `ldm_kindler/cache/html/`
- Cache JSON: `ldm_kindler/cache/json/`

## Cache, idempotência e retomada
- **Idempotência**: capítulos já normalizados em JSON são reutilizados sem novo fetch.
- **Checkpoint**: a cada capítulo processado, o JSON é salvo; reexecuções retomam apenas os faltantes.
- **Auditoria**: HTML bruto mantido para inspeção e futuras re‑normalizações.

## Regras de ética e robustez
- **Respeito a `robots.txt`**: valida acesso antes de coletar.
- **User‑agent**: identificado para uso pessoal/educacional.
- **Throttle + backoff**: atrasos aleatórios (min/max) e retentativas exponenciais em 429/5xx.
- **Sem DRM/paywall**: não há contorno de proteções; uso privado.

## Geração de EPUB
- **Metadados**: título, autor, idioma `pt-BR`, UUID, publisher e data de geração.
- **Capa**: gerada dinamicamente com título, número e faixa (Pillow).
- **TOC & spine**: capítulos em ordem crescente; CSS mínimo para leitura.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Troubleshooting
- `&&` no PowerShell: use `;` para encadear comandos.
- `ModuleNotFoundError: ldm_kindler`: use `-m ldm_kindler.cli` em vez de chamar o arquivo diretamente.
- Lentidão/bloqueios: aumente `--min-delay/--max-delay` e mantenha `--max-retries`.
- WebSocket não conecta em dev: verifique se o backend está rodando na porta 8000.

## Estrutura de pastas

```
kindlemake/
├── ldm_kindler/
│   ├── api.py            # FastAPI – REST + WebSocket
│   ├── cli.py            # Typer (CLI)
│   ├── constants.py      # intervalos, nomes e URL base
│   ├── crawler/
│   │   ├── fetch.py      # requests + backoff + robots + headers
│   │   ├── parse.py      # extrai título, corpo, navegação
│   │   ├── clean.py      # higieniza HTML → XHTML
│   │   └── persist.py    # cache HTML e JSON
│   └── builder/
│       ├── epub.py       # monta EPUB, TOC, spine, CSS, capa
│       ├── txt.py        # gera TXT simples
│       └── cover.py      # gera capa (Pillow)
├── frontend/
│   ├── src/
│   │   ├── views/        # CrawlView, JobView, LibraryView
│   │   ├── components/   # LogStream, FileCard
│   │   ├── stores/       # Pinia (jobs)
│   │   └── App.vue
│   ├── vite.config.js
│   └── package.json
├── build/                # EPUBs/TXTs gerados
├── requirements.txt
├── start_dev.bat         # atalho para iniciar backend + frontend
└── run_book.bat          # CLI guiado por prompts
```

## Notas
- **Fallback de parsing**: `readability-lxml` é usado se os seletores falharem.
- **Regeneração**: para forçar reprocessamento, remova o JSON do capítulo em `cache/json/`.
- **Produção**: `npm run build` gera `frontend/dist/`; o FastAPI serve como SPA estática.
