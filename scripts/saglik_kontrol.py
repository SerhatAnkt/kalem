#!/usr/bin/env python3
"""Ayarlı sağlayıcıya tek test isteği gönderir; API anahtarını yazdırmaz."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kalem.config import ayarlari_yukle
from kalem.llm.client import LLMIstemci


def main() -> int:
    ayarlar = ayarlari_yukle()
    if ayarlar.cevrimdisi:
        print("Çevrimdışı demo modu. API isteği gönderilmedi.")
        print("LLM modu için .env içinde KALEM_OFFLINE=0 ve sağlayıcı anahtarını ayarlayın.")
        return 0

    model = ayarlar.modeller["hizli"]
    print(f"Test edilen model: {model}")
    istemci = LLMIstemci(ayarlar)
    try:
        yanit = istemci._tek_cagri.__wrapped__(
            istemci, model, "Kısa yanıt ver.", "Tek kelimeyle: merhaba")
    except Exception as hata:
        # Sağlayıcı hata metinleri istek içeriği taşıyabilir; yalnız hata türünü göster.
        print(f"Bağlantı testi başarısız: {type(hata).__name__}")
        print("SDK kurulumu, anahtar, ağ bağlantısı, model erişimi ve kotayı kontrol edin.")
        return 1
    if not yanit.strip():
        print("Sağlayıcı boş yanıt döndürdü.")
        return 1
    print("Bağlantı testi başarılı. Ayarlı hızlı model yanıt verdi.")
    print("Bu test diğer modellerin veya tüm ajan akışının doğrulaması değildir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
