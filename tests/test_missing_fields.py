from kalem.agents.icerik_analiz import eksikleri_bul

KURALLAR = {
    "dilekce": [
        {"alan": "gonderen_ad_soyad", "kritiklik": "kritik", "dayanak": "3071 md.4"},
        {"alan": "adres", "kritiklik": "kritik", "dayanak": "3071 md.4"},
        {"alan": "tarih", "kritiklik": "onemli", "dayanak": "süre"},
    ]
}


def test_eksik_adres_tespit():
    alanlar = {"gonderen_ad_soyad": {"deger": "Ayşe Y."}, "tarih": {"deger": "01.01.2026"}}
    eksik = eksikleri_bul("dilekce", alanlar, KURALLAR)
    adlar = {e.alan for e in eksik}
    assert "adres" in adlar
    assert "gonderen_ad_soyad" not in adlar


def test_tam_belge_eksiksiz():
    alanlar = {"gonderen_ad_soyad": {"deger": "A"}, "adres": {"deger": "B"},
               "tarih": {"deger": "C"}}
    assert eksikleri_bul("dilekce", alanlar, KURALLAR) == []


def test_bos_deger_eksik_sayilir():
    alanlar = {"gonderen_ad_soyad": {"deger": "  "}, "adres": {"deger": "X"}}
    eksik = {e.alan for e in eksikleri_bul("dilekce", alanlar, KURALLAR)}
    assert "gonderen_ad_soyad" in eksik  # yalnızca boşluk = eksik
