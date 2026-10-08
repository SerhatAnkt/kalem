from kalem.security import kisisel_veri_maskele, maskesiz_tc_var_mi, tc_gecerli


def test_gecerli_tc():
    assert tc_gecerli("12345678950")


def test_gecersiz_tc():
    assert not tc_gecerli("12345678901")  # sağlama tutmaz
    assert not tc_gecerli("01234567890")  # sıfırla başlar
    assert not tc_gecerli("123")          # kısa


def test_maskeleme_son_iki_hane_acik():
    metin = "Başvuru sahibi T.C. 12345678950 numaralı kişidir."
    maskeli, tespit = kisisel_veri_maskele(metin)
    assert "12345678950" not in maskeli
    assert "*********50" in maskeli
    assert "tc_kimlik" in tespit


def test_gecersiz_tc_maskelenmez():
    metin = "Sayı 12345678901 bir TC değildir."
    maskeli, _ = kisisel_veri_maskele(metin)
    assert "12345678901" in maskeli  # sağlama tutmadığı için dokunulmaz


def test_maskesiz_tespit():
    assert maskesiz_tc_var_mi("kod 12345678950 burada")
    assert not maskesiz_tc_var_mi("kod *********50 burada")
