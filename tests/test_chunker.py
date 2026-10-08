from kalem.rag.chunker import dosyayi_parcala


def test_madde_bazli_parcalama(tmp_path):
    dosya = tmp_path / "test_mevzuat.txt"
    dosya.write_text(
        "KAYNAK: Test Kanunu 1234\n"
        "MADDE 4 - Birinci madde metni burada yer alır.\n"
        "MADDE 5 - İkinci madde metni de burada.\n",
        encoding="utf-8")
    parcalar = dosyayi_parcala(dosya)
    assert len(parcalar) == 2
    assert parcalar[0].kaynak == "Test Kanunu 1234"
    assert parcalar[0].madde_no == "4"
    assert "Birinci madde" in parcalar[0].metin
    assert parcalar[1].madde_no == "5"


def test_kaynak_satiri_chunka_girmez(tmp_path):
    dosya = tmp_path / "m.txt"
    dosya.write_text("KAYNAK: X\nNOT: özet\nMADDE 1 - içerik\n", encoding="utf-8")
    parcalar = dosyayi_parcala(dosya)
    assert len(parcalar) == 1
    assert "KAYNAK" not in parcalar[0].metin
