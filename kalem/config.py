"""YAML ayarları ve ortam değişkenlerinden çalışma modunu yükler."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

KOK = Path(__file__).resolve().parent.parent  # repo kökü
CONFIG_DIZIN = KOK / "config"

# Repo kökündeki .env dosyasını (varsa) ortama yükle. python-dotenv kuruluysa
# kullanılır; değilse basit bir ayrıştırıcıya düşülür (ek bağımlılık zorunlu değil).
# Böylece anahtarları .env'e yazmak yeterli olur; export şart değildir.
def _env_yukle() -> None:
    env_yolu = KOK / ".env"
    if not env_yolu.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_yolu, override=False)
        return
    except ImportError:
        pass
    for satir in env_yolu.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        anahtar, _, deger = satir.partition("=")
        os.environ.setdefault(anahtar.strip(), deger.strip().strip('"').strip("'"))


_env_yukle()


def _yaml_oku(ad: str) -> dict:
    with open(CONFIG_DIZIN / ad, encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class Ayarlar:
    kurum: dict[str, Any]
    modeller: dict[str, Any]
    esikler: dict[str, Any]
    llm: dict[str, Any]
    yollar: dict[str, Any]
    taksonomi: dict[str, Any] = field(default_factory=dict)
    birim_katalogu: list[dict] = field(default_factory=list)
    zorunlu_alanlar: dict[str, list[dict]] = field(default_factory=dict)

    @property
    def gemini_anahtar(self) -> str:
        return os.environ.get("GEMINI_API_KEY", "").strip()

    @property
    def groq_anahtar(self) -> str:
        return os.environ.get("GROQ_API_KEY", "").strip()

    @property
    def cevrimdisi(self) -> bool:
        if os.environ.get("KALEM_OFFLINE", "0") == "1":
            return True
        return not (self.gemini_anahtar or self.groq_anahtar)

    @property
    def kati(self) -> bool:
        """KALEM_STRICT=1: LLM çağrısı başarısız olursa mock'a düşme, hatayı fırlat.
        Teşhis/geliştirme için; çevrimiçi modun gerçekten çalışıp çalışmadığını görmeyi sağlar."""
        return os.environ.get("KALEM_STRICT", "0") == "1"

    def yol(self, anahtar: str) -> Path:
        return KOK / self.yollar[anahtar]


_onbellek: Ayarlar | None = None


def ayarlari_yukle(yeniden: bool = False) -> Ayarlar:
    global _onbellek
    if _onbellek is not None and not yeniden:
        return _onbellek
    s = _yaml_oku("settings.yaml")
    _onbellek = Ayarlar(
        kurum=s["kurum"],
        modeller=s["modeller"],
        esikler=s["esikler"],
        llm=s["llm"],
        yollar=s["yollar"],
        taksonomi=_yaml_oku("evrak_taksonomisi.yaml")["turler"],
        birim_katalogu=_yaml_oku("birim_katalogu.yaml")["birimler"],
        zorunlu_alanlar=_yaml_oku("zorunlu_alanlar.yaml")["kurallar"],
    )
    return _onbellek
