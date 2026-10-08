"""Operatör girişleri eksik veya belirsiz olduğunda akışın davranışı."""
from langgraph.types import Command

from kalem.config import KOK, ayarlari_yukle
from kalem.graph import bekleyen_kesme, graf_kur
from kalem.state import yeni_islem_state


def test_bos_cevap_kritik_eksigi_atlamaz():
    graf = graf_kur()
    cfg = {"configurable": {"thread_id": "bos-cevap"}}
    state = yeni_islem_state(
        dosya_yolu=str(KOK / "data/ornek_evraklar/dilekce_eksik_adres.txt"))
    graf.invoke(state, cfg)

    sonuc = graf.invoke(Command(resume={"secim": "tamamla", "cevaplar": {"adres": "  "}}), cfg)
    kesme = bekleyen_kesme(graf, cfg, sonuc)
    assert kesme["tip"] == "eksik_bilgi"
    assert "taslak" not in sonuc
    assert "adres" in {e["alan"] for e in kesme["eksikler"]}

    sonuc = graf.invoke(Command(resume={"secim": "eksiklik_yazisi"}), cfg)
    assert bekleyen_kesme(graf, cfg, sonuc)["tip"] == "nihai_onay"
    assert sonuc["taslak"]["tur"] == "eksiklik_bildirim"


def test_tur_dogrulamada_tum_siniflar_secilir():
    graf = graf_kur()
    cfg = {"configurable": {"thread_id": "tum-turler"}}
    sonuc = graf.invoke(yeni_islem_state(metin="Bugün hava güzel."), cfg)
    kesme = bekleyen_kesme(graf, cfg, sonuc)
    assert kesme["tip"] == "tur_dogrulama"
    assert set(kesme["adaylar"]) == set(ayarlari_yukle().taksonomi)


def test_operator_girdisi_de_maskelenir():
    graf = graf_kur()
    cfg = {"configurable": {"thread_id": "maskele"}}
    state = yeni_islem_state(
        dosya_yolu=str(KOK / "data/ornek_evraklar/dilekce_eksik_adres.txt"))
    graf.invoke(state, cfg)
    sonuc = graf.invoke(Command(resume={
        "secim": "tamamla", "cevaplar": {"adres": "Örnek Mah. test@example.com"}}), cfg)
    assert "test@example.com" not in sonuc["cikarilan_alanlar"]["adres"]["deger"]
    assert "eposta" in sonuc["pii_tespitleri"]
