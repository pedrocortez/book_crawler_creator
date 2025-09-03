### Lorde dos Mistérios – Crawler e Gerador de EPUB

Projeto em Python 3.11+ para coletar capítulos do romance “Lorde dos Mistérios” do site `illusia.com.br`, higienizar o HTML, normalizar em JSON e empacotar livros em EPUB prontos para Kindle.

## Sumário
- **Objetivos**
- **Arquitetura**
- **Instalação**
- **Uso (CLI)**
- **Cache, idempotência e retomada**
- **Regras de ética e robustez**
- **Geração de EPUB**
- **Testes**
- **Estrutura de pastas**

## Objetivos
- **Coletar**: capítulos 441–1394 do site indicado.
- **Normalizar**: salvar HTML bruto e JSON por capítulo, com limpeza para XHTML.
- **Empacotar**: gerar 4 EPUBs nos intervalos requeridos:
  - Livro 7 – Fool (534–680)
  - Livro 8 – Resonance (681–849)
  - Livro 9 – Mystery Pryer (850–1029)
  - Livro 10 – Apocalypse (1030–1394)
- **Observação**: capítulos < 534 são coletáveis para continuidade/validação, mas não entram nos 4 livros.

## Arquitetura
- **crawler/fetch.py**: requests com user‑agent próprio, validação de `robots.txt`, throttle (min/max delay) e backoff exponencial (429/5xx).
- **crawler/parse.py**: extrai título, corpo, prev/next; detecta número do capítulo via regex no título/URL; fallback `readability-lxml`.
- **crawler/clean.py**: higieniza HTML para XHTML simples; normaliza espaços/quebras, remove lixo; adiciona `word_count`, `book`, `volume_title`.
- **crawler/persist.py**: cache idempotente (HTML bruto e JSON normalizado por capítulo).
- **builder/epub.py**: monta EPUB com metadados, TOC, spine, CSS e capa.
- **builder/cover.py**: gera capa simples via Pillow.
- **constants.py**: intervalos dos livros, URL base e nomes de arquivo.
- **cli.py**: CLI (Typer) com opções de faixa, only, delays e dry‑run.
- **tests/**: pytest para regex/clean e estrutura básica do EPUB.

## Instalação
Use PowerShell e venv local.

```powershell
cd C:\Users\pedra\Documents\workspace\kindlemake
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Uso (CLI)
Todos os exemplos assumem a venv ativada acima.

- **Padrão (441–1394, gera EPUBs em ./build)**:
```powershell
.\.venv\Scripts\python.exe -m ldm_kindler.cli run --start 441 --end 1394 --out .\build
```

- **Dry‑run (valida seletores sem salvar)**:
```powershell
.\.venv\Scripts\python.exe -m ldm_kindler.cli run --dry-run --start 441 --end 450
```

- **Somente alguns capítulos**:
```powershell
.\.venv\Scripts\python.exe -m ldm_kindler.cli run --only 534,535,536
```

- **Faixa específica**:
```powershell
.\.venv\Scripts\python.exe -m ldm_kindler.cli run --range-str 850-1029
```

- **Throttle e resiliência**:
```powershell
.\.venv\Scripts\python.exe -m ldm_kindler.cli run --min-delay 2 --max-delay 5 --max-retries 4
```

- **Saídas**:
  - **EPUBs**: `./build`
  - **Cache HTML**: `ldm_kindler/cache/html/`
  - **Cache JSON**: `ldm_kindler/cache/json/`

## Cache, idempotência e retomada
- **Idempotência**: se já existir JSON do capítulo no cache, o capítulo é reutilizado (evita duplicação).
- **Checkpoint**: a cada capítulo normalizado, salva JSON; reexecuções retomam dos faltantes.
- **Auditoria**: HTML bruto salvo para inspeção e futuras re‑normalizações.

## Regras de ética e robustez
- **Respeito a `robots.txt`**: valida acesso antes de coletar.
- **User‑agent**: identificado para uso pessoal/educacional.
- **Throttle + backoff**: atrasos aleatórios (min/max) e retentativas exponenciais em 429/5xx.
- **Sem DRM/paywall**: não há contorno de proteções; uso privado.

## Geração de EPUB
- **Metadados**:
  - `title`: `Lorde dos Mistérios – Livro {NN}: {Nome}`
  - `creator`: `Cuttlefish That Loves Diving (trad. fã)`
  - `language`: `pt-BR`
  - `identifier`: `urn:uuid:{gerado}`
  - `publisher`: `Compilação pessoal – uso privado`
  - `date`: data de geração
- **Capa**: gerada dinamicamente com título, número e faixa (Pillow).
- **TOC & spine**: capítulos em ordem crescente; CSS mínimo para leitura.

## Testes
Rode a suíte (regex/clean/epub):
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Estrutura de pastas
```
ldm_kindler/
  crawler/
    fetch.py          # requests + backoff + robots + headers
    parse.py          # extrai título, corpo, navegação, data
    clean.py          # higieniza HTML -> XHTML simples
    persist.py        # cache HTML, JSON normalizado
  builder/
    epub.py           # monta EPUB, TOC, spine, CSS, capa
    cover.py          # gera capa simples (Pillow)
  cli.py              # Typer (CLI)
  constants.py        # intervalos dos livros, nomes e URL base
  tests/              # pytest
build/                # saídas (EPUBs)
ldm_kindler/cache/html/   # HTML bruto por capítulo
ldm_kindler/cache/json/   # JSON normalizado por capítulo
```

## Notas
- **Fallback de parsing**: `readability-lxml` é usado se os seletores falharem.
- **Bloqueios**: aumente os delays e reduza taxa se encontrar proteções (sem evasão agressiva).
- **Regeneração**: para forçar reprocessamento, remova o JSON do capítulo no cache.
