from kalem.ingestion.confidence import metin_guveni


def test_resmi_metin_yuksek_guven():
    metin = ("ÖRNEK KURUM BAŞKANLIĞINA. Konu ile ilgili gereğinin yapılmasını "
             "bilgilerinize saygılarımla arz ederim. Tarih ve sayı eklidir.")
    assert metin_guveni(metin) > 0.7


def test_bozuk_metin_dusuk_guven():
    metin = "@@@ ### %%% xz kq vb nm ~~~ ||| \\\\\\ 000 ??? !!!"
    assert metin_guveni(metin) < 0.3


def test_cok_kisa_metin_sifir():
    assert metin_guveni("kısa") == 0.0
