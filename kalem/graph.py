"""Belge işleme akışı ve operatör onay noktaları.

Deterministik omurga + koşullu kenarlar + döngü + insan-onay kesme noktaları:
  alim → siniflandirma → [tur_dogrulama] → icerik_analiz → [eksik_kapisi]
       → (mevzuat ∥ yonlendirme) → taslak → denetim ⇄ taslak → nihai_onay → cikti
"""
from __future__ import annotations

from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from kalem.agents import (AjanBaglami, denetim, icerik_analiz, mevzuat,
                          siniflandirma, taslak, yonlendirme)
from kalem.agents.icerik_analiz import eksikleri_bul
from kalem.config import Ayarlar, ayarlari_yukle
from kalem.ingestion.reader import belge_oku
from kalem.llm.client import LLMIstemci
from kalem.rag.retriever import MevzuatGetirici
from kalem.security import kisisel_veri_maskele
from kalem.state import EvrakState, log


def _ctx_kur(ayarlar: Ayarlar) -> AjanBaglami:
    return AjanBaglami(ayarlar=ayarlar, istemci=LLMIstemci(ayarlar),
                       getirici=MevzuatGetirici(ayarlar))


def graf_kur(ayarlar: Ayarlar | None = None, checkpointer=None):
    ayarlar = ayarlar or ayarlari_yukle()
    ctx = _ctx_kur(ayarlar)
    g = StateGraph(EvrakState)

    # 1 · Alım
    def alim(state: EvrakState) -> dict:
        gecmis = []
        if state.get("ham_metin"):  # UI'dan elle metin girildi
            metin, kaynak, guven = state["ham_metin"], "manuel", 0.99
        else:
            sonuc = belge_oku(state["dosya_yolu"], ayarlar)
            metin, kaynak, guven = sonuc.metin, sonuc.kaynak, sonuc.guven
            gecmis += [log("alim", n) for n in sonuc.notlar]
            if kaynak == "basarisiz" or guven < ayarlar.esikler["ocr_kritik"]:
                # HITL — H1: yeniden tarama yerine bu sürümde manuel metin istenir
                yanit = interrupt({
                    "tip": "manuel_metin",
                    "mesaj": ("Belge güvenilir okunamadı. Daha yüksek çözünürlükte tarayıp "
                              "yeniden yükleyebilir veya metni buraya yapıştırabilirsiniz."),
                    "guven": guven, "varsayilan": metin,
                })
                metin, kaynak, guven = yanit.get("metin", metin), "manuel", 0.99
                gecmis.append(log("alim", "İnsan kapısı: manuel metin alındı"))

        metin, pii = kisisel_veri_maskele(metin)
        gecmis.append(log("alim", f"Metin hazır ({kaynak}, güven {guven:.2f}, "
                                  f"{len(metin)} karakter, PII: {pii or 'yok'})"))
        return {"ham_metin": metin, "metin_kaynagi": kaynak, "ocr_guven": guven,
                "dusuk_guven": guven < ayarlar.esikler["ocr_dusuk"],
                "pii_tespitleri": pii, "islem_gecmisi": gecmis}

    # 2-3 · Sınıflandırma + tür doğrulama kapısı
    def sinif_dugumu(state: EvrakState) -> dict:
        return siniflandirma.calistir(state, ctx)

    def sinif_yonu(state: EvrakState) -> Literal["tur_dogrulama", "icerik_analiz"]:
        s = state["siniflandirma"]
        dusuk = s["guven"] < ayarlar.esikler["siniflandirma"] or s["tur"] == "diger_belirsiz"
        return "tur_dogrulama" if dusuk else "icerik_analiz"

    def tur_dogrulama(state: EvrakState) -> dict:
        oncelik = state["siniflandirma"]["tur"]
        adaylar = [oncelik] + [k for k in ayarlar.taksonomi if k != oncelik]
        yanit = interrupt({
            "tip": "tur_dogrulama",
            "mesaj": "Evrak türünden emin olunamadı. Lütfen doğru türü seçin.",
            "adaylar": adaylar,
            "adlar": {k: ayarlar.taksonomi[k]["ad"] for k in adaylar},
        })
        secim = yanit.get("tur", adaylar[0])
        if secim not in ayarlar.taksonomi:
            secim = "diger_belirsiz"
        s = dict(state["siniflandirma"], tur=secim, guven=1.0,
                 gerekce="İnsan operatör doğruladı")
        return {"siniflandirma": s,
                "islem_gecmisi": [log("tur_dogrulama", f"Operatör seçimi: {secim}")]}

    # 4 · İçerik analizi + eksik kapısı
    def analiz_dugumu(state: EvrakState) -> dict:
        return icerik_analiz.calistir(state, ctx)

    def eksik_yonu(state: EvrakState):
        kritik = [e for e in state.get("eksik_alanlar", []) if e["kritiklik"] == "kritik"]
        return "eksik_kapisi" if kritik else ["mevzuat", "yonlendirme"]

    def eksik_kapisi(state: EvrakState) -> dict:
        kritikler = [e for e in state["eksik_alanlar"] if e["kritiklik"] == "kritik"]
        yanit = interrupt({
            "tip": "eksik_bilgi",
            "mesaj": "Kritik bilgiler eksik. Tamamlayın veya eksiklik bildirim yazısı üretin.",
            "eksikler": kritikler,
        })
        if yanit.get("secim") == "eksiklik_yazisi":
            return {"eksiklik_modu": True,
                    "islem_gecmisi": [log("eksik_kapisi", "Seçim: eksiklik bildirim yazısı")]}
        alanlar = dict(state.get("cikarilan_alanlar", {}))
        tespitler = set(state.get("pii_tespitleri", []))
        izinli_alanlar = {e["alan"] for e in kritikler}
        for ad, deger in (yanit.get("cevaplar") or {}).items():
            if ad in izinli_alanlar and str(deger).strip():
                maskeli, bulunan = kisisel_veri_maskele(str(deger).strip())
                tespitler.update(bulunan)
                alanlar[ad] = {"deger": maskeli, "guven": 1.0,
                               "kaynak_span": "insan girdisi"}
        eksikler = eksikleri_bul(state["siniflandirma"]["tur"], alanlar, ayarlar.zorunlu_alanlar)
        return {"cikarilan_alanlar": alanlar,
                "eksik_alanlar": [e.model_dump() for e in eksikler],
                "pii_tespitleri": sorted(tespitler),
                "islem_gecmisi": [log("eksik_kapisi",
                                      f"Operatör {len(yanit.get('cevaplar') or {})} alan tamamladı")]}

    def kapi_yonu(state: EvrakState):
        if state.get("eksiklik_modu"):
            return "taslak"
        if any(e["kritiklik"] == "kritik" for e in state.get("eksik_alanlar", [])):
            return "eksik_kapisi"
        return ["mevzuat", "yonlendirme"]

    # 5-6 · Paralel dal
    def mevzuat_dugumu(state: EvrakState) -> dict:
        return mevzuat.calistir(state, ctx)

    def yonlendirme_dugumu(state: EvrakState) -> dict:
        return yonlendirme.calistir(state, ctx)

    # 7-8 · Taslak ⇄ Denetim döngüsü
    def taslak_dugumu(state: EvrakState) -> dict:
        return taslak.calistir(state, ctx)

    def denetim_dugumu(state: EvrakState) -> dict:
        return denetim.calistir(state, ctx)

    def denetim_yonu(state: EvrakState) -> Literal["taslak", "nihai_onay"]:
        kaldi = state["denetim_raporu"]["sonuc"] == "KALDI"
        if kaldi and state.get("revizyon_sayisi", 0) <= ayarlar.esikler["revizyon_limiti"]:
            return "taslak"
        return "nihai_onay"  # GEÇTİ veya limit doldu (bulgularla insana eskalasyon)

    # 9 · Nihai onay + çıktı
    def nihai_onay(state: EvrakState) -> dict:
        yanit = interrupt({
            "tip": "nihai_onay",
            "mesaj": "Taslak hazır. Onaylayın, düzenleyin veya revizyon isteyin.",
            "taslak": state["taslak"], "denetim": state["denetim_raporu"],
        })
        karar = yanit.get("karar", "onayla")
        if karar == "revize":
            return {"onay_karari": "revize", "revizyon_notu": yanit.get("not", ""),
                    "islem_gecmisi": [log("nihai_onay", "Revizyon istendi")]}
        guncelleme: dict = {"onay_karari": "onayla",
                            "islem_gecmisi": [log("nihai_onay", f"Karar: {karar}")]}
        if karar == "duzenle" and yanit.get("metin"):
            t = dict(state["taslak"], metin=yanit["metin"],
                     surum_no=state["taslak"]["surum_no"] + 1)
            guncelleme["taslak"] = t
            guncelleme["taslak_gecmisi"] = state.get("taslak_gecmisi", []) + [t]
        return guncelleme

    def onay_yonu(state: EvrakState) -> Literal["taslak", "cikti"]:
        return "taslak" if state.get("onay_karari") == "revize" else "cikti"

    def cikti(state: EvrakState) -> dict:
        from kalem.export.docx_writer import docx_yaz
        yol = docx_yaz(state, ayarlar.yol("cikti_dizini"))
        return {"cikti_yollari": {"docx": yol},
                "islem_gecmisi": [log("cikti", f"Nihai yazı üretildi: {yol}")]}

    # graf kabloları
    g.add_node("alim", alim)
    g.add_node("siniflandirma", sinif_dugumu)
    g.add_node("tur_dogrulama", tur_dogrulama)
    g.add_node("icerik_analiz", analiz_dugumu)
    g.add_node("eksik_kapisi", eksik_kapisi)
    g.add_node("mevzuat", mevzuat_dugumu)
    g.add_node("yonlendirme", yonlendirme_dugumu)
    g.add_node("taslak", taslak_dugumu)
    g.add_node("denetim", denetim_dugumu)
    g.add_node("nihai_onay", nihai_onay)
    g.add_node("cikti", cikti)

    g.add_edge(START, "alim")
    g.add_edge("alim", "siniflandirma")
    g.add_conditional_edges("siniflandirma", sinif_yonu)
    g.add_edge("tur_dogrulama", "icerik_analiz")
    g.add_conditional_edges("icerik_analiz", eksik_yonu)
    g.add_conditional_edges("eksik_kapisi", kapi_yonu)
    g.add_edge("mevzuat", "taslak")
    g.add_edge("yonlendirme", "taslak")
    g.add_edge("taslak", "denetim")
    g.add_conditional_edges("denetim", denetim_yonu)
    g.add_conditional_edges("nihai_onay", onay_yonu)
    g.add_edge("cikti", END)

    return g.compile(checkpointer=checkpointer or MemorySaver())


def bekleyen_kesme(graf, cfg, sonuc: dict | None = None):
    """Sürümler arası dayanıklı kesme (interrupt) yakalayıcı.

    Önce invoke/stream sonucundaki '__interrupt__' anahtarına, yoksa checkpoint
    anlık görüntüsündeki bekleyen görevlere bakar. Kesme yoksa None döner.
    """
    if sonuc and "__interrupt__" in sonuc:
        kesmeler = sonuc["__interrupt__"]
        if kesmeler:
            return kesmeler[0].value
    try:
        anlik = graf.get_state(cfg)
    except Exception:
        return None
    for gorev in getattr(anlik, "tasks", ()) or ():
        kesmeler = getattr(gorev, "interrupts", ()) or ()
        if kesmeler:
            return kesmeler[0].value
    return None
