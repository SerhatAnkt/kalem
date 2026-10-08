"""Jinja2 yazı iskeletini üretilen gövde metniyle birleştirir."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from kalem import prompts
from kalem.agents import AjanBaglami
from kalem.state import EvrakState, Taslak, log

_ENV = Environment(loader=FileSystemLoader(Path(__file__).resolve().parent.parent / "templates"),
                   trim_blocks=True, lstrip_blocks=True)

YAZI_TUR_ADLARI = {
    "cevap_yazisi": "Cevap Yazısı",
    "ust_yazi": "Üst Yazı (Havale)",
    "bilgilendirme": "Bilgilendirme Yazısı",
    "eksiklik_bildirim": "Eksiklik Bildirim Yazısı",
}


def _yazi_turu_sec(state: EvrakState, ctx: AjanBaglami) -> str:
    if state.get("eksiklik_modu"):
        return "eksiklik_bildirim"
    tur = state["siniflandirma"]["tur"]
    return ctx.ayarlar.taksonomi[tur].get("varsayilan_yazi_turu", "bilgilendirme")


def _alan(state: EvrakState, ad: str, varsayilan: str = "") -> str:
    return state.get("cikarilan_alanlar", {}).get(ad, {}).get("deger", "") or varsayilan


def calistir(state: EvrakState, ctx: AjanBaglami) -> dict:
    yazi_turu = _yazi_turu_sec(state, ctx)
    kurum = ctx.ayarlar.kurum
    tur_adi = ctx.ayarlar.taksonomi[state["siniflandirma"]["tur"]]["ad"]
    birim = (state.get("hedef_birim") or {}).get("birim", kurum["varsayilan_birim"])
    mevzuat = state.get("ilgili_mevzuat", [])
    muhatap = (_alan(state, "gonderen_kurum") or _alan(state, "gonderen_ad_soyad")
               or "İLGİLİ MAKAMA")

    # Kurumlar arası yazıda üst/eş makama "arz", şahsa/alt birime "rica" (yalınlaştırılmış kural)
    kapanis = "arz ederim." if state["siniflandirma"]["tur"] == "resmi_yazi_gelen" else "rica ederim."

    # Revizyon bağlamı: Denetim bulguları veya insan revizyon notu gövde prompt'una girer
    rev_parcalar = []
    if state.get("revizyon_notu"):
        rev_parcalar.append(f"Kullanıcının revizyon talebi: {state['revizyon_notu']}")
    if state.get("denetim_raporu", {}).get("sonuc") == "KALDI":
        bulgular = "; ".join(b["mesaj"] for b in state["denetim_raporu"]["bulgular"])
        rev_parcalar.append(f"Önceki taslağın denetim bulguları (düzelt): {bulgular}")
    revizyon_blok = ("\nDÜZELTME BAĞLAMI:\n" + "\n".join(rev_parcalar) + "\n") if rev_parcalar else ""

    if yazi_turu == "eksiklik_bildirim":
        govde = _eksiklik_govdesi(state)
    else:
        mevzuat_str = ("; ".join(f"{m['kaynak']} md.{m['madde_no']}" for m in mevzuat)
                       or "(atıf kullanma)")
        kullanici = prompts.TASLAK_GOVDE.format(
            yazi_turu_adi=YAZI_TUR_ADLARI[yazi_turu], kapanis=kapanis, tur_adi=tur_adi,
            ozet=state.get("ozet", ""),
            alanlar={k: v["deger"] for k, v in state.get("cikarilan_alanlar", {}).items()},
            birim=birim, mevzuat=mevzuat_str, revizyon_blok=revizyon_blok,
        )
        govde = ctx.istemci.uret("taslak_govde", prompts.SISTEM_KURALLARI, kullanici, katman="ana")

    sablon = _ENV.get_template(f"{yazi_turu}.j2")
    metin = sablon.render(
        kurum_adi=kurum["ad"], birim_adi=birim, muhatap=muhatap,
        sayi=f"E-{state['islem_id'][:8].upper()}",
        konu=_alan(state, "konu", tur_adi),
        tarih=date.today().strftime("%d.%m.%Y"),
        ilgi=_ilgi_satiri(state), govde=govde.strip(),
        mevzuat_atiflari=mevzuat, eksikler=state.get("eksik_alanlar", []),
        imza_ad=kurum["imza_ad"], imza_unvan=kurum["imza_unvan"],
        dusuk_guven=state.get("dusuk_guven", False),
    )
    surum = len(state.get("taslak_gecmisi", [])) + 1
    t = Taslak(tur=yazi_turu, metin=metin, surum_no=surum)
    return {
        "taslak": t.model_dump(),
        "taslak_gecmisi": state.get("taslak_gecmisi", []) + [t.model_dump()],
        "revizyon_notu": "",
        "islem_gecmisi": [log("taslak", f"{YAZI_TUR_ADLARI[yazi_turu]} üretildi (sürüm {surum})")],
    }


def _ilgi_satiri(state: EvrakState) -> str:
    sayi = _alan(state, "sayi")
    tarih = _alan(state, "tarih")
    if sayi or tarih:
        return f"{tarih} tarihli{' ve ' + sayi + ' sayılı' if sayi else ''} yazınız."
    return ""


def _eksiklik_govdesi(state: EvrakState) -> str:
    """Eksiklik yazısının gövdesi deterministiktir: kaynağı zaten kural tabanı."""
    satirlar = [f"  - {e['alan'].replace('_', ' ')} ({e['dayanak']})"
                for e in state.get("eksik_alanlar", []) if e["kritiklik"] == "kritik"]
    return ("Kurumumuza intikal eden başvurunuz incelenmiş olup, işleme alınabilmesi için "
            "aşağıda belirtilen zorunlu bilgi/belgelerin eksik olduğu tespit edilmiştir:\n\n"
            + "\n".join(satirlar) +
            "\n\nSöz konusu eksikliklerin tamamlanarak kurumumuza iletilmesi hâlinde "
            "başvurunuz işleme alınacaktır.\n\nBilgilerinizi ve gereğini rica ederim.")
