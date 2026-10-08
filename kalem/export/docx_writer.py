"""Taslak metnini DOCX olarak kaydeder."""
from __future__ import annotations

from pathlib import Path

from kalem.state import EvrakState


def docx_yaz(state: EvrakState, hedef_dizin: Path) -> str:
    hedef_dizin.mkdir(parents=True, exist_ok=True)
    yol = hedef_dizin / f"{state['islem_id']}_{state['taslak']['tur']}.docx"
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Pt
    except ImportError:
        yol = yol.with_suffix(".txt")
        yol.write_text(state["taslak"]["metin"], encoding="utf-8")
        return str(yol)

    d = Document()
    stil = d.styles["Normal"]
    stil.font.name = "Times New Roman"
    stil.font.size = Pt(12)

    satirlar = state["taslak"]["metin"].splitlines()
    for i, satir in enumerate(satirlar):
        p = d.add_paragraph(satir.rstrip())
        ilk_blok = i < 3 and bool(satir.strip()) and not satir.startswith(("Sayı", "Konu"))
        if ilk_blok and p.runs:  # T.C. / kurum / birim başlık bloğu ortalanır
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.runs[0].bold = True
        p.paragraph_format.space_after = Pt(2)
    d.save(yol)
    return str(yol)
