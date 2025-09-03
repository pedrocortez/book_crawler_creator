from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Dict

from PIL import Image, ImageDraw, ImageFont


def generate_cover_image(book: Dict, size=(1600, 2560), series_title: str | None = None) -> bytes:
    img = Image.new('RGB', size, color=(20, 24, 28))
    draw = ImageDraw.Draw(img)

    if series_title:
        title = f"{series_title}\n({book['start']}-{book['end']})"
    else:
        title = f"Lorde dos Mistérios\nLivro {book['book']}:\n{book['title']}\n({book['start']}-{book['end']})"

    try:
        font = ImageFont.truetype("arial.ttf", 72)
        font_small = ImageFont.truetype("arial.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()

    W, H = size
    # Medição compatível com versões do Pillow
    try:
        bbox = draw.multiline_textbbox((0, 0), title, font=font, align='center', spacing=10)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
    except Exception:
        # Fallback simples: mede linha a linha
        lines = title.split("\n")
        line_sizes = [draw.textbbox((0, 0), ln, font=font) for ln in lines]
        w = max((b[2] - b[0]) for b in line_sizes) if line_sizes else 0
        h = sum((b[3] - b[1]) for b in line_sizes) + (len(lines) - 1) * 10

    draw.multiline_text(((W - w) / 2, (H - h) / 2), title, fill=(230, 230, 230), font=font, align='center', spacing=10)
    draw.text((W - 20 - 300, H - 60), "Compilação pessoal", font=font_small, fill=(180, 180, 180))

    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


