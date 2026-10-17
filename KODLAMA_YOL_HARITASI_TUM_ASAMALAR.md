# 6. Kodlama Yol Haritası

> [!NOTE]
> **Genel Durum:** [x] **TAMAMLANDI (%100)** — Hustler v1.0.0 geliştirme yönergesi ve tüm kodlama aşamaları (M0–M8), 64 ana görev (K-001 – K-807) ve tüm çıkış kriterleri sıfır regresyon ve 5/5 doğrulama kapısı onayıyla başarıyla tamamlanmıştır.

Kilometre taşları ürün fazlarına bağlıdır ve bir kilometre taşı çıkış kriterini karşılamadan kapanmaz. Süreler tahmindir.

## 6.1 Çizelge (14 hafta)

| Kilometre taşı | H1 | H2 | H3 | H4 | H5 | H6 | H7 | H8 | H9 | H10 | H11 | H12 | H13 | H14 | Durum |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| [x] M0 İskelet | [x] | | | | | | | | | | | | | | [x] Tamamlandı |
| [x] M1 Faz 0 Paketi | [x] | | | | | | | | | | | | | | [x] Tamamlandı |
| [x] M2 Veri Motoru | | [x] | [x] | | | | | | | | | | | | [x] Tamamlandı |
| [x] M3 Transkript/Analiz | | | [x] | [x] | | | | | | | | | | | [x] Tamamlandı |
| [x] M4 Senaryo Motoru | | | | | [x] | | | | | | | | | | [x] Tamamlandı |
| [x] M5 Ses ve Altyazı | | | | | | [x] | | | | | | | | | [x] Tamamlandı |
| [x] M6 Şablon/Derleyici/Render | | | | | | | [x] | [x] | [x] | [x] | | | | | [x] Tamamlandı |
| [x] M7 Arayüz | | | | | | | | | | | [x] | [x] | | | [x] Tamamlandı |
| [x] M8 Sertleştirme | | | | | | | | | | | | | [x] | [x] | [x] Tamamlandı |

Toplam süre ürün dokümanındaki 12 haftadan 2 hafta uzundur. Fark bilinçli bir yatırımdır: iskelet, CI ve sertleştirme. M6 en belirsiz kilometre taşıdır (3-4 hafta); toplam tahmin için yaklaşık ±%30 belirsizlik varsayılmalıdır.

---

### [x] M0: Yürüyen İskelet (TAMAMLANDI)
**Süre:** 4-5 gün | **Ürün fazı:** F0 | **Durum:** [x] Tamamlandı

| ID | Görev | Kabul ölçütü |
|---|---|---|
| [x] K-001 | Monorepo, kilit dosyaları, just görevleri (dev, check, test, gen) | just check tek komutla lint + tip + test çalıştırır |
| [x] K-002 | ruff, mypy strict, ESLint/Prettier, rustfmt/clippy, pre-commit, gitleaks | Hatalı commit engellenir |
| [x] K-003 | CI hattı (Windows): lint → tip → birim; sözleşme denetimi K-004 ile eklenir | Boş projede yeşil |
| [x] K-004 | hustler.contracts, JSON Schema ve TypeScript tipi üretimi | Şema değişince üretilen dosya farkı CI'ı kırar |
| [x] K-005 | FastAPI iskeleti: /health, oturum belirteci, Problem Details, SSE | Entegrasyon testi geçer |
| [x] K-006 | Tauri 2 kabuğu: sidecar başlatma (dinamik port keşfi için stdout'tan BIND_PORT=xxxxx okunması), sağlık yoklaması, Job Object ile kapanış; servis adresi ve belirteci yalnızca Rust'ta tutulur | Zorla kapatmada yetim süreç yok; arayüz belleğinde port veya belirteç yok |
| [x] K-007 | structlog, run_id, Timer ve RunEvent modeli | Adım süresi veritabanına yazılır |
| [x] K-008 | SQLite katmanı: WAL PRAGMA'ları, auto_vacuum=INCREMENTAL (veritabanı oluşturulurken ve freelist sayfalarını OS'e geri vermek için WriterQueue içinde PRAGMA incremental_vacuum; tetikleyicisi), WriterQueue (bakım işi türüyle), ReaderPool, göç çalıştırıcı | 1 yazıcı + 5 okuyucu stres testinde 0 kilit hatası |
| [x] K-009 | hustler doctor: ffmpeg, WebView2, GPU/CUDA, disk, veritabanı ve runs/ boyutu, API anahtarları | Eksikleri ve büyüme uyarılarını tek raporda listeler |
| [x] K-010 | Tauri IPC köprüsü (önkoşul: K-005, K-006): genel proxy komutu, OpenAPI'den üretilen rota izin listesi, SSE → Tauri Channel akışı, istek boyutu ve süre sınırı; üretilmiş TypeScript istemcisinin taşıması invoke olur | Köprü sözleşme testi geçer; izin listesi dışı rota reddedilir; arayüzde doğrudan ağ çağrısı lint ile engellenir |

[x] **Çıkış kriteri:** Arayüzdeki bir düğme Tauri invoke ile sidecar'ı çağırır (arayüz doğrudan ağ çağrısı yapmaz), sonuç veritabanına yazılır ve olay Tauri Channel ile arayüze döner; CI yeşildir. — **[TAMAMLANDI / ONAYLANDI]**

---

### [x] M1: Faz 0 Doğrulama Paketi (TAMAMLANDI)
**Süre:** 4-5 gün | **Ürün fazı:** F0 | **Konum:** tools/ | **Durum:** [x] Tamamlandı

| ID | Görev | Kabul ölçütü |
|---|---|---|
| [x] K-101 | T0-1 ve T0-2: 5 konu x 20 video, kota ve hata günlüğü, Shorts sınıflandırma doğrulaması | 100 video eksiksiz; yanlış sınıflandırma < %10 |
| [x] K-102 | T0-3: transkript kapsama ölçümü (altyazı / Whisper) | Kapsama ≥ %90 |
| [x] K-103 | T0-4 ve T0-5: şema uyumu koşucusu (30 üretim) ve map-reduce A/B kıyas aracı | İlk denemede ≥ %95; 2 denemede %100; maliyet baz çizgisi |
| [x] K-104 | T0-6 ve T0-7: eşzamanlılık stres testi ve yavaş-kopyalama simülatörü | Kilit hatası 0; çökme 0 |
| [x] K-105 | T0-8: FFmpeg prototipi (8 görsel + ses + ASS), snapshot ve kuru çalıştırma | Nihai < 2 dk; taslak < 10 sn |
| [x] K-106 | T0-10, T0-11, T0-12: Whisper CPU ve devre kesici, asenkron Map (yerel model adayıyla event loop gecikme ölçümü dahil), sidecar paketleme ve taşıma alternatifleri (loopback + belirteç, stdio, named pipe) karşılaştırması | Bütçe içinde; yetim süreç 0; taşıma kararı ADR-010'a işlenir |
| [x] K-107 | Sonuç raporu: her test için ölçüm ve geç/revize kararı; eşiklerin kalibrasyonu | ADR'ler ölçülen değerlerle güncellenir |

[x] **Çıkış kriteri:** Tüm T0 testleri geçmiş veya ilgili mimari karar revize edilmiştir; varsayılan eşikler (5 video, 90 sn, %80 kart) ölçülmüş değerlerle değişmiştir. — **[TAMAMLANDI / ONAYLANDI]**

---

### [x] M2: Veri Motoru (TAMAMLANDI)
**Süre:** 1,5-2 hafta | **Ürün fazı:** F1 | **Durum:** [x] Tamamlandı

| ID | Görev | Kabul ölçütü |
|---|---|---|
| [x] K-201 | YouTubeClient (httpx async): arama, videolar, kanallar, sayfalama, zaman aşımı | Cassette testleri geçer |
| [x] K-202 | Kota izleyici ve SQLite önbellek: TTL ve tablo başına saklama politikası (öneri: video önbelleği kısa, transkript ve özet kartı uzun ömürlü), boyut üst sınırı; aynı sorgu tekrar çekilmez | Kota göstergesi olayı; ikinci çağrı önbellekten; saklama süreleri ayardan |
| [x] K-203 | Shorts sınıflandırıcı: süre eşiği ayardan gelir | Güncel eşik doğrulama testi |
| [x] K-204 | Skorlama (saf fonksiyonlar): log-ölçekli izlenme/abone, saatlik hız, minimum abone eşiği, gizli abone işareti | hypothesis: sınırlı, monoton, NaN yok |
| [x] K-205 | Discovery servisi, hustler discover CLI, Top 20 sıralaması | Top 20 < 30 sn |
| [x] K-206 | Arka plan zamanlayıcısı: kayıtlı konuların yenilenmesi; yenileme ve bakım işleri tek zamanlayıcıda, aktif üretim sürerken ertelenir | Yenileme sırasında arayüz okuması kilitlenmez |
| [x] K-207 | Önbellek bakımı (önkoşul: K-008, K-202): süresi dolan kayıtlar toplu (batch) silinir; wal_checkpoint(TRUNCATE); serbest sayfa oranı eşiği aşılınca PRAGMA incremental_vacuum; komutu ile alan işletim sistemine geri verilir (yazıcı kuyruğunda, boşta); runs/ klasörü için yaş ve toplam boyut kotası | 30 günlük büyüme simülasyonunda veritabanı boyutu platoya oturur; bakım sırasında okuma kilitlenmez; aktif üretimde bakım ertelenir |

[x] **Çıkış kriteri:** Bir konu için sıralı Top 20 listesi < 30 sn; eşzamanlılık stres testinde 0 kilit hatası; 30 günlük büyüme simülasyonunda veritabanı boyutu sınırlı kalır. — **[TAMAMLANDI / ONAYLANDI]**

---

### [x] M3: Transkript ve Analiz (TAMAMLANDI)
**Süre:** 1,5 hafta | **Ürün fazı:** F2 | **Durum:** [x] Tamamlandı

| ID | Görev | Kabul ölçütü |
|---|---|---|
| [x] K-301 | HardwareProfile: GPU/CUDA tespiti, RTF benchmark, kalıcı profil | Profil veritabanında; CUDA yokken doğru işaretlenir |
| [x] K-302 | TranscriptProvider: yerleşik altyazı önceliği, Whisper yedeği, dil algılama | Kapsama ≥ %90 |
| [x] K-303 | CircuitBreaker: kapalı/açık/yarı açık durum makinesi; video sayısı, süre ve video uzunluğu bütçesi | Durum makinesi birim ve özellik testleri |
| [x] K-304 | Map A: kanca adayı, kelime sayısı, dakikadaki kelime, CTA kuralları | Deterministik; LLM maliyeti sıfır |
| [x] K-305 | LLMPort + adapter, LlmCall maliyet defteri, token tavanı | Aşımda uyarı olayı |
| [x] K-306 | CpuBudget ve yerel çıkarım altyapısı (önkoşul: K-301): Whisper ve yerel Map modeli için paylaşılan CPU semaforu ve çekirdek bütçesi; InferencePort (API ve yerel uygulama); yerel çıkarım event loop dışında (asyncio.to_thread yalnızca GIL'i bırakan native kütüphanelerde, aksi halde ProcessPoolExecutor); model süreç başına bir kez yüklenir | Çıkarım sırasında event loop gecikmesi eşik altında (öneri: < 100 ms); iptalde çıkarım süreci sonlanır |
| [x] K-307 | Map B çalıştırıcı (önkoşul: K-305, K-306): API modunda asyncio eşzamanlılığı (Semaphore 5-8, zaman aşımı, 429 için geri çekilme + jitter, kısmi başarısızlık); yerel modda eşzamanlılık CpuBudget'a bağlı (varsayılan 1) | API modunda 20 kart < 60 sn; 429 simülasyonu geçer; yerel modda süre ölçülür (bütçeyi aşarsa API modu seçilir) |
| [x] K-308 | Reduce, AnalysisResult; önbellek anahtarı (transkript_hash + prompt_sürümü) | İkinci çalıştırmada LLM çağrısı yok |
| [x] K-309 | Prompt eval harness: sabit veri seti, otomatik puan raporu | Prompt değişikliği raporla kıyaslanır |

[x] **Çıkış kriteri:** 20 video için transkript + analiz < 3 dk; üretim başına maliyet tavanın altında; CUDA kapalıyken devre kesici doğru tetiklenir; CPU bağlı çıkarım sırasında event loop yanıt verir. — **[TAMAMLANDI / ONAYLANDI]**

---

### [x] M4: Senaryo Motoru (TAMAMLANDI)
**Süre:** 1 hafta | **Ürün fazı:** F3 | **Durum:** [x] Tamamlandı

| ID | Görev | Kabul ölçütü |
|---|---|---|
| [x] K-401 | ScriptDoc modelleri ve JSON Schema | Sözleşme üretimi CI'da güncel |
| [x] K-402 | TemplateSpec sözleşmesinin yapısal çekirdeği (sahne sayısı, süre aralığı, kelime sınırı) ve 1-2 örnek şablon; render alanları M6'da eklenir | Senaryo üretici örnek şablonla çalışır |
| [x] K-403 | Senaryo üretici (önkoşul: K-402): şablon yapısı prompt'a girdi, şema zorunlu çıktı, doğrulama, ≤ 2 yeniden deneme | Sığmayan senaryo < %10 |
| [x] K-404 | Anlamsal doğrulayıcı: sahne sayısı, kelime sınırı, süre toplamı, n-gram kopya taraması | Kopya eşiği aşılınca yeniden üretim |
| [x] K-405 | İddia işaretleyici ve onay durumu; onaysız render engeli domain kuralı olarak uygulanır | Onaysız senaryo render'a giremez (test) |
| [x] K-406 | Görsel prompt derleyici: stil öneki, sahne no, 9:16, toplu kopya çıktısı | Snapshot testi |
| [x] K-407 | Senaryo eval seti: 3 konu x şablon; şema geçerlilik raporu | ≥ %95 ilk denemede; %100 yeniden denemeyle |

[x] **Çıkış kriteri:** Şablona sığan, doğrulanmış, iddiaları işaretlenmiş senaryo; eval raporu eşikleri geçiyor. — **[TAMAMLANDI / ONAYLANDI]**

---

### [x] M5: Ses ve Altyazı (TAMAMLANDI)
**Süre:** 1 hafta | **Ürün fazı:** F4 | **Durum:** [x] Tamamlandı

| ID | Görev | Kabul ölçütü |
|---|---|---|
| [x] K-501 | TTSPort + ElevenLabs adapter: zaman aşımı, yeniden deneme, kota | Cassette testleri |
| [x] K-502 | Zaman damgası normalleştirici: kelime zamanları tam sayı ms/kare | Property testi: sıralı, çakışmasız |
| [x] K-503 | AssDocument + SubtitleStyle (kelime vurgusu), font paketleme | ASS snapshot testi |
| [x] K-504 | Ses profili yönetimi ve önbellek (aynı metin, aynı dosya) | İkinci istekte API çağrısı yok |
| [x] K-505 | Timeline / TimeCode çekirdeği (tam sayı kare), ses süresi girişi ve sahne süresi uyarlaması | Property testleri: toplam süre = ses süresi ± 1 kare, kayma yok |

[x] **Çıkış kriteri:** Onaydan sese ≤ 2 dk; altyazı senkronu hatasız. — **[TAMAMLANDI / ONAYLANDI]**

---

### [x] M6: Şablon, Derleyici, Render ve Assets (TAMAMLANDI)
**Süre:** 3-4 hafta (en belirsiz kilometre taşı) | **Ürün fazı:** F5 | **Durum:** [x] Tamamlandı

| ID | Görev | Kabul ölçütü |
|---|---|---|
| [x] K-601 | TemplateSpec'i render alanlarıyla genişlet (RenderConfig, SafeZone, Pydantic field_validator ile katı kısıtlamalar) | Şema doğrulaması geçer |
| [x] K-602 | AssetManager İnşası (Asenkron medya motoru, Semaphore, iter_bytes chunk streaming, Tenacity retry, akıllı Cache) | Eşzamanlılık ve Cache Hit testleri geçer |
| [x] K-603 | FFmpeg Derleyici (Compiler), AST Sınıfları (Filter, FilterChain) ve kuru çalıştırma yardımcısı assert_compiles | Null muxer ile I/O olmadan (ms seviyesinde) çalışır |
| [x] K-604 | SceneClipBuilder (scale/crop/zoompan/fps) ve hareket kayıt defteri (Motion Registry) | Kuru çalıştırmadan (Dry Run) ve MyPy'dan geçer |
| [x] K-605 | TransitionPlanner (xfade ofset) ve AudioMixer | Ofset hesabı birim testli |
| [x] K-606 | GraphValidator, Profile (Draft/Final), derleyici-şema sürüm eşleşmesi; tüm şablon x profil matrisi kuru çalıştırılır | Kopuk etiket ve süre tutarsızlığı yakalanır; matrisin tamamı kuru çalıştırmadan geçer (CI kapısı K4) |
| [x] K-607 | FFmpegRunner: progress ayrıştırma, zaman aşımı, iptal, hata ayrıştırma | İptalde alt süreç ölür |
| [x] K-608 | Altın dosya ve snapshot altyapısı; her şablon için referans render | Kare farkı eşiği CI'da |
| [x] K-609 | Assets: izleme durum makinesi (aday → kararlılık → doğrulama → kopya) | Yavaş-kopyalama testinde çökme 0 |
| [x] K-610 | Slot eşleme, oran ve eksik dosya uyarıları | Yanlış oranda net uyarı |
| [x] K-611 | Taslak önizleme akışı | Taslak < 10 sn; nihai < 2 dk |

[x] **Çıkış kriteri:** Bir senaryo, ses ve görsel seti klasöre bırakıldığında otomatik yerleşir; taslak < 10 sn, nihai render < 2 dk; kuru çalıştırma, altın dosya ve kararlılık testleri geçer. — **[TAMAMLANDI / ONAYLANDI]**

---

### [x] M7: Arayüz ve Süreç Yönetimi (TAMAMLANDI)
**Süre:** 2 hafta | **Ürün fazı:** F6 | **Durum:** [x] Tamamlandı

| ID | Görev | Kabul ölçütü |
|---|---|---|
| [x] K-701 | Tasarım sistemi (renk/aralık tokenları, bileşenler), koyu tema | Bileşen testleri |
| [x] K-702 | Akış ekranları: Konu → Top 20 → Senaryo → Ses → Görseller → Önizleme → Render | Ana akış e2e testi; arayüz kodunda doğrudan ağ çağrısı yok |
| [x] K-703 | Olay istemcisi (Tauri Channel üzerinden), ilerleme çubuğu, iptal, Problem Details hata gösterimi | Hata türleri arayüzde eşlenir; bağlantı kopmasında yeniden abone olur |
| [x] K-704 | Senaryo editörü ve iddia onay paneli | Onaysız render düğmesi kapalı |
| [x] K-705 | Tek tık toplu prompt kopyalama ekranı | Kopya içeriği snapshot testli |
| [x] K-706 | Şablon yöneticisi: kategori, klonla, içe/dışa aktar | Şema doğrulamalı |
| [x] K-707 | Süre paneli: 15 dk hedefine göre durum | Timer olaylarından beslenir |
| [x] K-708 | Supervisor tamamlama: yeniden başlatma politikası, kapanış, yetim temizliği | Zorla kapatma senaryoları |
| [x] K-709 | Arayüz güvenlik e2e testi: doğrudan ağ çağrısı CSP ile engellenir, izin listesi dışı komut reddedilir | Test yeşil; ihlal denemesi günlüğe düşer |

[x] **Çıkış kriteri:** Yeni konu akışı yönergesiz tamamlanır; render sırasında arayüz donmaz; yetim süreç 0; arayüz hiçbir ağ çağrısı yapmaz. — **[TAMAMLANDI / ONAYLANDI]**

---

### [x] M8: Sertleştirme ve Yayın (TAMAMLANDI)
**Süre:** 1,5-2 hafta | **Ürün fazı:** F7 | **Durum:** [x] Tamamlandı

| ID | Görev | Kabul ölçütü |
|---|---|---|
| [x] K-801 | Kurulum paketi (Tauri bundler), WebView2 bootstrapper, temiz makine testi | Temiz VM'de kurulum ve çalıştırma |
| [x] K-802 | Yedekleme/geri yükleme (SQLite backup API; önbellek tabloları hariç), proje kurtarma | Çökme sonrası devam testi |
| [x] K-803 | Tanılama paketi: günlükler, doctor raporu, sürümler (zip) | Tek komutla üretilir |
| [x] K-804 | Performans bütçesi CI kapısı (tools/bench) | Regresyon derlemeyi kırar |
| [x] K-805 | Güvenlik gözden geçirme: Tauri izinleri, CSP, IPC izin listesi, bağımlılık ve lisans taraması | Rapor ve açık madde 0 |
| [x] K-806 | yt-dlp güncelleme politikası ve bozulma tespiti (kanarya testi) | Bozulmada net uyarı, hat durmaz |
| [x] K-807 | 5 kronometreli üretim, CHANGELOG, v1.0 etiketi | Medyan ≤ 15 dk |

[x] **Çıkış kriteri:** Temiz makinede kurulup uçtan uca 15 dk içinde Shorts üretilir; tüm kalite kapıları yeşildir. — **[TAMAMLANDI / ONAYLANDI - K-807 YAYIN KAPISI 5/5 GEÇTİ]**

---

## 6.2 Kilometre Taşı Sıralaması ve Bağımlılıklar

Kural: Bir kilometre taşı, önkoşulu olan kilometre taşlarının çıkış kriteri geçilmeden başlamaz. Tek planlı çakışma M2 ile M3 arasındadır: M3, M2'nin K-205'i bitince başlayabilir; K-206 ve K-207 M3 ile paralel yürür ve M3 kapanmadan doğrulanır.

| Kilometre taşı | Önkoşul | Devrettiği çıktı | Kapı | Durum |
|---|---|---|---|---|
| [x] M0 | - | İskelet, CI, IPC köprüsü, veritabanı katmanı | K1-K3 yeşil | [x] Tamamlandı |
| [x] M1 | M0 | Ölçülmüş eşikler, mimari kararların doğrulanması | T0 raporu | [x] Tamamlandı |
| [x] M2 | M0 (K-008, K-010), M1 (T0-1, T0-2, T0-6) | Top 20 servisi, önbellek ve bakım | Top 20 < 30 sn; büyüme simülasyonu | [x] Tamamlandı |
| [x] M3 | M2 (K-205), M1 (T0-3, T0-10, T0-11) | Analiz sonucu, CpuBudget, maliyet defteri | 20 video < 3 dk | [x] Tamamlandı |
| [x] M4 | M3 | Doğrulanmış senaryo, TemplateSpec çekirdeği | Eval eşikleri | [x] Tamamlandı |
| [x] M5 | M4 | Ses, altyazı, Timeline çekirdeği | ≤ 2 dk; senkron | [x] Tamamlandı |
| [x] M6 | M5, M1 (T0-8) | Derleyici, render, assets | Render bütçesi; kuru çalıştırma (K4) | [x] Tamamlandı |
| [x] M7 | M6, M0 (K-010) | Tam arayüz | Yönergesiz akış; güvenlik e2e | [x] Tamamlandı |
| [x] M8 | M7 | Kurulum paketi ve v1.0 | Yayın kapısı (K-807) | [x] Tamamlandı |
