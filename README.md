### Book Crawler Creator – Crawler e Gerador de EPUB

Projeto em Python 3.11+ para coletar capítulos de romances da web via URL template (com {id}), higienizar o HTML, normalizar em JSON e empacotar saídas em EPUB/TXT.

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
- **Coletar**: capítulos a partir de um template de URL (`--url-template` com `{id}`).
- **Normalizar**: salvar HTML bruto e JSON por capítulo, com limpeza para XHTML.
- **Empacotar**: gerar um arquivo único por execução (EPUB ou TXT) com a faixa escolhida.

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

- **Dry‑run (valida seletores sem salvar)**:
```powershell
.\.venv\Scripts\python.exe -m ldm_kindler.cli --dry-run --start 441 --end 450
```

- **Somente alguns capítulos**:
```powershell
.\.venv\Scripts\python.exe -m ldm_kindler.cli --only 534,535,536
```

- **Faixa específica**:
```powershell
.\.venv\Scripts\python.exe -m ldm_kindler.cli --range-str 850-1029
```

- **Throttle e resiliência**:
```powershell
.\.venv\Scripts\python.exe -m ldm_kindler.cli --min-delay 2 --max-delay 5 --max-retries 4
```

- **Origem via URL template (obrigatório), série e autor**:
```powershell
.\.venv\Scripts\python.exe -m ldm_kindler.cli run ^
  --range-str 1-50 ^
  --url-template "https://exemplo.com/romance/capitulo-{id}" ^
  --series-title "Minha Série" ^
  --author "Autor Desconhecido" ^
  --format epub ^
  --out .\build
```

## Uso (menu .bat)
- Execução guiada por prompts para URL template:
```powershell
./run_book.bat
```
- Informe o `--url-template`, título da série, autor, faixa e formato (EPUB/TXT).

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

## Troubleshooting
- "Got unexpected extra argument (run)" ao usar -m: chame sem o subcomando, ex.: `-m ldm_kindler.cli --range-str 1-50`.
- `ModuleNotFoundError: ldm_kindler` ao rodar arquivo direto: prefira `-m ldm_kindler.cli` ou ajuste `PYTHONPATH`.
- Lentidão/bloqueios: aumente `--min-delay/--max-delay` e mantenha `--max-retries`.
- Windows PowerShell: se aparecer erro com `&&`, use `;` para encadear comandos.

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
