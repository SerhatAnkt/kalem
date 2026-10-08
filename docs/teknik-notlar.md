# Teknik notlar

## Tasarım tercihleri

**Ortak durum ve onay noktaları.** Ajanlar serbest bir sohbet yürütmüyor. Her biri `EvrakState` içindeki belirli alanları okuyup güncelliyor. LangGraph `interrupt` ile tür doğrulama, eksik bilgi ve nihai onayda duruyor. Varsayılan checkpoint bellekte tutuluyor; uygulama kapanınca işlem devamlılığı korunmuyor.

**Kural ve model ayrımı.** Alan çıkarımı modelden veya çevrimdışı regex kurallarından geliyor. Hangi alanın zorunlu olduğu `config/zorunlu_alanlar.yaml` ile belirleniyor. Bu ayrım, eksik alan kontrolünün modelden bağımsız test edilmesini sağlıyor. Alanın dolu olması doğruluğunun kanıtı değil.

**Yerel arama.** Örnek mevzuat maddelere ayrılıp BM25 ile indeksleniyor. Yeterli sözcük eşleşmesi yoksa sonuç dönmüyor. ChromaDB ve sentence-transformers kurulup ayrıca indekslenirse dense sonuçlar RRF ile sıralamaya katılıyor. Mevcut hibrit arama da BM25 alt eşiğine bağlı. Bu özellik çevrimdışı test koşusunun kapsamında değil.

**Şablon ve gövde.** Başlık, sayı, konu ve imza alanları Jinja2 ile oluşturuluyor. Gövde LLM veya çevrimdışı şablondan geliyor. Denetim temel biçim, açık T.C. numarası ve bazı kaynak atfı desenlerini kontrol ediyor. Kaynak numarasının bulunması, o kaynağın taslaktaki ifadeyi hukuken desteklediğini doğrulamaz.

## LLM modu

İlk demo için gerekli değil. Groq kullanmak için:

```bash
python -m pip install groq
```

`.env` dosyanızda `GROQ_API_KEY` değerini doldurup aşağıdaki iki ayarı kullanın:

```dotenv
KALEM_OFFLINE=0
KALEM_STRICT=1
```

`config/settings.yaml` dosyasındaki `hizli`, `ana` ve `yedekler` alanları sağlayıcı/model kimlikleridir. Anahtarlar bu YAML dosyasına yazılmaz. Model erişimi ve kota hesabınıza bağlıdır; güncel seçenekler için [Groq model listesine](https://console.groq.com/docs/models) bakın.

```bash
python scripts/saglik_kontrol.py
python -m streamlit run app.py
```

Sağlık kontrolü yalnızca ayarlı hızlı modele bir istek gönderir. Tüm akışın çalıştığı anlamına gelmez. `KALEM_STRICT=1`, API çağrıları başarısız olduğunda kural tabanlı yedeğe sessiz geçişi engeller. API anahtarı bulunmazsa uygulama çevrimdışı açılır. `KALEM_STRICT=0` durumunda yedek kurallar kullanılabilir; arayüzdeki mod bilgisi tüm adımların gerçekten LLM kullandığını kanıtlamaz.

Gemini veya başka bir LiteLLM sağlayıcısı için `litellm` kurun ve üç model alanını birlikte değiştirin. Sağlayıcının beklediği ortam değişkenini kullanın. [LiteLLM sağlayıcı belgeleri](https://docs.litellm.ai/docs/providers) kimlik biçimlerini açıklar. Bu dağıtımda canlı API çağrısı doğrulanmamıştır.

## OCR ve dense arama

- TXT ve metin katmanlı PDF: temel kurulum.
- PNG/JPG/JPEG/WEBP: yerel OCR için `pytesseract`, sistemde Tesseract ve Türkçe dil paketi gerekir.
- Multimodal okuma: `modeller.ocr` alanı varsayılan olarak boştur. LiteLLM üzerinden görüntü/PDF destekleyen ayrı bir model ile denenebilir. Sağlayıcıların PDF istek biçimleri değişebilir; bu yol deneysel kalır.
- Taranmış PDF için yerel rasterleştirme uygulanmamıştır. Okunamayan belgede manuel metin girişi istenir.
- Dense arama: `chromadb` ve `sentence-transformers` kurulduktan sonra `python scripts/index_corpus.py` çalıştırılır. İlk kullanım BAAI/bge-m3 modelini indirir; ek disk/bellek ve ağ erişimi gerekir. İlk demo için `--bm25` yeterlidir.

## Bilinen sınırlar

- API anahtarı, model erişimi, OCR ve dense arama bu hazırlıkta canlı servislerle sınanmadı.
- Özet ve taslak kalitesi için bağımsız insan değerlendirmesi yok.
- T.C. numarası maskesinde son iki hane kalır; ad, adres ve telefonlar genel olarak maskelenmez. Görüntüler multimodal okumaya metin maskelemesinden önce gönderilebilir.
- Prompt içinde belge etiketleri kullanılması tek başına injection engeli değildir. Tek çevrimdışı kanarya testi güvenlik garantisi vermez.
- Taslak denetimi başarısız olsa bile revizyon sınırından sonra operatör karar verir. Operatörün son ekranda yaptığı metin değişiklikleri yeniden otomatik denetlenmez.
- Yanıt önbelleği ve çıktılar diskte tutulur. Depoya eklenmez; hassas veriyle kullanım için ayrıca saklama ve erişim politikası gerekir.
- Kimlik doğrulama, kurum yetkilendirmesi ve EBYS entegrasyonu yoktur. Streamlit uygulaması yerel demo içindir.
- Kurulum kaynak klasöründen çalışacak şekilde düzenlenmiştir. Bağımsız bir wheel dağıtımı hedeflenmemiştir; `config/` ve `data/` repo kökünde bulunmalıdır.

## Yerel doğrulama

Python 3.12.14 ile 22 test geçti; Ruff kontrolü temiz çıktı. Çevrimdışı CLI akışı ve Streamlit arayüzündeki eksik bilgi → onay → DOCX akışı doğrulandı. Temel paketler: LangGraph 1.2.14, Pydantic 2.13.5, Streamlit 1.65.0, rank-bm25 0.2.2, python-docx 1.2.0, pdfplumber 0.11.8. Kurulum aralıkları `pyproject.toml` içindedir; tam bir bağımlılık kilidi değildir.

GitHub Actions, Python 3.11 ve 3.12 için tanımlıdır. Uzak CI sonucu ancak depo GitHub'a yüklendiğinde oluşur.
