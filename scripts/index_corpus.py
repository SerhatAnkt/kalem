#!/usr/bin/env python3
"""Mevzuat korpusunu indeksler (BM25 + opsiyonel dense).

Kullanım:
  python scripts/index_corpus.py            # dense denemeli (kurulu ise)
  python scripts/index_corpus.py --bm25     # yalnızca BM25 (hızlı, CPU-dostu)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kalem.config import ayarlari_yukle
from kalem.rag.indexer import indeks_kur


def main() -> None:
    p = argparse.ArgumentParser(description="KALEM mevzuat indeksleyici")
    p.add_argument("--bm25", action="store_true", help="Yalnızca BM25 (dense atla)")
    args = p.parse_args()

    ayarlar = ayarlari_yukle()
    rapor = indeks_kur(ayarlar, dense=not args.bm25)
    print("İndeksleme tamamlandı:")
    for k, v in rapor.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
