"""Ortak hafıza (blackboard): tüm ajanların okuyup yazdığı tipli durum.

Tasarım notları:
- Ajanlar birbirine mesaj göndermez; yalnızca bu state üzerinden haberleşir.
- `islem_gecmisi` append-only denetim izidir ve paralel dalların (mevzuat ∥
  yönlendirme) çakışmadan birleşebilmesi için `operator.add` reducer'ı taşır.
- LangGraph checkpoint serileştirmesi için state'te düz dict/list tutulur;
  Pydantic modelleri ajan içi doğrulamada kullanılıp `model_dump()` ile yazılır.
"""
from __future__ import annotations

import operator
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

# Pydantic şemaları (ajan çıktıları)
Kritiklik = Literal["kritik", "onemli", "opsiyonel"]


class Siniflandirma(BaseModel):
    tur: str = Field(description="Taksonomideki tür kodu")
    aciliyet: Literal["dusuk", "normal", "yuksek"] = "normal"
    guven: float = Field(ge=0, le=1)
    gerekce: str = ""


class Alan(BaseModel):
    deger: str
    guven: float = Field(default=0.8, ge=0, le=1)
    kaynak_span: str = ""  # değerin geçtiği ham metin parçası (grounding kanıtı)


class EksikAlan(BaseModel):
    alan: str
    kritiklik: Kritiklik
    dayanak: str = ""


class MevzuatAtfi(BaseModel):
    kaynak: str
    madde_no: str
    alinti: str
    skor: float = 0.0


class BirimOnerisi(BaseModel):
    birim: str
    birim_kodu: str = ""
    guven: float = Field(default=0.5, ge=0, le=1)
    gerekce: str = ""
    alternatif: str = ""


class Taslak(BaseModel):
    tur: str  # cevap_yazisi | ust_yazi | bilgilendirme | eksiklik_bildirim
    metin: str
    surum_no: int = 1


class DenetimBulgusu(BaseModel):
    kural: str
    seviye: Literal["kritik", "uyari"]
    mesaj: str


class DenetimRaporu(BaseModel):
    sonuc: Literal["GECTI", "KALDI"]
    bulgular: list[DenetimBulgusu] = Field(default_factory=list)


# LangGraph state
class EvrakState(TypedDict, total=False):
    # Kimlik ve girdi
    islem_id: str
    dosya_yolu: str
    dosya_adi: str

    # Metin katmanı (Alım Ajanı)
    ham_metin: str
    metin_kaynagi: Literal["dogal_metin", "multimodal_ocr", "tesseract", "manuel"]
    ocr_guven: float
    dusuk_guven: bool
    pii_tespitleri: list[str]

    # Görev 1 çıktıları
    siniflandirma: dict
    cikarilan_alanlar: dict[str, dict]
    eksik_alanlar: list[dict]
    ozet: str
    ilgili_mevzuat: list[dict]

    # Görev 2 çıktıları
    hedef_birim: dict
    taslak: dict
    taslak_gecmisi: list[dict]
    denetim_raporu: dict
    revizyon_sayisi: int
    revizyon_notu: str
    eksiklik_modu: bool  # kullanıcı "eksiklik bildirim yazısı üret" seçtiyse
    onay_karari: str     # onayla | revize
    cikti_yollari: dict[str, str]

    # Süreç kontrol ve izlenebilirlik
    islem_gecmisi: Annotated[list[dict], operator.add]
    hatalar: Annotated[list[dict], operator.add]


def log(ajan: str, mesaj: str, **ekstra: Any) -> dict:
    """Denetim izine tek satır kayıt üretir."""
    return {
        "zaman": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ajan": ajan,
        "mesaj": mesaj,
        **ekstra,
    }


def yeni_islem_state(dosya_yolu: str | None = None, metin: str | None = None,
                     dosya_adi: str | None = None) -> EvrakState:
    """UI/CLI'nin grafa verdiği başlangıç durumu."""
    return EvrakState(
        islem_id=uuid.uuid4().hex[:12],
        dosya_yolu=dosya_yolu or "",
        dosya_adi=dosya_adi or (dosya_yolu.rsplit("/", 1)[-1] if dosya_yolu else "elle_giris.txt"),
        ham_metin=metin or "",
        taslak_gecmisi=[],
        revizyon_sayisi=0,
        eksiklik_modu=False,
        islem_gecmisi=[],
        hatalar=[],
    )
