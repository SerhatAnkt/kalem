# Örnek veriler

Bu depodaki başvurular demo ve test için hazırlanmış sentetik metinlerdir. Gerçek başvuru veya kurum içi evrak arşivi değildir. Kişi adları, adresler ve kurum imzaları senaryo içeriğidir; gerçek kişiler veya işlemlerle ilişkilendirilmemelidir.

| Klasör | İçerik |
|---|---|
| `ornek_evraklar/` | Arayüzde seçilebilen 5 örnek evrak |
| `golden_set/` | 17 sentetik belge ve `labels.jsonl` etiketleri |
| `mevzuat/` | Dört örnek/özet mevzuat dosyası |
| `index/` | Yerelde üretilen indeks; Git'e eklenmez |

`12345678950`, maskeleme kontrolünde kullanılan test değeridir; bir başvurucudan toplanmamıştır. Veri kümesi `python scripts/generate_golden_set.py` ile yeniden üretilebilir. Üretici sabit rastgelelik tohumu kullanır.

Golden set, demo kurallarından bağımsız değildir. Küçük şablon değişiklikleri ve az sayıda belge türü içerir. Bu nedenle yüksek puanlar gerçek kullanım başarısı olarak sunulmamalıdır.

Mevzuat korpusu güncel ve eksiksiz bir hukuki kaynak değildir. Başlık ve madde numaraları arama/atıf akışını göstermek için kullanılır. Gerçek bir kuruma uyarlarken korpusun ve zorunlu alan kurallarının ayrıca doğrulanması gerekir.
