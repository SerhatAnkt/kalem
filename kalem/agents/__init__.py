"""Uzman ajanlar. Her ajan saf bir fonksiyondur: (state, ctx) → kısmi state.

ctx (AjanBaglami): ayarlar + LLM istemcisi + mevzuat getirici. Ajanların yan
etkisi yoktur; tüm iletişim blackboard (EvrakState) üzerinden yürür.
"""
from dataclasses import dataclass

from kalem.config import Ayarlar
from kalem.llm.client import LLMIstemci
from kalem.rag.retriever import MevzuatGetirici


@dataclass
class AjanBaglami:
    ayarlar: Ayarlar
    istemci: LLMIstemci
    getirici: MevzuatGetirici
