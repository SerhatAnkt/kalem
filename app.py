#!/usr/bin/env python3
"""KALEM — Streamlit arayüzü.

Özellikler:
- Canlı ajan akışı (her düğüm bittiğinde işlem izi güncellenir)
- İnsan-onay kapıları interaktif formlarla (tür doğrulama, eksik bilgi, nihai onay)
- Görev 1 panelleri (sınıflandırma, çıkarılan alanlar, eksikler, mevzuat, özet)
- Görev 2 çıktısı (resmî yazı taslağı + denetim raporu + DOCX indirme)

Çalıştırma:  streamlit run app.py
Çevrimiçi mod için .env dosyasına GEMINI_API_KEY veya GROQ_API_KEY girin.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from langgraph.types import Command

from kalem.config import ayarlari_yukle
from kalem.graph import graf_kur
from kalem.state import yeni_islem_state

st.set_page_config(page_title="KALEM · Kamu Evrak Ajanı", page_icon="📄", layout="wide")


@st.cache_resource
def _graf_ve_ayar():
    ayarlar = ayarlari_yukle()
    return graf_kur(ayarlar), ayarlar


graf, ayarlar = _graf_ve_ayar()

# oturum durumu
ss = st.session_state
ss.setdefault("thread_id", None)
ss.setdefault("kesme", None)
ss.setdefault("son_state", None)
ss.setdefault("gecmis", [])
ss.setdefault("bitti", False)


def _cfg():
    return {"configurable": {"thread_id": ss.thread_id}}


def _akisi_isle(girdi):
    """Grafı çalıştırır; ilk kesmede durur veya biterse sonucu saklar."""
    for parca in graf.stream(girdi, _cfg(), stream_mode="updates"):
        if "__interrupt__" in parca:
            ss.kesme = parca["__interrupt__"][0].value
            return
        for _dugum, guncelleme in parca.items():
            if isinstance(guncelleme, dict):
                ss.gecmis += guncelleme.get("islem_gecmisi", [])
    # Akış kesmesiz bitti
    ss.kesme = None
    ss.son_state = graf.get_state(_cfg()).values
    ss.bitti = True


def _baslat(dosya_yolu=None, metin=None):
    st_ = yeni_islem_state(dosya_yolu=dosya_yolu, metin=metin)
    ss.thread_id = st_["islem_id"]
    ss.gecmis, ss.kesme, ss.son_state, ss.bitti = [], None, None, False
    _akisi_isle(st_)


def _devam(yanit):
    _akisi_isle(Command(resume=yanit))


# kenar çubuğu
with st.sidebar:
    st.title("KALEM")
    st.caption("Kamu Ajanlı Lisan ve Evrak Mimarisi")
    mod = "Çevrimdışı demo · kural tabanlı" if ayarlar.cevrimdisi else "LLM modu · API bağlantısı gerekli"
    st.info(f"**Mod:** {mod}\n\n**Kurum:** {ayarlar.kurum['ad']}")
    st.divider()
    st.markdown("**Girdi**")
    kaynak = st.radio("Kaynak", ["Örnek evrak", "Metin yapıştır", "Dosya yükle"],
                      label_visibility="collapsed")

    baslat_edildi = False
    if kaynak == "Örnek evrak":
        ornek_dizin = Path(__file__).resolve().parent / "data" / "ornek_evraklar"
        secenekler = sorted(p.name for p in ornek_dizin.glob("*.txt"))
        secim = st.selectbox("Örnek seçin", secenekler)
        if st.button("İşle", type="primary", use_container_width=True):
            _baslat(dosya_yolu=str(ornek_dizin / secim)); baslat_edildi = True
    elif kaynak == "Metin yapıştır":
        metin = st.text_area("Evrak metni", height=200)
        if st.button("İşle", type="primary", use_container_width=True) and metin.strip():
            _baslat(metin=metin); baslat_edildi = True
    else:
        yuklenen = st.file_uploader("Dosya (.txt/.pdf/.png)", type=["txt", "pdf", "png", "jpg"])
        if yuklenen and st.button("İşle", type="primary", use_container_width=True):
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=Path(yuklenen.name).suffix, delete=False) as f:
                f.write(yuklenen.getbuffer())
                tmp = Path(f.name)
            try:
                _baslat(dosya_yolu=str(tmp)); baslat_edildi = True
            finally:
                tmp.unlink(missing_ok=True)

    if baslat_edildi:
        st.rerun()

# ana panel
st.title("Kamu Evrak ve Yazışma Ajanı")
st.caption("TEKNOFEST 2026 · Yapay Zekâ Dil Ajanları · Senaryo 1")

if ss.thread_id is None:
    st.markdown("Gelen evrakı inceleyin, eksik bilgileri tamamlayın ve yazı taslağını onaylayın.")
    st.info("İlk deneme için soldan **dilekce_eksik_adres.txt** örneğini seçip **İşle** düğmesine basın.")
    c1, c2, c3 = st.columns(3)
    c1.markdown("**1. Evrakı incele**\n\nTür, özet, alanlar ve eksik bilgiler.")
    c2.markdown("**2. Taslağı değerlendir**\n\nBirim önerisi, kaynaklar ve denetim bulguları.")
    c3.markdown("**3. Onayla ve indir**\n\nDüzenlenebilir taslak ve DOCX çıktısı.")
    st.caption("Örnek evraklar sentetiktir. Çevrimdışı demo API anahtarı ve GPU gerektirmez.")
    st.stop()

# İşlem izi
with st.expander("Ajan işlem izi", expanded=not ss.bitti):
    for k in ss.gecmis:
        st.text(f"[{k['ajan']}] {k['mesaj']}")

# kesme (insan-onay) formları
if ss.kesme:
    k = ss.kesme
    st.warning(f"**Operatör kararı gerekiyor** — {k.get('mesaj', '')}")

    if k["tip"] == "manuel_metin":
        m = st.text_area("Metni yapıştırın", value=k.get("varsayilan", ""), height=200)
        if st.button("Devam et", type="primary"):
            if m.strip():
                _devam({"metin": m}); st.rerun()
            st.error("Devam etmek için belge metnini girin.")

    elif k["tip"] == "tur_dogrulama":
        secim = st.radio("Evrak türü:", k["adaylar"],
                         format_func=lambda x: k["adlar"].get(x, x))
        if st.button("Onayla", type="primary"):
            _devam({"tur": secim}); st.rerun()

    elif k["tip"] == "eksik_bilgi":
        st.markdown("**Eksik kritik alanlar:**")
        cevaplar = {}
        for e in k["eksikler"]:
            cevaplar[e["alan"]] = st.text_input(
                f"{e['alan'].replace('_', ' ')} — _{e.get('dayanak', '')}_", key=f"eks_{e['alan']}")
        c1, c2 = st.columns(2)
        if c1.button("Tamamla ve devam", type="primary"):
            if all(v.strip() for v in cevaplar.values()):
                _devam({"secim": "tamamla", "cevaplar": cevaplar}); st.rerun()
            st.error("Zorunlu alanları doldurun veya eksiklik bildirim yazısını seçin.")
        if c2.button("Eksiklik bildirim yazısı üret"):
            _devam({"secim": "eksiklik_yazisi"}); st.rerun()

    elif k["tip"] == "nihai_onay":
        rapor = k["denetim"]
        renk = "🟢" if rapor["sonuc"] == "GECTI" else "🔴"
        st.markdown(f"**Denetim:** {renk} {rapor['sonuc']} — {len(rapor['bulgular'])} bulgu")
        for b in rapor["bulgular"]:
            st.caption(f"  [{b['seviye']}] {b['mesaj']}")
        yeni_metin = st.text_area("Taslak (düzenleyebilirsiniz):",
                                  value=k["taslak"]["metin"], height=400)
        c1, c2 = st.columns(2)
        if c1.button("Onayla", type="primary"):
            karar = {"karar": "duzenle", "metin": yeni_metin} if yeni_metin != k["taslak"]["metin"] \
                else {"karar": "onayla"}
            _devam(karar); st.rerun()
        with c2:
            not_ = st.text_input("Revizyon notu")
            if st.button("Revizyon iste") and not_:
                _devam({"karar": "revize", "not": not_}); st.rerun()

# sonuç panelleri
if ss.bitti and ss.son_state:
    s = ss.son_state
    st.success("İşlem tamamlandı")

    # Çevrimiçi moda ayarlıyken LLM düşüp mock'a inildiyse kullanıcıyı uyar.
    # Mock özeti her zaman bu ibareyle başlar → düşüşün işareti.
    if not ayarlar.cevrimdisi and s.get("ozet", "").startswith("Evrak özeti (kural tabanlı)"):
        st.error(
            "⚠ **Çevrimiçi moda ayarlısınız ancak LLM çağrısı başarısız oldu; "
            "sistem kural tabanlı yedeğe düştü.** (API'de bu yüzden kullanım görünmez.) "
            "Bağlantı, API anahtarı, model erişimi ve kota ayarlarını kontrol edin.")

    sol, sag = st.columns([1, 1])
    with sol:
        st.subheader("Belge analizi")
        sf = s.get("siniflandirma", {})
        st.metric("Evrak türü", ayarlar.taksonomi.get(sf.get("tur", ""), {}).get("ad", "?"),
                  f"güven {sf.get('guven', 0):.0%}")
        hb = s.get("hedef_birim", {})
        st.metric("Yönlendirilen birim", hb.get("birim", "?"), f"güven {hb.get('guven', 0):.0%}")

        if s.get("ozet"):
            st.markdown("**Özet:** " + s["ozet"])

        alanlar = s.get("cikarilan_alanlar", {})
        if alanlar:
            st.markdown("**Çıkarılan alanlar:**")
            st.json({a: v.get("deger") for a, v in alanlar.items()}, expanded=False)

        eksik = s.get("eksik_alanlar", [])
        if eksik:
            st.markdown("**Eksik alanlar:**")
            for e in eksik:
                im = "🔴" if e["kritiklik"] == "kritik" else "🟡"
                st.caption(f"{im} {e['alan']} — {e.get('dayanak', '')}")

        mev = s.get("ilgili_mevzuat", [])
        if mev:
            st.markdown("**İlgili mevzuat:**")
            for m in mev:
                st.caption(f"{m['kaynak']} md.{m['madde_no']}")

    with sag:
        st.subheader("Yazı taslağı")
        taslak = s.get("taslak", {})
        st.code(taslak.get("metin", ""), language=None, wrap_lines=True, height=550)

        yol = s.get("cikti_yollari", {}).get("docx")
        if yol and Path(yol).exists():
            with open(yol, "rb") as f:
                st.download_button("DOCX indir", f.read(), file_name=Path(yol).name,
                                   mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                   type="primary")
