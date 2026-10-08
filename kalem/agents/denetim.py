"""7 · Denetim Ajanı (Kontrol Memuru).

İki katman:
A) Deterministik kontroller (her modda çalışır, ölçülebilir):
   format unsurları, kapanış formülü, maskesiz TC taraması, KAYNAKSIZ MEVZUAT
   ATFI çapraz doğrulaması (halüsinasyon yakalayıcı), teyit işaretleri, uzunluk.
B) LLM üslup değerlendirmesi (çevrimiçi modda, yalnız 'uyarı' seviyesinde).

KALDI kararını yalnızca 'kritik' bulgular verir. KALDI'da revizyon sayacı artar.
"""
from __future__ import annotations

import re

from kalem import prompts
from kalem.agents import AjanBaglami
from kalem.security import maskesiz_tc_var_mi, sarmala_belge
from kalem.state import DenetimBulgusu, DenetimRaporu, EvrakState, log

# Gerçek mevzuat atfı: "NNNN sayılı Kanun/Yönetmelik/KHK...". Ardından mevzuat türü
# GELMEYEN "sayılı" kullanımları (ör. "...2026 sayılı yazınız", "300-45 sayılı yazı")
# belge referansıdır, kanun atfı DEĞİLDİR → yanlış alarm vermesin diye tür şartı eklenir.
_KANUN_ATIF = re.compile(
    r"\b(\d{3,4})\s+say[ıi]l[ıi]\s+"
    r"(?:[^\s.]+\s+){0,4}"   # araya kanun adı girebilir (ör. "Bilgi Edinme Hakkı"), nokta/cümle sınırı aşılmaz
    r"(?:kanun|yönetmelik|yonetmelik|khk|kararname|tüzük|tuzuk|genelge|tebliğ|teblig)",
    re.I)


def _deterministik(state: EvrakState) -> list[DenetimBulgusu]:
    metin = state["taslak"]["metin"]
    b: list[DenetimBulgusu] = []

    for etiket in ("Sayı", "Konu"):
        if f"{etiket}" not in metin:
            b.append(DenetimBulgusu(kural="format", seviye="kritik",
                                    mesaj=f"Zorunlu unsur eksik: {etiket}"))
    if not re.search(r"(arz|rica)(\s+ve\s+rica)?\s+ederim", metin, re.I):
        b.append(DenetimBulgusu(kural="format", seviye="kritik",
                                mesaj="Resmî kapanış formülü (arz/rica ederim) yok"))
    if maskesiz_tc_var_mi(metin):
        b.append(DenetimBulgusu(kural="kvkk", seviye="kritik",
                                mesaj="Taslakta maskesiz TC kimlik numarası tespit edildi"))

    # Kaynaksız atıf: taslaktaki her '#### sayılı' ifadesi, Mevzuat Ajanı'nın
    # getirdiği kaynaklarda geçmek zorunda. (LLM'in serbest atıf uydurmasını yakalar.)
    izinli = " ".join(m["kaynak"] + " " + m["madde_no"] for m in state.get("ilgili_mevzuat", []))
    izinli += " " + " ".join(e.get("dayanak", "") for e in state.get("eksik_alanlar", []))
    for m in _KANUN_ATIF.finditer(metin):
        if m.group(1) not in izinli:
            b.append(DenetimBulgusu(kural="kaynak_dogruluk", seviye="kritik",
                                    mesaj=f"Kaynaksız mevzuat atfı: {m.group(0)} "
                                          f"(getirilen atıf listesinde yok)"))

    teyit = metin.count("[TEYİT EDİLECEK")
    if teyit:
        b.append(DenetimBulgusu(kural="teyit", seviye="uyari",
                                mesaj=f"{teyit} adet teyit bekleyen ifade var"))
    if len(metin.split()) < 40:
        b.append(DenetimBulgusu(kural="icerik", seviye="uyari", mesaj="Gövde beklenenden kısa"))
    if state.get("dusuk_guven"):
        b.append(DenetimBulgusu(kural="ocr", seviye="uyari",
                                mesaj="Kaynak belge düşük OCR güvenli; alanlar teyit edilmeli"))
    return b


def calistir(state: EvrakState, ctx: AjanBaglami) -> dict:
    bulgular = _deterministik(state)

    if not ctx.ayarlar.cevrimdisi:
        try:
            ham = ctx.istemci.uret("denetim_uslup", prompts.SISTEM_KURALLARI,
                                   prompts.DENETIM_USLUP.format(
                                       belge=sarmala_belge(state["taslak"]["metin"])),
                                   katman="ana")
            from kalem.utils import json_ayikla
            u = json_ayikla(ham)
            if not u.get("uygun", True):
                for n in u.get("notlar", [])[:3]:
                    bulgular.append(DenetimBulgusu(kural="uslup", seviye="uyari", mesaj=str(n)))
        except Exception:
            if ctx.ayarlar.kati:
                raise
            bulgular.append(DenetimBulgusu(
                kural="uslup", seviye="uyari", mesaj="LLM üslup kontrolü tamamlanamadı"))

    sonuc = "KALDI" if any(x.seviye == "kritik" for x in bulgular) else "GECTI"
    rapor = DenetimRaporu(sonuc=sonuc, bulgular=bulgular)
    guncelleme: dict = {
        "denetim_raporu": rapor.model_dump(),
        "islem_gecmisi": [log("denetim", f"Sonuç: {sonuc} ({len(bulgular)} bulgu)")],
    }
    if sonuc == "KALDI":
        guncelleme["revizyon_sayisi"] = state.get("revizyon_sayisi", 0) + 1
    return guncelleme
