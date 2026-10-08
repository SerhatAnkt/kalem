"""İndeks kurucu: BM25 (zorunlu, saf Python) + opsiyonel dense (Chroma+bge-m3).

Dense bacak yalnızca chromadb + sentence-transformers kuruluysa oluşturulur;
yoksa sistem BM25-tek modda tam işlevlidir (donanım bağımsızlık ilkesi).
"""
from __future__ import annotations

import pickle

from rank_bm25 import BM25Okapi

from kalem.config import Ayarlar
from kalem.rag.chunker import korpusu_parcala
from kalem.utils import tokenize

EMBED_MODEL = "BAAI/bge-m3"


def indeks_kur(ayarlar: Ayarlar, dense: bool = True) -> dict:
    mevzuat_dizin = ayarlar.yol("mevzuat_dizini")
    indeks_dizin = ayarlar.yol("indeks_dizini")
    indeks_dizin.mkdir(parents=True, exist_ok=True)

    parcalar = korpusu_parcala(mevzuat_dizin)
    if not parcalar:
        raise RuntimeError(f"Mevzuat korpusu boş: {mevzuat_dizin}")

    dokumanlar = [f"{p.kaynak} madde {p.madde_no} {p.metin}" for p in parcalar]
    bm25 = BM25Okapi([tokenize(d) for d in dokumanlar])
    with open(indeks_dizin / "bm25.pkl", "wb") as f:
        pickle.dump({"bm25": bm25,
                     "parcalar": [(p.kaynak, p.madde_no, p.metin) for p in parcalar]}, f)

    rapor = {"parca_sayisi": len(parcalar), "bm25": True, "dense": False}
    if dense:
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(EMBED_MODEL)
            vektorler = model.encode([p.metin for p in parcalar], normalize_embeddings=True)
            istemci = chromadb.PersistentClient(path=str(indeks_dizin / "chroma"))
            try:
                istemci.delete_collection("mevzuat")
            except Exception:
                pass
            kol = istemci.create_collection("mevzuat", metadata={"hnsw:space": "cosine"})
            kol.add(ids=[str(i) for i in range(len(parcalar))],
                    embeddings=[v.tolist() for v in vektorler],
                    metadatas=[{"kaynak": p.kaynak, "madde_no": p.madde_no} for p in parcalar],
                    documents=[p.metin for p in parcalar])
            rapor["dense"] = True
        except ImportError:
            rapor["not"] = "chromadb/sentence-transformers yok → BM25-tek mod"
    return rapor
