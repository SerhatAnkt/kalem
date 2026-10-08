#!/usr/bin/env python3
"""Uçtan uca CLI demo sürücüsü.

Kullanım:
  python scripts/demo_cli.py data/ornek_evraklar/dilekce_eksik_adres.txt --otomatik
  python scripts/demo_cli.py --metin "ÖRNEK KURUM... arz ederim" --otomatik
  python scripts/demo_cli.py <dosya>                # interaktif (kapılarda soru sorar)

--otomatik: insan-onay kapıları politika ile otomatik yanıtlanır (demo/eval).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.types import Command

from kalem.config import ayarlari_yukle
from kalem.graph import bekleyen_kesme, graf_kur
from kalem.state import yeni_islem_state
from kalem.utils import otomatik_yanit

CIZGI = "─" * 70


def _interaktif_yanit(kesme: dict) -> dict:
    print(f"\n⏸  [{kesme['tip']}] {kesme.get('mesaj', '')}")
    tip = kesme["tip"]
    if tip == "manuel_metin":
        m = input("   Metni yapıştırın (boş=varsayılan): ").strip()
        return {"metin": m or kesme.get("varsayilan", "")}
    if tip == "tur_dogrulama":
        for i, kod in enumerate(kesme["adaylar"]):
            print(f"     {i}) {kesme['adlar'].get(kod, kod)}")
        s = input("   Seçim (numara): ").strip()
        try:
            return {"tur": kesme["adaylar"][int(s)]}
        except (ValueError, IndexError):
            return {"tur": kesme["adaylar"][0]}
    if tip == "eksik_bilgi":
        print("   Eksik kritik alanlar:", ", ".join(e["alan"] for e in kesme["eksikler"]))
        sec = input("   [t]amamla / [e]ksiklik yazısı üret? ").strip().lower()
        if sec.startswith("e"):
            return {"secim": "eksiklik_yazisi"}
        cevaplar = {}
        for e in kesme["eksikler"]:
            v = input(f"     {e['alan']} = ").strip()
            if v:
                cevaplar[e["alan"]] = v
        return {"secim": "tamamla", "cevaplar": cevaplar}
    if tip == "nihai_onay":
        print(CIZGI); print(kesme["taslak"]["metin"]); print(CIZGI)
        rapor = kesme["denetim"]
        print(f"   Denetim: {rapor['sonuc']} — {len(rapor['bulgular'])} bulgu")
        for b in rapor["bulgular"]:
            print(f"     [{b['seviye']}] {b['mesaj']}")
        sec = input("   [o]nayla / [r]evize? ").strip().lower()
        if sec.startswith("r"):
            return {"karar": "revize", "not": input("   Revizyon notu: ").strip()}
        return {"karar": "onayla"}
    return {}


def main() -> None:
    p = argparse.ArgumentParser(description="KALEM CLI demo")
    p.add_argument("dosya", nargs="?", help="Evrak dosyası (.txt/.pdf/.png)")
    p.add_argument("--metin", help="Dosya yerine doğrudan metin")
    p.add_argument("--otomatik", action="store_true", help="Kapıları otomatik yanıtla")
    p.add_argument("--offline", action="store_true", help="API çağrısı yapmadan çalıştır")
    args = p.parse_args()

    if not args.dosya and not args.metin:
        p.error("Bir dosya yolu ya da --metin verin")
    if args.dosya and not Path(args.dosya).is_file():
        p.error(f"Dosya bulunamadı: {args.dosya}")
    if args.offline:
        os.environ["KALEM_OFFLINE"] = "1"
    if args.otomatik:
        print("Demo modu: eksik alanlara örnek değerler yazılır ve onaylar otomatik verilir.")

    ayarlar = ayarlari_yukle()
    mod = "ÇEVRİMDIŞI (kural tabanlı)" if ayarlar.cevrimdisi else "ÇEVRİMİÇİ (LLM)"
    print(f"KALEM · mod: {mod}\n{CIZGI}")

    graf = graf_kur(ayarlar)
    st = yeni_islem_state(dosya_yolu=args.dosya, metin=args.metin)
    cfg = {"configurable": {"thread_id": st["islem_id"]}}

    sonuc = graf.invoke(st, cfg)
    while (kesme := bekleyen_kesme(graf, cfg, sonuc)) is not None:
        yanit = otomatik_yanit(kesme) if args.otomatik else _interaktif_yanit(kesme)
        if args.otomatik:
            print(f"⏸  [{kesme['tip']}] → otomatik: {yanit}")
        sonuc = graf.invoke(Command(resume=yanit), cfg)

    print(f"\n{CIZGI}\nİŞLEM İZİ:")
    for k in sonuc.get("islem_gecmisi", []):
        print(f"  [{k['ajan']:14s}] {k['mesaj']}")

    print(f"\n{CIZGI}\nNİHAİ TASLAK ({sonuc['taslak']['tur']}):")
    print(CIZGI); print(sonuc["taslak"]["metin"]); print(CIZGI)
    yol = sonuc.get("cikti_yollari", {}).get("docx", "(üretilemedi)")
    print(f"\n✓ Çıktı dosyası: {yol}")


if __name__ == "__main__":
    main()
