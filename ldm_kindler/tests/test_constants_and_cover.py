from __future__ import annotations

from io import BytesIO

from PIL import Image

from ldm_kindler.constants import (
    get_book_info_for_chapter,
    output_filename_for_book,
    output_filename,
    output_filename_single,
    sanitize_for_filename,
)
from ldm_kindler.builder.cover import generate_cover_image


def test_get_book_info_for_chapter_boundaries():
    assert get_book_info_for_chapter(1)[0] == 1
    assert get_book_info_for_chapter(65)[0] == 1
    assert get_book_info_for_chapter(680)[0] == 7
    assert get_book_info_for_chapter(2000) == (None, None)


def test_output_filename_for_book_and_custom_series():
    book = {"book": 8, "title": "Resonance (Ressonância)", "start": 681, "end": 849}
    name_default = output_filename_for_book(book)
    assert name_default.startswith("Lorde_dos_Misterios_Livro_08_")
    assert name_default.endswith("(681-849).epub")
    assert "Ressonancia" in name_default  # acento removido

    name_custom = output_filename("Minha Série", book)
    assert name_custom.startswith("Minha_Serie_Livro_08_")
    assert name_custom.endswith("(681-849).epub")


def test_output_filename_single_and_sanitize():
    assert output_filename_single("Título/Com:Caracteres?*Especiais", 1, 2) == "Titulo_Com-CaracteresEspeciais_(1-2).epub"
    assert sanitize_for_filename("A/B\\C:D*E?F\"G<H>I|J ãâ êé ó ç") == "A_B_C-DEF'G(H)I-J_aa_ee_o_c"


def test_generate_cover_image_png_and_size():
    book = {"book": 1, "title": "Clown (Palhaço)", "start": 1, "end": 65}
    data = generate_cover_image(book, size=(400, 600), series_title=None)
    img = Image.open(BytesIO(data))
    assert img.size == (400, 600)
    assert img.mode == "RGB"
    assert img.format == "PNG"

