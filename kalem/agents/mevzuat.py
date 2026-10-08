"""Yerel örnek korpustan ilgili mevzuat parçalarını getirir."""
from __future__ import annotations

from kalem.agents import AjanBaglami
from kalem.state import EvrakState, log


def calistir(state: EvrakState, ctx: AjanBaglami) -> dict:
    parcalar = [state["siniflandirma"]["tur"].replace("_", " "),
                state.get("ozet", ""),
                state.get("cikarilan_alanlar", {}).get("konu", {}).get("deger", ""),
                state.get("cikarilan_alanlar", {}).get("talep_ozeti", {}).get("deger", "")]
    sorgu = " ".join(p for p in parcalar if p)
    atiflar = ctx.getirici.ara(sorgu)
    mesaj = (f"{len(atiflar)} mevzuat atfı bulundu" if atiflar
             else "İlgili mevzuat korpusta tespit edilemedi ")
    return {"ilgili_mevzuat": [a.model_dump() for a in atiflar],
            "islem_gecmisi": [log("mevzuat", mesaj)]}
