"""5 · Yönlendirme Ajanı (Havale Memuru)."""
from __future__ import annotations

from pydantic import BaseModel

from kalem import prompts
from kalem.agents import AjanBaglami
from kalem.security import sarmala_belge
from kalem.state import BirimOnerisi, EvrakState, log


class _YonYaniti(BaseModel):
    birim_kodu: str
    guven: float = 0.5
    gerekce: str = ""
    alternatif_kodu: str = ""


def calistir(state: EvrakState, ctx: AjanBaglami) -> dict:
    katalog = "\n".join(f"- {b['kod']}: {b['ad']} — {b['gorev']}" for b in ctx.ayarlar.birim_katalogu)
    kodlar = {b["kod"]: b["ad"] for b in ctx.ayarlar.birim_katalogu}
    kullanici = prompts.YONLENDIRME.format(
        katalog=katalog,
        tur_adi=ctx.ayarlar.taksonomi[state["siniflandirma"]["tur"]]["ad"],
        ozet=state.get("ozet", ""),
        belge=sarmala_belge(state["ham_metin"][:3000]),
    )
    try:
        y: _YonYaniti = ctx.istemci.uret_json(
            "yonlendirme", prompts.SISTEM_KURALLARI, kullanici, _YonYaniti, katman="hizli")
    except ValueError:
        y = _YonYaniti(birim_kodu="yazi_isleri", guven=0.4, gerekce="Şema hatası → genel birim")
    if y.birim_kodu not in kodlar:
        y = _YonYaniti(birim_kodu="yazi_isleri", guven=0.4,
                       gerekce=f"Katalog dışı kod ({y.birim_kodu}) → genel birim")
    oneri = BirimOnerisi(birim=kodlar[y.birim_kodu], birim_kodu=y.birim_kodu, guven=y.guven,
                         gerekce=y.gerekce, alternatif=kodlar.get(y.alternatif_kodu, ""))
    return {"hedef_birim": oneri.model_dump(),
            "islem_gecmisi": [log("yonlendirme",
                                  f"Birim: {oneri.birim} (güven {oneri.guven:.2f})")]}
