"""Pytest kök konfigürasyonu: repo kökünü path'e ekler ve çevrimdışı modu
zorlar. Böylece testler API anahtarı olmadan, deterministik ve ücretsiz koşar.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["KALEM_OFFLINE"] = "1"
