# KALEM — Değerlendirme Raporu

**Mod:** ÇEVRİMDIŞI (kural tabanlı)
**Örnek sayısı:** 17

> Bu küçük sentetik küme, kural tabanlı demo ile aynı şablon ve anahtar kelime varsayımlarını paylaşır. Sonuçlar bağımsız bir benchmark veya gerçek kurum belgelerinde başarı göstergesi değildir.
> LLM kalitesi, OCR doğruluğu ve hukuki uygunluk bu çalıştırmada ölçülmemiştir.


## Özet Metrikler

| Metrik | Değer |
|---|---|
| Sınıflandırma doğruluğu (accuracy) | **100.0%** |
| Sınıflandırma makro-F1 | **1.000** |
| Yönlendirme isabeti (14 etiketli) | **100.0%** |
| Eksik tespiti precision | 100.0% |
| Eksik tespiti recall | 100.0% |
| Eksik tespiti F1 | **1.000** |
| Kanarya metninin çıktıda bulunmaması (1 örnek) | **100%** |

Sınıflandırma için insan müdahalesinden önceki ilk tahmin kullanılır. Eksik alanlar
onay kapısında ölçülür; akışın devamında demo değerleriyle doldurulur. Tek kanarya
örneği, genel bir prompt-injection dayanıklılığı sonucu olarak yorumlanmamalıdır.

## Belge Bazında

| Dosya | Sınıflandırma | Yönlendirme | Not |
|---|---|---|---|
| dilekce_park_0.txt         | ✓ dilekce            | ✓              | |
| dilekce_park_1.txt         | ✓ dilekce            | ✓              | |
| dilekce_park_2.txt         | ✓ dilekce            | ✓              | |
| dilekce_eksik_adres.txt    | ✓ dilekce            | ✓              | |
| dilekce_bakim.txt          | ✓ dilekce            | ✓              | |
| bilgi_edinme_0.txt         | ✓ bilgi_edinme       | ✓              | |
| bilgi_edinme_1.txt         | ✓ bilgi_edinme       | ✓              | |
| bilgi_edinme_eksik.txt     | ✓ bilgi_edinme       | ✓              | |
| resmi_ebys.txt             | ✓ resmi_yazi_gelen   | ✓              | |
| resmi_odeme.txt            | ✓ resmi_yazi_gelen   | ✓              | |
| resmi_konusuz.txt          | ✓ resmi_yazi_gelen   | —              | |
| sikayet_park.txt           | ✓ dilekce            | ✓              | |
| gorus_oneri.txt            | ✓ gorus_oneri        | —              | |
| izin_onay.txt              | ✓ izin_onay_talebi   | ✓              | |
| mali_fatura.txt            | ✓ mali_evrak         | ✓              | |
| diger_belirsiz.txt         | ✓ diger_belirsiz     | —              | |
| injection_dilekce.txt      | ✓ dilekce            | ✓              | [canary ENGELLENDİ ✓] |
