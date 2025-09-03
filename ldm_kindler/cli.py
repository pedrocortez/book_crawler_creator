from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional
from io import BytesIO
import requests

import typer
from rich.progress import Progress

from ldm_kindler.constants import BOOKS, ensure_dirs
from ldm_kindler.crawler.fetch import FetchClient
from ldm_kindler.crawler.parse import parse_chapter
from ldm_kindler.crawler.clean import clean_html
from ldm_kindler.crawler.persist import CacheStore
from ldm_kindler.builder.epub import EpubBuilder
from ldm_kindler.constants import output_filename_single


app = typer.Typer(help="Crawler e gerador de EPUB para 'Lorde dos Mistérios'.")


def parse_only_list(only: Optional[str]) -> Optional[List[int]]:
    if not only:
        return None
    return [int(x.strip()) for x in only.split(",") if x.strip()]


def parse_range(range_str: Optional[str]) -> Optional[tuple[int, int]]:
    if not range_str:
        return None
    a, b = range_str.split("-")
    return int(a), int(b)


@app.command()
def run(
    start: int = typer.Option(441, help="Capítulo inicial."),
    end: int = typer.Option(1394, help="Capítulo final."),
    out: str = typer.Option("./build", help="Diretório de saída."),
    only: Optional[str] = typer.Option(None, help="Lista de capítulos: 534,535,536"),
    range_str: Optional[str] = typer.Option(None, help="Faixa: 850-1029"),
    url_template: Optional[str] = typer.Option(None, help="Template da URL com {id}, ex.: https://site/x/capitulo-{id}"),
    series_title: Optional[str] = typer.Option(None, help="Título da série para metadados/arquivo."),
    author: Optional[str] = typer.Option(None, help="Autor para metadados do EPUB."),
    cover_url: Optional[str] = typer.Option(None, help="URL da imagem de capa (opcional)"),
    min_delay: float = typer.Option(2.0, help="Delay mínimo entre requests."),
    max_delay: float = typer.Option(5.0, help="Delay máximo entre requests."),
    max_retries: int = typer.Option(4, help="Máximo de tentativas por capítulo."),
    dry_run: bool = typer.Option(False, help="Executa sem salvar outputs permanentes."),
):
    base = Path('.')
    ensure_dirs(base)

    if range_str:
        start, end = parse_range(range_str)  # type: ignore
    only_list = parse_only_list(only)

    cache = CacheStore(base)
    fetcher = FetchClient(min_delay=min_delay, max_delay=max_delay, max_retries=max_retries, url_template=url_template)

    chapter_ids: List[int]
    if only_list:
        chapter_ids = only_list
    else:
        chapter_ids = list(range(start, end + 1))

    normalized_chapters = []
    total = len(chapter_ids)

    with Progress() as progress:
        task = progress.add_task(f"Processando capítulos {chapter_ids[0]}-{chapter_ids[-1]}", total=total)

        for idx, cid in enumerate(chapter_ids, start=1):
            typer.echo(f"[INFO] ({idx}/{total}) fetch cid={cid}")
            # Idempotência: verifica cache JSON
            existing = cache.load_json(cid)
            if existing is not None:
                typer.echo(f"[INFO] ({idx}/{total}) cache hit cid={cid}")
                normalized_chapters.append(existing)
                progress.advance(task)
                continue

            url = fetcher.compose_url(cid)
            html = fetcher.fetch(cid, url)

            if html is None:
                typer.echo(json.dumps({"level": "WARN", "chapter": cid, "status": "skip_no_html", "url": url}))
                progress.advance(task)
                continue

            cache.save_html(cid, html)

            typer.echo(f"[INFO] ({idx}/{total}) parse cid={cid}")
            parsed = parse_chapter(cid, url, html)
            typer.echo(f"[INFO] ({idx}/{total}) clean cid={cid}")
            cleaned = clean_html(parsed)

            if not dry_run:
                cache.save_json(cid, cleaned)

            typer.echo(f"[OK]   ({idx}/{total}) done cid={cid}")
            normalized_chapters.append(cleaned)
            progress.advance(task)

    if dry_run:
        typer.echo(json.dumps({"level": "INFO", "status": "dry_run_complete", "chapters": len(normalized_chapters)}))
        raise typer.Exit(code=0)

    # Construção de EPUBs
    builder = EpubBuilder(Path(out), series_title=series_title, author=author)
    by_id = {c["id"]: c for c in normalized_chapters}

    if url_template:
        # Modo custom: gerar um único EPUB com os capítulos coletados e título da série como título do "livro"
        book_meta = {
            "book": 1,
            "title": series_title or "Livro",
            "start": min(by_id),
            "end": max(by_id),
        }
        group = [by_id[cid] for cid in sorted(by_id)]
        filename = output_filename_single(series_title or "Livro", book_meta['start'], book_meta['end'])
        typer.echo(f"[INFO] build EPUB unico custom range={book_meta['start']}-{book_meta['end']} -> {filename}")
        cover_bytes = None
        if cover_url:
            try:
                r = requests.get(cover_url, timeout=30)
                r.raise_for_status()
                cover_bytes = r.content
            except Exception as e:
                typer.echo(json.dumps({"level": "WARN", "status": "cover_fetch_failed", "error": str(e)}))
        builder.build_epub(group, book_meta, cover_bytes=cover_bytes, override_filename=filename)
        typer.echo("[OK]   EPUB custom gerado")
    else:
        # Preset LOM: quebrar por BOOKS
        for book in BOOKS:
            group = [by_id[cid] for cid in sorted(by_id) if book["start"] <= cid <= book["end"] and cid in by_id]
            if not group:
                continue
            typer.echo(f"[INFO] build EPUB livro={book['book']} range={book['start']}-{book['end']}")
            builder.build_epub(group, book)
            typer.echo(f"[OK]   EPUB livro={book['book']} gerado")


if __name__ == "__main__":
    app()


