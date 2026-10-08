"""Arayüzden eksik bilgi tamamlama, onay ve çıktı akışı."""
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_eksik_adres_ekrani_ve_docx():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=20).run()
    assert not app.exception
    app.selectbox[0].select("dilekce_eksik_adres.txt").run()
    next(b for b in app.button if b.label == "İşle").click().run()
    assert app.session_state["kesme"]["tip"] == "eksik_bilgi"

    next(b for b in app.button if b.label == "Tamamla ve devam").click().run()
    assert app.error
    assert app.session_state["kesme"]["tip"] == "eksik_bilgi"

    app.text_input(key="eks_adres").set_value("Örnek Mahallesi No: 1, Merkez").run()
    next(b for b in app.button if b.label == "Tamamla ve devam").click().run()
    assert app.session_state["kesme"]["tip"] == "nihai_onay"
    next(b for b in app.button if b.label == "Onayla").click().run()

    assert not app.exception
    assert app.session_state["bitti"]
    assert len(app.get("download_button")) == 1
    output = Path(app.session_state["son_state"]["cikti_yollari"]["docx"])
    assert output.exists()
    assert output.read_bytes().startswith(b"PK")
