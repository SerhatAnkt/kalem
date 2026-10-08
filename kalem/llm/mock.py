"""API gerektirmeyen demo için anahtar kelime, regex ve şablon tabanlı yanıtlar."""
from __future__ import annotations

import json
import re

from kalem.config import Ayarlar
from kalem.utils import tr_kucult


def _belge_icerigi(kullanici: str) -> str:
    m = re.search(r"<belge>\n?(.*?)\n?</belge>", kullanici, flags=re.S)
    return m.group(1) if m else kullanici


class SahteLLM:
    def __init__(self, ayarlar: Ayarlar):
        self.a = ayarlar

    def uret(self, gorev: str, sistem: str, kullanici: str) -> str:
        metin = _belge_icerigi(kullanici)
        if gorev == "siniflandirma":
            return self._siniflandir(metin)
        if gorev == "icerik_analiz":
            return self._analiz(metin, kullanici)
        if gorev == "yonlendirme":
            return self._yonlendir(metin, kullanici)
        if gorev == "taslak_govde":
            return self._govde(kullanici)
        if gorev == "denetim_uslup":
            return json.dumps({"uygun": True, "notlar": []}, ensure_ascii=False)
        return "{}"

    # sınıflandırma: anahtar kelime isabet sayımı
    def _siniflandir(self, metin: str) -> str:
        k = tr_kucult(metin)
        en_iyi, en_sayi = "diger_belirsiz", 0
        for kod, t in self.a.taksonomi.items():
            sayi = sum(1 for ak in t.get("anahtar_kelimeler", []) if tr_kucult(ak) in k)
            if sayi > en_sayi:
                en_iyi, en_sayi = kod, sayi
        guven = 0.4 if en_sayi == 0 else min(0.95, 0.60 + 0.08 * en_sayi)
        aciliyet = "yuksek" if any(s in k for s in ("acil", "ivedi", "derhal")) else "normal"
        return json.dumps({"tur": en_iyi, "aciliyet": aciliyet, "guven": round(guven, 2),
                           "gerekce": f"Kural tabanlı: {en_sayi} anahtar kelime isabeti"},
                          ensure_ascii=False)

    # alan çıkarımı: düzenli ifadeler
    def _analiz(self, metin: str, kullanici: str) -> str:
        alanlar: dict[str, dict] = {}

        def ekle(ad: str, deger: str | None, span: str = "", guven: float = 0.85) -> None:
            if deger and deger.strip():
                alanlar[ad] = {"deger": deger.strip(), "kaynak_span": (span or deger).strip()[:120],
                               "guven": guven}

        def satir(desen: str) -> tuple[str | None, str]:
            m = re.search(desen, metin, flags=re.I | re.M)
            return (m.group(1), m.group(0)) if m else (None, "")

        d, s = satir(r"^\s*Ad[ıi]?[- ]?Soyad[ıi]?\s*:\s*(.+)$"); ekle("gonderen_ad_soyad", d, s)
        d, s = satir(r"^\s*Adres\s*:\s*(.+)$"); ekle("adres", d, s)
        d, s = satir(r"^\s*Konu\s*:\s*(.+)$"); ekle("konu", d, s)
        d, s = satir(r"^\s*Say[ıi]\s*:\s*(.+)$"); ekle("sayi", d, s)
        d, s = satir(r"^\s*Tarih\s*:\s*(.+)$")
        if not d:
            m = re.search(r"\b(\d{1,2}[./]\d{1,2}[./]\d{4})\b", metin)
            d, s = (m.group(1), m.group(0)) if m else (None, "")
        ekle("tarih", d, s)
        d, s = satir(r"^\s*(?:Kurum|Gönderen Kurum)\s*:\s*(.+)$")
        if not d:
            m = re.search(r"^\s*T\.?C\.?\s*\n\s*([A-ZÇĞİÖŞÜ][^\n]{4,60})$", metin, flags=re.M)
            d, s = (m.group(1), m.group(0)) if m else (None, "")
        ekle("gonderen_kurum", d, s)
        if re.search(r"\bimza\b|imzal[ıi]d[ıi]r|\(imza\)", metin, flags=re.I):
            ekle("imza", "mevcut", "imza ibaresi", 0.7)
        m = re.search(r"\*{9}\d{2}", metin)  # security katmanı maskeli bıraktı
        if m:
            ekle("tc_kimlik", m.group(0), m.group(0), 0.9)
        m = re.search(r"([\d.,]+)\s*(?:TL|₺)", metin, flags=re.I)
        if m:
            ekle("tutar", m.group(0), m.group(0))
        m = re.search(r"([^.\n]{15,220}?(?:talep|arz|rica|şikayet|şikâyet|bilgi edinme)[^.\n]{0,160}\.)",
                      metin, flags=re.I)
        if m:
            ekle("talep_ozeti", m.group(1), m.group(1), 0.7)

        ilk = re.sub(r"\s+", " ", metin.strip())[:200]
        ozet = f"Evrak özeti (kural tabanlı): {ilk}..."
        return json.dumps({"alanlar": alanlar, "ozet": ozet}, ensure_ascii=False)

    # yönlendirme: katalog anahtar kelime örtüşmesi
    def _yonlendir(self, metin: str, kullanici: str) -> str:
        # DİKKAT: yalnızca belge içeriğini tara. Tam prompt (kullanici) içinde
        # katalog açıklamaları gömülüdür; taransaydı her birimin anahtar kelimesi
        # kendi katalog satırından "isabet" alır ve puanlama bozulurdu.
        k = tr_kucult(metin)
        puanlar = []
        for b in self.a.birim_katalogu:
            sayi = sum(1 for ak in b.get("anahtar_kelimeler", []) if tr_kucult(ak) in k)
            puanlar.append((sayi, b["kod"]))
        puanlar.sort(reverse=True)
        if puanlar[0][0] == 0:
            return json.dumps({"birim_kodu": "yazi_isleri", "guven": 0.5,
                               "gerekce": "Belirgin eşleşme yok; genel evrak birimi",
                               "alternatif_kodu": ""}, ensure_ascii=False)
        fark = puanlar[0][0] - (puanlar[1][0] if len(puanlar) > 1 else 0)
        guven = min(0.95, 0.65 + 0.1 * fark)
        alt = puanlar[1][1] if len(puanlar) > 1 and puanlar[1][0] > 0 else ""
        return json.dumps({"birim_kodu": puanlar[0][1], "guven": round(guven, 2),
                           "gerekce": f"Kural tabanlı: {puanlar[0][0]} anahtar kelime isabeti",
                           "alternatif_kodu": alt}, ensure_ascii=False)

    # taslak gövdesi: şablon cümleler
    def _govde(self, kullanici: str) -> str:
        def cek(etiket: str) -> str:
            m = re.search(rf"- {etiket}: (.+)", kullanici)
            return m.group(1).strip() if m else ""

        ozet = cek("Özet") or "ilgi konusu husus"
        birim = cek("Hedef birim")
        kapanis = "arz ederim." if "arz ederim" in kullanici else "rica ederim."
        p1 = (f"İlgi konusu evrak kurumumuz kayıtlarına alınmış olup içeriği incelenmiştir. "
              f"{ozet}")
        p2 = (f"Söz konusu hususun değerlendirilmesi amacıyla evrak "
              f"{birim or 'ilgili birim'} tarafından işleme alınmıştır. "
              f"Sürece ilişkin gelişmeler tarafınıza ayrıca bildirilecektir.")
        p3 = f"Bilgilerinizi ve gereğini {kapanis}"
        return "\n\n".join([p1, p2, p3])
