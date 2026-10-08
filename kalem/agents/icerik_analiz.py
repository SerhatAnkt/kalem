"""Alanları ve özeti çıkarır; YAML kurallarına göre eksikleri belirler."""
from __future__ import annotations

from pydantic import BaseModel, Field

from kalem import prompts
from kalem.agents import AjanBaglami
from kalem.security import sarmala_belge
from kalem.state import Alan, EksikAlan, EvrakState, log

VARSAYILAN_ALANLAR = ["gonderen_ad_soyad", "gonderen_kurum", "tarih", "sayi", "konu",
                      "adres", "tc_kimlik", "talep_ozeti", "imza", "tutar"]


class _AnalizYaniti(BaseModel):
    alanlar: dict[str, Alan] = Field(default_factory=dict)
    ozet: str = ""


def eksikleri_bul(tur: str, alanlar: dict[str, dict], kurallar: dict) -> list[EksikAlan]:
    """Saf fonksiyon (birim testli): tür kurallarına göre eksik listesi."""
    eksikler = []
    for kural in kurallar.get(tur, []):
        ad = kural["alan"]
        mevcut = alanlar.get(ad, {}).get("deger", "").strip()
        if not mevcut:
            eksikler.append(EksikAlan(alan=ad, kritiklik=kural["kritiklik"],
                                      dayanak=kural.get("dayanak", "")))
    return eksikler


def calistir(state: EvrakState, ctx: AjanBaglami) -> dict:
    tur = state["siniflandirma"]["tur"]
    tur_adi = ctx.ayarlar.taksonomi[tur]["ad"]
    kullanici = prompts.ICERIK_ANALIZ.format(
        tur_adi=tur_adi, alanlar=", ".join(VARSAYILAN_ALANLAR),
        belge=sarmala_belge(state["ham_metin"]),
    )
    try:
        yanit: _AnalizYaniti = ctx.istemci.uret_json(
            "icerik_analiz", prompts.SISTEM_KURALLARI, kullanici, _AnalizYaniti, katman="hizli")
    except ValueError as e:
        yanit = _AnalizYaniti(ozet="(analiz üretilemedi)")
        hata = [log("icerik_analiz", f"JSON hatası: {e}")]
    else:
        hata = []

    alanlar = {k: v.model_dump() for k, v in yanit.alanlar.items()}
    eksikler = eksikleri_bul(tur, alanlar, ctx.ayarlar.zorunlu_alanlar)
    kritik_sayisi = sum(1 for e in eksikler if e.kritiklik == "kritik")
    return {
        "cikarilan_alanlar": alanlar,
        "ozet": yanit.ozet,
        "eksik_alanlar": [e.model_dump() for e in eksikler],
        "hatalar": hata,
        "islem_gecmisi": [log("icerik_analiz",
                              f"{len(alanlar)} alan çıkarıldı; {len(eksikler)} eksik "
                              f"({kritik_sayisi} kritik)")],
    }
