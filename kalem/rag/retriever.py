"""BM25 ve isteğe bağlı dense sonuçlarını RRF ile sıralar."""
from __future__ import annotations

import pickle

from kalem.config import Ayarlar
from kalem.state import MevzuatAtfi
from kalem.utils import tokenize

RRF_K = 60


class MevzuatGetirici:
    def __init__(self, ayarlar: Ayarlar):
        self.a = ayarlar
        self._bm25 = None
        self._parcalar: list[tuple[str, str, str]] = []
        self._dense = None       # (model, koleksiyon) | None
        self._yuklendi = False

    def _yukle(self) -> None:
        if self._yuklendi:
            return
        self._yuklendi = True
        yol = self.a.yol("indeks_dizini") / "bm25.pkl"
        if not yol.exists():
            return  # indekslenmemiş: aramalar boş döner (kapı yerine dürüst boşluk)
        with open(yol, "rb") as f:
            veri = pickle.load(f)
        self._bm25, self._parcalar = veri["bm25"], veri["parcalar"]
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
            from kalem.rag.indexer import EMBED_MODEL

            istemci = chromadb.PersistentClient(path=str(self.a.yol("indeks_dizini") / "chroma"))
            kol = istemci.get_collection("mevzuat")
            self._dense = (SentenceTransformer(EMBED_MODEL), kol)
        except Exception:
            self._dense = None  # BM25-tek mod

    def ara(self, sorgu: str, k: int | None = None) -> list[MevzuatAtfi]:
        self._yukle()
        if self._bm25 is None:
            return []
        k = k or self.a.esikler["mevzuat_k"]

        bm_skorlar = self._bm25.get_scores(tokenize(sorgu))
        bm_sira = sorted(range(len(bm_skorlar)), key=lambda i: bm_skorlar[i], reverse=True)

        # Mutlak alt eşik: en iyi BM25 skoru bile zayıfsa ilgili mevzuat yok say.
        if not bm_sira or bm_skorlar[bm_sira[0]] < self.a.esikler["mevzuat_min_skor"]:
            return []

        rrf: dict[int, float] = {}
        for sira, i in enumerate(bm_sira[: k * 3]):
            rrf[i] = rrf.get(i, 0.0) + 1.0 / (RRF_K + sira + 1)
        if self._dense is not None:
            model, kol = self._dense
            v = model.encode([sorgu], normalize_embeddings=True)[0].tolist()
            sonuc = kol.query(query_embeddings=[v], n_results=k * 3)
            for sira, kimlik in enumerate(sonuc["ids"][0]):
                i = int(kimlik)
                rrf[i] = rrf.get(i, 0.0) + 1.0 / (RRF_K + sira + 1)

        secilen = sorted(rrf, key=rrf.get, reverse=True)[:k]
        atiflar = []
        for i in secilen:
            kaynak, madde, metin = self._parcalar[i]
            atiflar.append(MevzuatAtfi(kaynak=kaynak, madde_no=madde,
                                       alinti=metin[:400], skor=round(rrf[i], 4)))
        return atiflar
