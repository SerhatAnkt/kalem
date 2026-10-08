"""Güvenlik ve KVKK katmanı.

1) TC kimlik no: 11 hane + algoritmik sağlama (checksum) doğrulaması; doğrulanan
   numaralar loglara/prompta girmeden maskelenir.
2) Prompt injection savunması: kuruma gelen evrakın içindeki metin *veridir*,
   talimat değildir. Belge içeriği her prompt'ta <belge> etiketiyle sarmalanır ve
   sistem kuralı bunu açıkça belirtir (bkz. prompts.SISTEM_KURALLARI).
"""
from __future__ import annotations

import re

_TC_DESEN = re.compile(r"\b[1-9]\d{10}\b")
_EPOSTA = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def tc_gecerli(no: str) -> bool:
    """Resmî TC kimlik sağlama algoritması."""
    if not re.fullmatch(r"[1-9]\d{10}", no):
        return False
    d = [int(c) for c in no]
    tek = d[0] + d[2] + d[4] + d[6] + d[8]
    cift = d[1] + d[3] + d[5] + d[7]
    if (tek * 7 - cift) % 10 != d[9]:
        return False
    return sum(d[:10]) % 10 == d[10]


def kisisel_veri_maskele(metin: str) -> tuple[str, list[str]]:
    """Metindeki doğrulanmış TC no ve e-postaları maskeler.

    Dönüş: (maskeli_metin, tespit_listesi). Maske deseni son 2 hane açık bırakır
    ki insan operatör gerektiğinde fiziki evrakla eşleştirebilsin.
    """
    tespitler: list[str] = []

    def _tc(m: re.Match) -> str:
        if tc_gecerli(m.group(0)):
            tespitler.append("tc_kimlik")
            return "*********" + m.group(0)[-2:]
        return m.group(0)

    metin = _TC_DESEN.sub(_tc, metin)
    if _EPOSTA.search(metin):
        tespitler.append("eposta")
        metin = _EPOSTA.sub("[e-posta maskelendi]", metin)
    return metin, tespitler


def maskesiz_tc_var_mi(metin: str) -> bool:
    """Denetim Ajanı kontrolü: taslakta maskesiz-geçerli TC kalmış mı?"""
    return any(tc_gecerli(m.group(0)) for m in _TC_DESEN.finditer(metin))


def sarmala_belge(metin: str) -> str:
    """Belge içeriğini prompt'a veri olarak gömer (injection sınırı)."""
    temiz = metin.replace("<belge>", "(belge)").replace("</belge>", "(/belge)")
    return f"<belge>\n{temiz}\n</belge>"
