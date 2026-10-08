"""LLM çağrıları, model yedekleri, SQLite yanıt önbelleği ve JSON doğrulama."""
from __future__ import annotations

import hashlib
import logging
import sqlite3
from pathlib import Path
from typing import Type

from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from kalem.config import Ayarlar
from kalem.llm.mock import SahteLLM
from kalem.utils import json_ayikla

log = logging.getLogger("kalem.llm")

# Bu hata türleri anında tekrar denemede düzelmez (kota dolu, anahtar yanlış,
# model yok...). Yeniden deneme yalnızca kotayı/vakti boşa harcar → tek denemede
# geç, fallback devreye girsin. Geçici hatalarda (timeout, bağlantı, 500) tekrar dene.
_TEKRAR_YOK = {"RateLimitError", "AuthenticationError", "NotFoundError",
               "PermissionDeniedError", "BadRequestError",
               "ImportError", "ModuleNotFoundError"}


def _yeniden_denenebilir(e: BaseException) -> bool:
    return type(e).__name__ not in _TEKRAR_YOK


class LLMIstemci:
    def __init__(self, ayarlar: Ayarlar):
        self.ayarlar = ayarlar
        self.mock = SahteLLM(ayarlar)
        self._db: sqlite3.Connection | None = None
        self.son_hata: str | None = None  # en son LLM çağrı hatası (teşhis için)

    # önbellek
    def _onbellek(self) -> sqlite3.Connection:
        if self._db is None:
            yol = Path(self.ayarlar.llm["onbellek_db"])
            if not yol.is_absolute():
                from kalem.config import KOK
                yol = KOK / yol
            yol.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(yol, check_same_thread=False)
            self._db.execute("CREATE TABLE IF NOT EXISTS onbellek (h TEXT PRIMARY KEY, yanit TEXT)")
        return self._db

    def _anahtar(self, model: str, sistem: str, kullanici: str) -> str:
        return hashlib.sha256(f"{model}||{sistem}||{kullanici}".encode()).hexdigest()

    def _onbellekten(self, h: str) -> str | None:
        satir = self._onbellek().execute("SELECT yanit FROM onbellek WHERE h=?", (h,)).fetchone()
        return satir[0] if satir else None

    def _onbellege(self, h: str, yanit: str) -> None:
        db = self._onbellek()
        db.execute("INSERT OR REPLACE INTO onbellek VALUES (?,?)", (h, yanit))
        db.commit()

    # ham üretim
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=8),
           retry=retry_if_exception(_yeniden_denenebilir), reraise=True)
    def _tek_cagri(self, model: str, sistem: str, kullanici: str) -> str:
        # groq/ modelleri: önce Groq'un kendi SDK'sıyla dene (litellm gerektirmez). Yoksa litellm'e düş.
        if model.startswith("groq/"):
            try:
                return self._groq_native(model, sistem, kullanici)
            except ImportError:
                pass  # groq SDK yok → litellm üzerinden dene
        return self._litellm_cagri(model, sistem, kullanici)

    def _groq_native(self, model: str, sistem: str, kullanici: str) -> str:
        """Groq resmî SDK'sı ile doğrudan çağrı (OpenAI-uyumlu, hafif bağımlılık)."""
        import os

        from groq import Groq  # pip install groq — Rust/derleme gerektirmez

        istemci = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
        yanit = istemci.chat.completions.create(
            model=model.split("/", 1)[1],  # "groq/openai/gpt-oss-120b" → "openai/gpt-oss-120b"
            messages=[{"role": "system", "content": sistem},
                      {"role": "user", "content": kullanici}],
            temperature=self.ayarlar.llm["sicaklik"],
            max_tokens=self.ayarlar.llm["max_cikti_token"],
        )
        return yanit.choices[0].message.content or ""

    def _litellm_cagri(self, model: str, sistem: str, kullanici: str) -> str:
        import litellm  # tembel import: çevrimdışı kurulumda zorunlu değil

        yanit = litellm.completion(
            model=model,
            messages=[{"role": "system", "content": sistem},
                      {"role": "user", "content": kullanici}],
            temperature=self.ayarlar.llm["sicaklik"],
            max_tokens=self.ayarlar.llm["max_cikti_token"],
        )
        return yanit.choices[0].message.content or ""

    def uret(self, gorev: str, sistem: str, kullanici: str, katman: str = "hizli") -> str:
        """Metin üretimi. gorev: mock yönlendirme + izleme etiketi."""
        if self.ayarlar.cevrimdisi:
            return self.mock.uret(gorev, sistem, kullanici)

        modeller = [self.ayarlar.modeller[katman], *self.ayarlar.modeller.get("yedekler", [])]
        h = self._anahtar(modeller[0], sistem, kullanici)
        if (onb := self._onbellekten(h)) is not None:
            return onb

        for model in modeller:
            try:
                yanit = self._tek_cagri(model, sistem, kullanici)
                self._onbellege(h, yanit)
                self.son_hata = None
                return yanit
            except Exception as e:  # noqa: BLE001 — fallback zinciri bilinçli geniş
                # Kısa ama tanımlayıcı hata özeti (401, 404, rate limit vb. görünsün)
                ozet = str(e).replace("\n", " ")[:300]
                self.son_hata = f"{type(e).__name__}: {ozet}"
                log.warning("LLM çağrısı başarısız (%s): %s", model, self.son_hata)
                continue

        # Tüm sağlayıcılar düştü.
        if self.ayarlar.kati:
            # Teşhis modu: gerçek hatayı gizleme, fırlat.
            raise RuntimeError(
                f"KATI MOD: LLM çağrısı başarısız oldu, mock'a düşülmedi. Son hata → {self.son_hata}")
        # Normal mod: kural tabanlı düşük moda in. Ama artık SESSİZ DEĞİL:
        log.warning("Tüm LLM sağlayıcıları başarısız → kural tabanlı mock'a düşülüyor. "
                    "Son hata: %s", self.son_hata)
        return self.mock.uret(gorev, sistem, kullanici)

    def uret_json(self, gorev: str, sistem: str, kullanici: str,
                  sema: Type[BaseModel], katman: str = "hizli") -> BaseModel:
        """JSON üret + Pydantic doğrula + tek onarım denemesi."""
        ham = self.uret(gorev, sistem, kullanici, katman)
        try:
            return sema.model_validate(json_ayikla(ham))
        except Exception as ilk_hata:
            if self.ayarlar.cevrimdisi:
                raise ValueError(f"Mock JSON doğrulanamadı: {ilk_hata}") from ilk_hata
            onarim = (f"{kullanici}\n\nÖnceki yanıtın şu doğrulama hatasını verdi: {ilk_hata}\n"
                      f"Yalnızca geçerli JSON döndür.")
            ham2 = self.uret(gorev, sistem, onarim, katman)
            try:
                return sema.model_validate(json_ayikla(ham2))
            except Exception as e:
                raise ValueError(f"JSON onarımı başarısız: {e}") from e
