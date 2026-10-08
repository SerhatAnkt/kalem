"""Metin güven skoru: OCR/çıkarım kalitesinin sezgisel ölçümü (0-1).

Bileşenler: Türkçe karakter varlığı, harf oranı, ortalama kelime uzunluğu
makullüğü, sık-Türkçe-kelime isabet oranı, bozuk karakter oranı.
Model bağımsız çalışır; Tesseract'ın kendi kelime güvenleriyle harmanlanabilir.
"""
from __future__ import annotations

import re

from kalem.utils import tokenize

# Yüksek frekanslı Türkçe kelimeler (fonksiyonel + resmî yazışma alanı)
_SIK = {
    "ve", "ile", "bir", "bu", "için", "olarak", "olan", "gereği", "gereğini",
    "tarafından", "hakkında", "konu", "sayı", "tarih", "arz", "rica", "ederim",
    "talep", "bilgi", "kurum", "müdürlüğü", "başkanlığı", "sayın", "adres",
    "olup", "ilgili", "yazı", "ekte", "kadar", "sonra", "üzere", "söz", "konusu",
}
_BOZUK = re.compile(r"[^\w\sçğıöşüÇĞİÖŞÜ.,;:!?()\-/'\"@%₺]")


def metin_guveni(metin: str) -> float:
    metin = metin.strip()
    if len(metin) < 20:
        return 0.0
    harf = sum(c.isalpha() for c in metin)
    harf_orani = harf / max(1, len(metin))
    turkce = 1.0 if re.search(r"[çğıöşüÇĞİÖŞÜ]", metin) else 0.4
    bozuk_orani = len(_BOZUK.findall(metin)) / max(1, len(metin))
    kelimeler = tokenize(metin)
    if not kelimeler:
        return 0.0
    ort = sum(map(len, kelimeler)) / len(kelimeler)
    uzunluk_puani = 1.0 if 2.5 <= ort <= 12 else 0.3
    isabet = sum(1 for k in kelimeler if k in _SIK) / len(kelimeler)
    isabet_puani = min(1.0, isabet / 0.08)  # %8+ isabet → tam puan

    skor = (0.25 * min(1.0, harf_orani / 0.55)
            + 0.15 * turkce
            + 0.20 * uzunluk_puani
            + 0.25 * isabet_puani
            + 0.15 * max(0.0, 1.0 - bozuk_orani * 25))
    return round(max(0.0, min(1.0, skor)), 3)
