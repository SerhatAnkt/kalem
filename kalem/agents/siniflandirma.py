"""2 · Sınıflandırma Ajanı (Tasnif Memuru)."""
from __future__ import annotations

from kalem import prompts
from kalem.agents import AjanBaglami
from kalem.security import sarmala_belge
from kalem.state import EvrakState, Siniflandirma, log

METIN_LIMIT = 4000  # maliyet optimizasyonu: tür tayini için ilk ~4K karakter yeterli


def calistir(state: EvrakState, ctx: AjanBaglami) -> dict:
    tur_listesi = "\n".join(f"- {kod}: {t['ad']}" for kod, t in ctx.ayarlar.taksonomi.items())
    kullanici = prompts.SINIFLANDIRMA.format(
        tur_listesi=tur_listesi,
        belge=sarmala_belge(state["ham_metin"][:METIN_LIMIT]),
    )
    try:
        sonuc: Siniflandirma = ctx.istemci.uret_json(
            "siniflandirma", prompts.SISTEM_KURALLARI, kullanici, Siniflandirma, katman="hizli")
        if sonuc.tur not in ctx.ayarlar.taksonomi:
            sonuc = Siniflandirma(tur="diger_belirsiz", guven=0.4,
                                  gerekce=f"Model taksonomi dışı kod verdi: {sonuc.tur}")
    except ValueError as e:
        # Güvenli varsayılan: belirsiz sınıf + düşük güven → tür doğrulama kapısı açılır
        sonuc = Siniflandirma(tur="diger_belirsiz", guven=0.0, gerekce="Şema doğrulanamadı")
        return {"siniflandirma": sonuc.model_dump(),
                "hatalar": [log("siniflandirma", f"JSON hatası: {e}")],
                "islem_gecmisi": [log("siniflandirma", "Güvenli varsayılana inildi")]}
    return {
        "siniflandirma": sonuc.model_dump(),
        "islem_gecmisi": [log("siniflandirma",
                              f"Tür: {sonuc.tur} (güven {sonuc.guven:.2f}) — {sonuc.gerekce}")],
    }
