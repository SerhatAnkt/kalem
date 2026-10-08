import pytest

from kalem.config import ayarlari_yukle
from kalem.rag.indexer import indeks_kur
from kalem.rag.retriever import MevzuatGetirici


@pytest.fixture(scope="module")
def getirici():
    a = ayarlari_yukle()
    indeks_kur(a, dense=False)  # gerçek korpusla BM25 indeks
    return MevzuatGetirici(a)


def test_dilekce_sorgusu_3071_bulur(getirici):
    sonuc = getirici.ara("dilekçe adres imza soyadı zorunlu unsurlar başvuru")
    kaynaklar = " ".join(m.kaynak for m in sonuc)
    assert "3071" in kaynaklar


def test_alakasiz_sorgu_bos_doner(getirici):
    # Kapalı korpus + eşik: alakasız sorgu halüsinasyon yerine boş liste vermeli
    sonuc = getirici.ara("uzay mekiği kuantum dolanıklık fotosentez klorofil")
    assert sonuc == []
