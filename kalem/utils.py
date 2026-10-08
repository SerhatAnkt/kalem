"""Ortak yardımcılar: Türkçe normalizasyon, JSON ayıklama, otomatik HITL yanıtı."""
from __future__ import annotations

import json
import re
from typing import Any

# Türkçe'ye özgü büyük harf tuzağı: "İ".lower() ve "I".lower() Python'da
# İngilizce kurala göre çalışır; önce çeviri tablosu uygulanır.
_TR_CEVIRI = str.maketrans({"İ": "i", "I": "ı"})

_TOKEN = re.compile(r"[a-zçğıöşü0-9]+")


def tr_kucult(s: str) -> str:
    return s.translate(_TR_CEVIRI).lower()


def tokenize(s: str) -> list[str]:
    return _TOKEN.findall(tr_kucult(s))


def json_ayikla(metin: str) -> dict:
    """LLM çıktısından JSON gövdesini ayıklar (kod bloğu/önsöz toleranslı)."""
    metin = metin.strip()
    metin = re.sub(r"^```(?:json)?\s*|\s*```$", "", metin, flags=re.S)
    ilk, son = metin.find("{"), metin.rfind("}")
    if ilk == -1 or son == -1:
        raise ValueError("JSON gövdesi bulunamadı")
    return json.loads(metin[ilk : son + 1])


def otomatik_yanit(kesme: dict) -> Any:
    """Eval/CLI otomatik modunda insan-onay kapılarına verilen politika yanıtları."""
    tip = kesme.get("tip")
    if tip == "manuel_metin":
        return {"metin": kesme.get("varsayilan", "(otomatik: metin sağlanamadı)")}
    if tip == "tur_dogrulama":
        adaylar = kesme.get("adaylar") or ["diger_belirsiz"]
        return {"tur": adaylar[0]}
    if tip == "eksik_bilgi":
        cevaplar = {e["alan"]: "BEYAN EDİLDİ (otomatik demo)" for e in kesme.get("eksikler", [])}
        return {"secim": "tamamla", "cevaplar": cevaplar}
    if tip == "nihai_onay":
        return {"karar": "onayla"}
    return {}
