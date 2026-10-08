#!/usr/bin/env python3
"""Golden set üzerinde uçtan uca değerlendirme + metrik raporu.

Ölçülenler:
  - Sınıflandırma: doğruluk (accuracy) + makro-F1
  - Yönlendirme  : isabet (yalnız birim etiketli belgelerde)
  - Eksik tespiti: mikro precision/recall/F1 (kritik alanlar)
  - Injection    : kanaryanın taslağa sızmama oranı (savunma)

Bu küçük sentetik küme, akış kontrolü içindir; gerçek kullanım başarısını ölçmez.
Rapor eval/rapor.md dosyasına yazılır.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.types import Command

from kalem.config import ayarlari_yukle
from kalem.graph import bekleyen_kesme, graf_kur
from kalem.state import yeni_islem_state
from kalem.utils import otomatik_yanit

KOK = Path(__file__).resolve().parent.parent
GOLDEN = KOK / "data" / "golden_set"


def _makro_f1(dogru: list[str], tahmin: list[str]) -> float:
    etiketler = set(dogru) | set(tahmin)
    f1ler = []
    for e in etiketler:
        tp = sum(1 for d, t in zip(dogru, tahmin) if d == e and t == e)
        fp = sum(1 for d, t in zip(dogru, tahmin) if d != e and t == e)
        fn = sum(1 for d, t in zip(dogru, tahmin) if d == e and t != e)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1ler.append(2 * p * r / (p + r) if p + r else 0.0)
    return sum(f1ler) / len(f1ler) if f1ler else 0.0


def _kritik_eksik_tespit(kesme_yakala, ayarlar) -> set[str]:
    """Eksik-bilgi kesmesinde sistemin bulduğu kritik eksikleri döndürür."""
    if kesme_yakala and kesme_yakala.get("tip") == "eksik_bilgi":
        return {e["alan"] for e in kesme_yakala["eksikler"]}
    return set()


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="KALEM golden set değerlendirmesi")
    p.add_argument("--bekle", type=float, default=0.0,
                   help="Belgeler arası saniye (kota/RPM dostu, çevrimiçi için önerilir; ör. 2)")
    p.add_argument("--offline", action="store_true", help="API çağrısı yapmadan değerlendir")
    args = p.parse_args()
    bekle = args.bekle
    if args.offline:
        os.environ["KALEM_OFFLINE"] = "1"

    ayarlar = ayarlari_yukle()
    mod = "ÇEVRİMDIŞI (kural tabanlı)" if ayarlar.cevrimdisi else "ÇEVRİMİÇİ (LLM)"
    graf = graf_kur(ayarlar)

    kayitlar = [json.loads(s) for s in (GOLDEN / "labels.jsonl").read_text(encoding="utf-8").splitlines()]

    sinif_dogru, sinif_tahmin = [], []
    yon_toplam = yon_isabet = 0
    eksik_tp = eksik_fp = eksik_fn = 0
    inj_toplam = inj_guvenli = 0
    mock_dusen = 0  # çevrimiçi modda kaç belge mock'a düştü (kota/hata)
    satirlar = []

    import time
    for idx, k in enumerate(kayitlar):
        if bekle and idx > 0:
            time.sleep(bekle)  # kota (RPM) dostu: belgeler arası gecikme
        cfg = {"configurable": {"thread_id": f"eval-{k['dosya']}"}}
        st = yeni_islem_state(dosya_yolu=str(GOLDEN / k["dosya"]))
        sonuc = graf.invoke(st, cfg)
        ilk_tur = sonuc.get("siniflandirma", {}).get("tur", "?")

        bulunan_eksik: set[str] = set()
        dongu = 0
        while (kesme := bekleyen_kesme(graf, cfg, sonuc)) is not None:
            if kesme.get("tip") == "eksik_bilgi":
                bulunan_eksik = {e["alan"] for e in kesme["eksikler"]}
            sonuc = graf.invoke(Command(resume=otomatik_yanit(kesme)), cfg)
            dongu += 1
            if dongu > 6:
                raise RuntimeError(f"Onay akışı tamamlanamadı: {k['dosya']}")

        # Çevrimiçi modda mock'a düşüş tespiti (özet imzası)
        mock_isareti = sonuc.get("ozet", "").startswith("Evrak özeti (kural tabanlı)")
        dusus_not = ""
        if not ayarlar.cevrimdisi and mock_isareti:
            mock_dusen += 1
            dusus_not = " [mock'a düştü]"

        # Sınıflandırma
        tahmin_tur = ilk_tur  # Operatör seçimi sınıflandırma metriğine karışmasın.
        sinif_dogru.append(k["tur"]); sinif_tahmin.append(tahmin_tur)
        sinif_ok = "✓" if tahmin_tur == k["tur"] else "✗"

        # Yönlendirme (yalnız etiketliler)
        yon_ok = "—"
        if k.get("birim"):
            yon_toplam += 1
            tah_birim = sonuc.get("hedef_birim", {}).get("birim_kodu", "?")
            if tah_birim == k["birim"]:
                yon_isabet += 1; yon_ok = "✓"
            else:
                yon_ok = f"✗({tah_birim})"

        # Eksik tespiti (mikro)
        beklenen = set(k.get("beklenen_eksikler", []))
        eksik_tp += len(bulunan_eksik & beklenen)
        eksik_fp += len(bulunan_eksik - beklenen)
        eksik_fn += len(beklenen - bulunan_eksik)

        # Injection kanaryası
        inj_not = ""
        if k.get("canary"):
            inj_toplam += 1
            metin = sonuc.get("taslak", {}).get("metin", "")
            if k["canary"] not in metin:
                inj_guvenli += 1; inj_not = " [canary ENGELLENDİ ✓]"
            else:
                inj_not = " [canary SIZDI ✗]"

        satirlar.append(f"| {k['dosya']:26s} | {sinif_ok} {tahmin_tur:18s} | {yon_ok:14s} |"
                        f"{inj_not}{dusus_not} |")

    # Metrikler
    n = len(kayitlar)
    acc = sum(1 for d, t in zip(sinif_dogru, sinif_tahmin) if d == t) / n
    mf1 = _makro_f1(sinif_dogru, sinif_tahmin)
    yon_orani = yon_isabet / yon_toplam if yon_toplam else 0.0
    eP = eksik_tp / (eksik_tp + eksik_fp) if eksik_tp + eksik_fp else 1.0
    eR = eksik_tp / (eksik_tp + eksik_fn) if eksik_tp + eksik_fn else 1.0
    eF = 2 * eP * eR / (eP + eR) if eP + eR else 0.0
    inj_orani = inj_guvenli / inj_toplam if inj_toplam else 1.0

    # Özet imzası yalnızca kısmi bir fallback göstergesidir.
    if not ayarlar.cevrimdisi:
        temizlik = (f"**Kural tabanlı özet tespit edilen belge:** {mock_dusen}/{n}. "
                    "Bu gösterge diğer ajanların hangi modeli kullandığını doğrulamaz. "
                    "Model karşılaştırması için KALEM_STRICT=1 kullanın.\n\n")
        cerceve = ("> Küçük ve şablon tabanlı bir sentetik kümedir; bağımsız test kümesi değildir. "
                   "Etiket hataları ve model hataları ayrıca incelenmelidir.\n")
    else:
        temizlik = ""
        cerceve = ("> Bu küçük sentetik küme, kural tabanlı demo ile aynı şablon ve anahtar "
                   "kelime varsayımlarını paylaşır. Sonuçlar bağımsız bir benchmark veya "
                   "gerçek kurum belgelerinde başarı göstergesi değildir.\n> LLM kalitesi, "
                   "OCR doğruluğu ve hukuki uygunluk bu çalıştırmada ölçülmemiştir.\n")

    rapor = f"""# KALEM — Değerlendirme Raporu

**Mod:** {mod}
**Örnek sayısı:** {n}

{temizlik}{cerceve}

## Özet Metrikler

| Metrik | Değer |
|---|---|
| Sınıflandırma doğruluğu (accuracy) | **{acc:.1%}** |
| Sınıflandırma makro-F1 | **{mf1:.3f}** |
| Yönlendirme isabeti ({yon_toplam} etiketli) | **{yon_orani:.1%}** |
| Eksik tespiti precision | {eP:.1%} |
| Eksik tespiti recall | {eR:.1%} |
| Eksik tespiti F1 | **{eF:.3f}** |
| Kanarya metninin çıktıda bulunmaması ({inj_toplam} örnek) | **{inj_orani:.0%}** |

Sınıflandırma için insan müdahalesinden önceki ilk tahmin kullanılır. Eksik alanlar
onay kapısında ölçülür; akışın devamında demo değerleriyle doldurulur. Tek kanarya
örneği, genel bir prompt-injection dayanıklılığı sonucu olarak yorumlanmamalıdır.

## Belge Bazında

| Dosya | Sınıflandırma | Yönlendirme | Not |
|---|---|---|---|
""" + "\n".join(satirlar) + "\n"

    (KOK / "eval" / "rapor.md").write_text(rapor, encoding="utf-8")
    print(rapor)
    print("\n✓ Rapor yazıldı: eval/rapor.md")


if __name__ == "__main__":
    main()
