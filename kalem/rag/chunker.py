"""Madde-bazlı parçalama: mevzuat metni rastgele pencerelerle değil, MADDE
sınırlarından bölünür → her parça atıf yapılabilir bir birimdir.

Dosya biçimi (data/mevzuat/*.txt):
  1. satır  : KAYNAK: <mevzuatın tam adı>
  devamı    : "MADDE 4 - ..." satırlarıyla başlayan madde metinleri
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_MADDE = re.compile(r"(?im)^\s*madde\s+(\d+)\s*[-–—.]?\s*")


@dataclass
class MevzuatParcasi:
    kaynak: str
    madde_no: str
    metin: str


def dosyayi_parcala(yol: Path) -> list[MevzuatParcasi]:
    icerik = yol.read_text(encoding="utf-8")
    satirlar = icerik.splitlines()
    kaynak = yol.stem
    govde_baslangic = 0
    for i, s in enumerate(satirlar[:5]):
        if s.upper().startswith("KAYNAK:"):
            kaynak = s.split(":", 1)[1].strip()
            govde_baslangic = i + 1
            break
    govde = "\n".join(satirlar[govde_baslangic:])

    parcalar: list[MevzuatParcasi] = []
    eslesmeler = list(_MADDE.finditer(govde))
    for j, m in enumerate(eslesmeler):
        son = eslesmeler[j + 1].start() if j + 1 < len(eslesmeler) else len(govde)
        metin = govde[m.start():son].strip()
        parcalar.append(MevzuatParcasi(kaynak=kaynak, madde_no=m.group(1), metin=metin))
    if not parcalar and govde.strip():  # maddesiz metin: tek parça (genelge vb.)
        parcalar.append(MevzuatParcasi(kaynak=kaynak, madde_no="-", metin=govde.strip()))
    return parcalar


def korpusu_parcala(dizin: Path) -> list[MevzuatParcasi]:
    parcalar: list[MevzuatParcasi] = []
    for yol in sorted(dizin.glob("*.txt")):
        parcalar.extend(dosyayi_parcala(yol))
    return parcalar
