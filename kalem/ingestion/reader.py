"""Metin, deneysel multimodal okuma ve Tesseract ile belge alımı.

1) Yerleşik metin katmanı  : .txt doğrudan; .pdf -> pdfplumber
2) Multimodal LLM okuma    : taranmış PDF/görüntü -> Gemini (çevrimiçi modda)
3) Tesseract 5 (tur)       : yerel görüntü OCR

Her yol (metin, kaynak, güven) üçlüsü döndürür; katman yükseltme kararı
güven eşiklerine göre burada verilir. Ağır bağımlılıklar tembel import edilir:
kurulmamışsa sistem çökmez, bir sonraki katmana düşer.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

from kalem.config import Ayarlar
from kalem.ingestion.confidence import metin_guveni

GORUNTU_UZANTILAR = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class OkumaSonucu:
    metin: str
    kaynak: str  # dogal_metin | multimodal_ocr | tesseract | basarisiz
    guven: float
    notlar: list[str]


def _pdf_metin_katmani(yol: Path) -> str:
    try:
        import pdfplumber
    except ImportError:
        return ""
    try:
        with pdfplumber.open(yol) as pdf:
            return "\n".join((s.extract_text() or "") for s in pdf.pages)
    except Exception:
        return ""


def _multimodal_oku(yol: Path, ayarlar: Ayarlar) -> str:
    """Gemini'nin yerleşik görüntü/PDF anlama yeteneğiyle metin çıkarımı."""
    model = ayarlar.modeller.get("ocr")
    if ayarlar.cevrimdisi or not model:
        return ""
    try:
        import litellm
    except ImportError:
        return ""
    veri = base64.b64encode(yol.read_bytes()).decode()
    mime = "application/pdf" if yol.suffix.lower() == ".pdf" else f"image/{yol.suffix.lstrip('.').lower()}"
    try:
        yanit = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": [
                {"type": "text",
                 "text": ("Bu belgedeki TÜM metni, düzenini koruyarak aynen çıkar. "
                          "Yorum ekleme, yalnızca metni ver.")},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{veri}"}},
            ]}],
            temperature=0.0,
        )
        return yanit.choices[0].message.content or ""
    except Exception:
        return ""


def _tesseract_oku(yol: Path) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""
    try:
        return pytesseract.image_to_string(Image.open(yol), lang="tur")
    except Exception:
        return ""


def belge_oku(dosya_yolu: str, ayarlar: Ayarlar) -> OkumaSonucu:
    yol = Path(dosya_yolu)
    notlar: list[str] = []
    if not yol.exists():
        return OkumaSonucu("", "basarisiz", 0.0, [f"Dosya bulunamadı: {dosya_yolu}"])
    ek = yol.suffix.lower()

    # Katman 1 — yerleşik metin
    if ek == ".txt":
        metin = yol.read_text(encoding="utf-8", errors="replace")
        return OkumaSonucu(metin, "dogal_metin",
                           max(metin_guveni(metin), 0.9 if metin.strip() else 0.0), notlar)
    if ek == ".pdf":
        metin = _pdf_metin_katmani(yol)
        g = metin_guveni(metin)
        if g >= ayarlar.esikler["ocr_dusuk"]:
            return OkumaSonucu(metin, "dogal_metin", g, notlar)
        notlar.append("PDF metin katmanı zayıf/yok → taranmış varsayıldı, katman yükseltiliyor")

    # Katman 2 — multimodal (görüntüler ve taranmış PDF'ler)
    if ek == ".pdf" or ek in GORUNTU_UZANTILAR:
        metin = _multimodal_oku(yol, ayarlar)
        g = metin_guveni(metin)
        if g >= ayarlar.esikler["ocr_kritik"]:
            return OkumaSonucu(metin, "multimodal_ocr", g, notlar)
        if metin:
            notlar.append("Multimodal okuma düşük güvenli → Tesseract deneniyor")

        # Tesseract yalnız görüntü dosyalarına uygulanır; PDF rasterleştirme yoktur.
        if ek in GORUNTU_UZANTILAR:
            metin = _tesseract_oku(yol)
            g = metin_guveni(metin)
            if g >= ayarlar.esikler["ocr_kritik"]:
                return OkumaSonucu(metin, "tesseract", g, notlar)
        notlar.append("Tüm katmanlar eşik altında kaldı")
        return OkumaSonucu(metin, "basarisiz", g, notlar)

    return OkumaSonucu("", "basarisiz", 0.0, [f"Desteklenmeyen uzantı: {ek}"])
