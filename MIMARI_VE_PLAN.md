# HUSTLER PROTOKOLLERİ, MİMARİ VE ÜRÜN GEREKSİNİMLERİ (EKSİKSİZ AKTARIM)

---
# BÖLÜM 1: ÜRÜN YOL HARİTASI VE GEREKSİNİMLER (v1.2)
---

, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
HUSTLER
Ürün Yol Haritası ve Geliştirme Yönergesi
Trend analizi, senaryo, ses ve şablon tabanlı Shorts üretimini tek istasyonda birleştiren Windows masaüstü uygulaması.
Doküman kontrolü
Sürüm
1.2 (Nihai taslak - Onay Bekliyor)
Tarih
30 Eylül 2026
Ürün sahibi
Hustler proje sahibi
Kullanım
Yerel, kişisel, ticari olmayan
Sınıflandırma
Gizli - Dahili
Sonraki gözden geçirme
Faz 0 çıkışında
Sürüm
Tarih
Değişiklik özeti
1.0
30 Eylül 2026
İlk yayın: kapsam, mimari, yol haritası
1.1
30 Eylül 2026
Teknik gözden geçirme: SQLite WAL ve tek yazıcı kuyruğu, Map-Reduce analiz hattı, dosya kararlılık denetimi, Faz 0 test paketi, render motoru kararı (FFmpeg), risk kaydı revizyonu, mimari karar kayıtları
1.2
30 Eylül 2026
Mimari sertleştirme: Tauri kararı ve sidecar süreç modeli, asenkron Map çağrıları, Whisper devre kesici, nesne yönelimli Filtergraph derleyici, Faz 0 testleri T0-10…T0-12, risk R15…R17, ADR-006…009
Okuma Rehberi
Bu doküman Hustler projesinin yönetici özetinden test stratejisine kadar tüm karar noktalarını tek yerde toplar. Hangi bölümün kime ve ne için gerektiğini aşağıdaki tablo gösterir.
Bölüm
İçerik
Ne zaman bakılır?

# 1. Yönetici Özeti

Vizyon, hedef, ana metrik
Karar verirken

# 2. Hedefler ve KPI

Ölçülebilir başarı kriterleri
Faz çıkışlarında

# 3. Kapsam

İçeride/dışarıda olanlar, kullanıcı akışı
Kapsam tartışmasında

# 4. Gereksinimler

Fonksiyonel ve fonksiyonel olmayan
Geliştirme ve test planında

# 5. Mimari

Katmanlar, veri ve eşzamanlılık, süreç modeli, transkript devre kesici, Map-Reduce, dosya kararlılığı, render ve Filtergraph derleyici
Teknik tasarımda
6-7. Şablon ve Senaryo
Şablon şeması, senaryo çıktısı, güvenceler
Faz 3 ve Faz 5'te

# 8. UX İlkeleri

Arayüz ve akış standartları
Faz 6'da

# 9. Yol Haritası

Fazlar, çizelge, çıkış kriterleri
Planlama ve takipte
10-13. Kalite, Güvenlik, Risk, Sürümleme
Test, uyum, risk kaydı, yayın planı
Her faz sonunda
Ek A-D
Mimari karar kayıtları, açık kararlar, ilk hafta, sözlük
Başlangıçta ve karar anlarında

# 1. Yönetici Özeti

Hustler, seçilen bir konuda (örneğin psikoloji) son 7 günün en yüksek performanslı YouTube Shorts ve videolarını tespit eden, transkriptlerini çıkarıp kalıp analizi yapan ve şablona uyumlu, özgün bir senaryo üreten yerel bir Windows uygulamasıdır. Onaylanan senaryo ElevenLabs ile seslendirilir, görsel prompt'ları hazırlanır; görseller uygulama dışında (Google Flow) manuel üretilir ve izlenen klasöre atıldığında 6-7 hazır şablondan biriyle otomatik yerleştirilip render edilir.
Ana hedef
Konu seçiminden yayına hazır MP4'e kadar en fazla 15 dakika. Tüm mimari, öncelik ve fazlama kararları bu hedefe göre verilir.
Stratejik ilkeler
Önce hat, sonra arayüz. Her modül komut satırından tek başına çalışır; arayüz yalnızca bu modülleri çağırır.
Önce doğrula, sonra büyüt. Faz 0'da elle yapılan deneme çalışmıyorsa uygulama yazılmaz.
Harmanlama değil, kalıp analizi. Model kaynak cümleleri kopyalamaz; özgün açı önerir. Bu hem kaliteyi hem hukuki güvenliği artırır.
İnsan onayı zorunlu. Özellikle psikoloji iddialarında yayın öncesi kontrol adımı atlanamaz.
Ölçülmeyen iyileşmez. Her adımın süresi ve her LLM çağrısının maliyeti kaydedilir; optimizasyon tahmine değil veriye dayanır.
Dayanıklılık tasarım gereğidir. Eşzamanlılık, yarım yazılmış dosyalar ve geçersiz LLM çıktısı sonradan yama değil, mimarinin parçasıdır.
"CapCut düzeyi" tanımı
Hedef, tam bir zaman çizelgesi editörü değildir. Hedef; CapCut'ın sunduğu akıcılık, hız ve cila seviyesini şablon odaklı bir üretim akışında yakalamaktır: anlık önizleme, az tıklama, tutarlı tasarım, anlaşılır hata mesajları. Bu kapsam tek geliştirici için gerçekçidir.

# 2. Hedefler ve Başarı Ölçütleri


## 2.1 Zaman bütçesi (15 dakika)

Adım
Hedef
Sorumlu
Not
Konu seç, analiz ve senaryo
≤ 3 dk
Uygulama
Top 20 verisi önceden arka planda çekilmiş olmalı
Senaryo okuma ve onay
≤ 2 dk
Kullanıcı
İddia işaretleri burada kontrol edilir
Ses üretimi
≤ 2 dk
Uygulama
Onaydan sonra otomatik
Görsel üretimi (Flow)
≤ 6 dk
Kullanıcı
Uygulama dışı; süresi ölçülür
Yerleştirme, önizleme, render
≤ 2 dk
Uygulama
Otomatik slot eşleme
Toplam
≤ 15 dk

## 2.2 KPI'lar

KPI
Hedef
Ölçüm yöntemi
Uçtan uca üretim süresi
≤ 15 dk (medyan)
Uygulama içi zamanlayıcı, son 10 üretim
Top 20 listesi süresi
< 30 sn
Faz 1 kabul testi
Şablona sığmayan senaryo oranı
< %10
Senaryo doğrulama günlüğü
Elle düzeltme gerektiren senaryo
< %30
Onay ekranı düzenleme oranı
Render süresi (30-45 sn video)
< 2 dk
Render günlüğü
Taslak önizleme süresi
< 10 sn
Render günlüğü
Şema geçerliliği (ilk denemede)
≥ %95
Doğrulama günlüğü
Şema geçerliliği (≤ 2 yeniden denemeyle)
%100 (aksi halde kontrollü hata)
Doğrulama günlüğü
LLM maliyeti / üretim
Faz 0 baz çizgisi + tanımlı tavan
Çağrı başına token günlüğü
database is locked hatası
0
Eşzamanlılık stres testi
Map aşaması (20 kart)
< 60 sn (tahmin, T0-11 ölçer)
LlmCall günlüğü
Uygulama çökme oranı
< %1 üretimde
Hata günlüğü
Yayınlanan videoda ortalama tutma
Baz çizgi + %10 (v1.5)
YouTube Studio verisi, elle giriş

# 3. Kapsam


## 3.1 Kapsam matrisi

Alan
v1 (İçeride)
Kapsam dışı
Veri
YouTube Data API, skorlama, önbellek
TikTok (v2), diğer platformlar
Metin
Transkript, kalıp analizi, senaryo, iddia işaretleme
Otomatik yayın, otomatik yorum
Ses
ElevenLabs entegrasyonu, kelime zamanlı altyazı
Ses klonlama yönetimi
Görsel
Prompt çıktısı, klasör izleme, oran denetimi
Görsel üretim otomasyonu (uygulama dışı, ileride)
Video
6-7 şablon, önizleme, render (1080x1920)
Serbest zaman çizelgesi editörü
Dağıtım
Windows kurulum paketi
Bulut, çok kullanıcı, satış, mağaza

## 3.2 Ana kullanıcı akışı

Konu girilir veya kayıtlı konulardan seçilir.
Top 20 listesi ve kalıp analizi görüntülenir; istenirse videolar hariç tutulur.
Şablon seçilir; senaryo şablon yapısına uygun üretilir.
Senaryo düzenlenir, iddia işaretleri onaylanır.
Ses üretilir; sahne prompt'ları tek ekranda kopyalanır.
Görseller dışarıda üretilip izlenen klasöre atılır; otomatik yerleşir, uyarılar giderilir.
Önizleme yapılır, tek tıkla render alınır.
4. Ürün Gereksinimleri
Öncelikler MoSCoW yöntemiyle verilmiştir: M (Must), S (Should), C (Could), W (Won't bu sürümde).

## 4.1 Fonksiyonel gereksinimler

ID
Gereksinim
Öncelik
Faz
FR-01
Konu bazlı YouTube araması (son 7 gün, Shorts süre filtresi)
M
F1
FR-02
Skorlama: izlenme/abone oranı (log ölçekli), izlenme hızı, minimum abone eşiği, gizli abone işareti
M
F1
FR-03
Sıralı Top 20 listesi, önbellek, kota göstergesi
M
F1
FR-04
Transkript: yerleşik altyazı, yoksa yt-dlp + Whisper
M
F2
FR-05
Kalıp analizi: kanca türleri, süre, yapı, ortak konular, eksik açılar
M
F2
FR-06
Şablon yapısına uyumlu senaryo (JSON)
M
F3
FR-07
Sahne bazlı görsel prompt, sabit stil öneki, 9:16 notu
M
F3
FR-08
İddia işaretleme ve zorunlu onay adımı
M
F3
FR-09
ElevenLabs ile ses üretimi ve ses profili yönetimi
M
F4
FR-10
Kelime zamanlı altyazı ve stil ayarları
M
F4
FR-11
6-7 şablon, kategori yönetimi, klonlama, içe/dışa aktarma
M
F5
FR-12
İzlenen klasör, sıra numarasıyla slot eşleme, eksik/yanlış oran uyarısı
M
F5
FR-13
Hızlı taslak önizleme (düşük çözünürlüklü proxy render) ve tek tık nihai render
M
F5
FR-14
Adım süresi ölçümü ve "15 dk hedefi" paneli
S
F6
FR-15
Yayın sonrası performans verisi girişi
C
v1.5
FR-16
TikTok veri kaynağı (üçüncü parti servis)
C
F8
FR-17
Toplu (batch) üretim
W
-
FR-18
Klasör izleme: dosya kararlılığı denetimi, bozuk dosya doğrulaması, proje klasörüne kopyalama
M
F5
FR-19
Map-Reduce analiz: transkript başına özet kartı, LLM'e yalnızca kartlar gider
M
F2
FR-20
Token ve maliyet ölçümü, üretim başına tavan ve aşım uyarısı
M
F2
FR-21
SQLite WAL, tek yazıcı kuyruğu, kilit hatasına karşı kontrollü yeniden deneme
M
F1
FR-22
Donanım profili ve Whisper devre kesici (GPU yoksa sınırlı transkript)
M
F2
FR-23
Map çağrılarının sınırlı eşzamanlılıkla (asyncio) çalıştırılması, kısmi başarısızlık yönetimi
M
F2
FR-24
Şablon JSON'dan nesne yönelimli Filtergraph derleyici; elle string birleştirme yasağı
M
F5
FR-25
Sidecar süreç yaşam döngüsü: sağlık kontrolü, iptal, düzgün kapanış, yetim süreç temizliği
M
F6

## 4.2 Fonksiyonel olmayan gereksinimler

Kategori
Gereksinim
Hedef
Performans
Uygulama açılışı; arayüz etkileşim gecikmesi; taslak önizleme süresi
< 3 sn; < 500 ms; < 10 sn
Güvenilirlik
Çökme sonrası proje kurtarma, otomatik kayıt
Her adımda kayıt
Kullanılabilirlik
Yeni konu akışı yönergesiz tamamlanabilir
İlk denemede
Güvenlik
API anahtarları şifreli saklanır
Windows Credential Manager
Taşınabilirlik
Windows 10/11 (WebView2 gerekli); GPU olmadan devre kesiciyle çalışır
CPU yedeği + Whisper sınırı
Gözlemlenebilirlik
Yapılandırılmış günlük, adım süreleri, hata izleri
Her modülde
Bakım
Dış bağımlılıklar (yt-dlp vb.) soyutlama arkasında
Tek dosyada değişim
Eşzamanlılık
Okuma ve yazma çakışmasında kilit hatası yok
WAL + tek yazıcı; 0 hata
Kaynak kullanımı
Kabuğun bellek ayak izi izlenir; render sırasında arayüz donmaz
Baz çizgi Faz 6'da ölçülür
Dosya bütünlüğü
Kararsız veya bozuk dosya render hattına girmez
Kararlılık denetimi zorunlu
Maliyet
Üretim başına token tavanı; aşımda uyarı
Faz 0'da belirlenir

# 5. Sistem Mimarisi


## 5.1 Teknoloji yığını (öneri)

Katman
Seçim
Gerekçe
Arayüz
Tauri 2 (Rust kabuk, WebView2) + React + Tailwind
Hafif kabuk; ağır işler ayrı sidecar süreçlerinde
Çekirdek servis
Python (FastAPI, asyncio, yalnızca localhost) sidecar
yt-dlp, Whisper, LLM entegrasyonu; asenkron I/O
Transkript
yt-dlp + faster-whisper (CUDA varsa GPU; yoksa devre kesicili CPU)
Yerel, ücretsiz
Analiz (Map)
Yerel küçük model veya ucuz model + deterministik çıkarım
Maliyet ve bağlam kontrolü
Analiz (Reduce) ve senaryo
LLM API, JSON şeması zorunlu çıktı + doğrulama
Doğrulanabilir yapılandırılmış sonuç
Ses
ElevenLabs API (zaman damgalı çıktı)
Kelime zamanlı altyazı
Render
FFmpeg; şablon JSON nesne yönelimli Filtergraph derleyiciyle komuta çevrilir (5.9); NVENC opsiyonel
Hafif ve hızlı; string manipülasyonu yok
Veri
SQLite (WAL modu) + yerel dosya sistemi
Kurulumsuz, taşınabilir, eşzamanlı okuma

## 5.2 Modüller ve sorumluluklar

Modül
Sorumluluk
Girdi → Çıktı
Discovery
Arama, skorlama, önbellek
Konu → Sıralı video listesi
Transcribe
Transkript çıkarma, donanım profili, Whisper devre kesici
Video ID → Metin + dil
Analyze
Map-Reduce kalıp analizi
Transkriptler → Özet kartları → Analiz JSON
Script
Senaryo ve prompt üretimi
Analiz + şablon → Senaryo JSON
Voice
Ses ve zaman damgaları
Senaryo → WAV/MP3 + kelime zamanları
Assets
Klasör izleme, kararlılık denetimi, doğrulama, eşleme
Görseller → Doğrulanmış kopyalar → Slot atamaları
Template
Şablon yönetimi ve doğrulama
Şablon JSON → Doğrulanmış şablon
Render
Filtergraph derleyici, taslak önizleme, nihai çıktı (FFmpeg)
Proje → MP4
Timer
Adım süresi ölçümü
Olaylar → Süre kayıtları
Supervisor
Görev kuyruğu, sidecar sağlık kontrolü, iptal ve kapanış
Görevler → Durum ve ilerleme olayları

## 5.3 Temel veri varlıkları

Varlık
Anahtar alanlar
Topic
id, ad, kategori, dil, son_yenileme
Video
id, kanal_id, başlık, yayın_zamanı, süre, izlenme, beğeni, abone, skor
Transcript
video_id, dil, kaynak (altyazı/whisper), metin, hash, oluşturma_zamanı
SummaryCard
video_id, transkript_hash, prompt_sürümü, kanca_türü, ana_fikir, yapı, token_sayısı
LlmCall
id, modül, model, giriş_token, çıkış_token, maliyet, süre, sonuç
HardwareProfile
gpu_var, cuda_sürümü, cpu_çekirdek, whisper_rtf, ölçüm_zamanı
Analysis
topic_id, kanca_türleri, ort_süre, yapı, eksik_açılar, sürüm
Project
id, topic_id, template_id, senaryo, ses_yolu, durum, süre_kayıtları
Template
id, kategori, şema_sürümü, slotlar, stil

## 5.4 Veri Katmanı ve Eşzamanlılık

Arka plandaki veri motoru yazarken arayüz aynı anda okur. SQLite varsayılan (rollback journal) modda bu durumda "database is locked" hatası verir. Bu nedenle aşağıdaki yapılandırma zorunludur.
Ayar / kural
Değer
Amaç
PRAGMA journal_mode
WAL
Okuyucular yazıcıyı, yazıcı okuyucuları engellemez
PRAGMA synchronous
NORMAL
WAL modunda dayanıklılık ve hız dengesi
PRAGMA busy_timeout
5000 ms
Kısa yazma çakışmasında hata yerine bekleme
PRAGMA foreign_keys
ON
Veri bütünlüğü
Yazma mimarisi
Tek yazıcı kuyruğu; BEGIN IMMEDIATE ile kısa işlemler
WAL yazar-yazar çakışmasını kaldırmaz; kuyruk kaldırır
Okuma bağlantıları
Ayrı, salt okunur bağlantı havuzu
Arayüz okumaları yazmayı beklemez
Toplu yazma
Discovery sonuçları tek işlemde yazılır
Satır satır commit yok; kilit süresi kısalır
Konum
Yerel disk (ağ paylaşımı yasak)
WAL ağ dosya sistemlerinde güvenilir değildir
Yedekleme
SQLite backup API; -wal ve -shm dosyaları tek başına kopyalanmaz
Tutarlı yedek
Kabul testi
1 yazıcı ve 5 okuyucu 10 dakika eşzamanlı çalışır; "database is locked" hata sayısı 0 olmalıdır (Faz 0, T0-6).

## 5.5 Yürütme Modeli ve Süreç Yönetimi

Arayüz kabuğu ile ağır işler ayrı süreçlerde çalışır. Tauri yalnızca pencere ve sidecar yaşam döngüsünden sorumludur; iş mantığı Python servisindedir.
Konu
Karar
Kabuk
Tauri 2 (Rust): arayüz penceresi, sidecar başlatma ve kapatma. İş mantığı kabukta yazılmaz
Sidecar'lar
Python servisi (FastAPI) ve FFmpeg ikilisi Tauri sidecar olarak paketlenir; paketleme (PyInstaller vb., Whisper/CTranslate2 bağımlılıklarıyla) Faz 0'da prototiplenir
Güvenlik
Servis yalnızca localhost'ta, dinamik portta ve oturum belirteciyle dinler; başka yerel süreçler erişemez
Sağlık kontrolü
Açılışta /health yoklaması; yanıt yoksa sınırlı yeniden başlatma, sonra kullanıcıya net hata
Yetim süreçler
Windows Job Object ile alt süreçler kabukla birlikte sonlanır; açılışta önceki oturumdan kalan süreçler temizlenir
Görev kuyruğu
Uzun işler (transkript, render) kuyruğa alınır; ilerleme ve iptal olayları arayüze akış olarak iletilir
Ağ bağlantılı işler
YouTube, ElevenLabs ve LLM çağrıları asyncio ile eşzamanlı çalışır; her akış için sınırlı eşzamanlılık (asyncio.Semaphore)
CPU/GPU bağlı işler
Whisper, yerel model, decode ayrı süreçte veya süreç havuzunda çalışır; event loop asla bloklanmaz
Veritabanı yazımı
Tüm yazmalar tek yazıcı kuyruğundan geçer (Bölüm 5.4)
Karar notu
Arayüz kabuğunun bellek farkı gerçektir, ancak asıl kaynak tüketimi Whisper ve FFmpeg süreçlerindedir. Tauri, Windows'ta sisteme ait WebView2 bileşenini (Chromium tabanlı) kullanır; yük ortadan kalkmaz, paylaşılan bileşene kayar. Bu ödünleşim ve küçük Rust kabuk kodu kabul edilmiştir (ADR-006).

## 5.6 Transkript Hattı ve Whisper Devre Kesici

Transkript iki kademelidir: önce videonun yerleşik altyazısı, yoksa Whisper. CUDA olmayan bir makinede 20 videonun tamamını Whisper ile çıkarmak 15 dakikalık hedefi tek başına aşabilir; bu nedenle Whisper aşaması bir devre kesici arkasındadır. Gerçek süre model boyutuna ve video uzunluğuna bağlıdır; kurallar Faz 0'daki ölçüme (T0-10) göre kalibre edilir.
Kural
Tanım
Donanım profili
İlk açılışta ve sürücü değişince GPU/CUDA tespiti, çekirdek sayısı ve 10 sn'lik örnek sesle gerçek zaman katsayısı (RTF) ölçümü; HardwareProfile'a yazılır
Kademe 1
Yerleşik altyazı önceliklidir; Whisper yalnızca altyazısı olmayan videolar için çalışır
Devre kesici: video sayısı
CUDA yoksa Whisper yalnızca skoru en yüksek ilk 5 altyazısız video ile sınırlı (varsayılan, ayarlanabilir)
Devre kesici: süre bütçesi
Toplam Whisper süre bütçesi (varsayılan 90 sn, RTF'ye göre ayarlanır); aşılırsa kalan işler iptal edilir
Devre kesici: video süresi
Tek video için ses süresi üst sınırı; aşan video Whisper'a girmez
Durumlar
Kapalı (normal) → Açık (bütçe aşıldı, Whisper atlanır) → Yarı açık (sonraki üretimde tek deneme)
Tetiklenince
Kalan videolar "transkriptsiz" işaretlenir; analiz mevcut kartlar ve metriklerle (başlık, açıklama, süre, istatistik) sürer; arayüzde "X video atlandı" uyarısı
Model seçimi
CPU'da küçük model (int8); GPU'da daha büyük model
Önceden hazırlama
Kayıtlı konular için transkript ve özet kartları arka planda önbelleğe alınır; 15 dk sayacı başlamadan hazır olur

## 5.7 Analiz Hattı: Map-Reduce

20 ham transkripti tek çağrıda LLM'e göndermek maliyeti artırır, sonucu tekrarlanamaz kılar ve uzun videolarda bağlam sınırını aşabilir. Bu nedenle analiz iki aşamalı yürütülür ve ham transkript senaryo aşamasına hiç taşınmaz.
Aşama
İşlem
Çıktı / sınır

# 0. Hazırlık

Metin temizleme, hash hesabı, önbellek sorgusu
Önbellekte varsa Map atlanır
Map A (yerel, deterministik)
Kanca adayı (ilk ~15 kelime), kelime sayısı, dakikadaki kelime, cümle sayısı, kural tabanlı CTA tespiti
Metrik JSON; LLM maliyeti sıfır
Map B (model)
Transkript başına özet kartı: ana fikir, kanca türü, yapı, ton
Kart başına çıkış tavanı (tahmin: ≤ 200 token); uzun videolarda parçalı özetleme
Map B eşzamanlılığı
asyncio.gather ile eşzamanlı çağrı; asyncio.Semaphore ile sınırlı (varsayılan 5-8); çağrı başına zaman aşımı; 429 için üstel geri çekilme + jitter; return_exceptions=True ile kısmi başarısızlık
Ardışık çağrı yok; hedef: 20 kart < 60 sn (tahmin, T0-11 ölçer)
Reduce
20 kart + metrikler tek çağrıda kalıp analizine dönüşür
Tek çağrı; tahmini bağlam birkaç bin token
Senaryo
Analiz JSON + şablon yapısı → senaryo
Ham transkript gönderilmez
Önbellek
Anahtar: transkript_hash + prompt_sürümü
Aynı girdi için ikinci çağrı yok
Ölçüm
Her çağrı LlmCall tablosuna yazılır
Üretim başına maliyet tavanı ve uyarı
Gerekçe: Kısa Shorts transkriptlerinde bağlam sınırı tek başına sorun değildir; asıl kazanç maliyet, tekrarlanabilirlik ve uzun video desteğidir.
Risk: Map aşaması ayrıntı kaybettirebilir. Faz 0'daki A/B testi (T0-5) map-reduce çıktısını tam bağlam çıktısıyla karşılaştırır; kalite kaybı eşiği aşarsa Reduce'a seçili kanca cümleleri eklenir.
Model seçimi: Map için yerel model mi ucuz API modeli mi kullanılacağı T0-5 sonucuna göre belirlenir. Yerel model CPU bağlıdır; asyncio ile değil süreç havuzunda çalışır.
Kısmi başarısızlık: Başarısız kartlar yalnızca kendi çağrılarını yeniden dener. Kartların belirlenen oranı (varsayılan %80) hazırsa Reduce başlar, eksikler işaretlenir.

## 5.8 Klasör İzleme ve Dosya Kararlılığı

İşletim sistemi dosyayı diske yazmayı bitirmeden okumak render hattını çökertir. İzleyici olay gördüğünde dosyayı işlemez; yalnızca aday olarak kaydeder ve aşağıdaki kapılardan geçirir.
Adım
Kural

# 1. Olay

Dosya izleyici olayı yalnızca aday listesine ekler

# 2. Filtre

Geçici uzantılar (.tmp, .crdownload, .part), gizli ve sistem dosyaları yok sayılır

# 3. Debounce

Aynı dosya için olay yağmuru 1500 ms'lik pencerede tek olaya birleştirilir

# 4. Boyut kararlılığı

Boyut ve değiştirilme zamanı ardışık 2 yoklamada (500 ms aralık) değişmez ve boyut > 0

# 5. Kilit kontrolü

Dosya salt okunur açılabiliyor (Windows paylaşım ihlali yok)

# 6. Doğrulama

Tam decode denemesi (Pillow verify, ffprobe); çözünürlük ve 9:16 oran denetimi
7. İzolasyon
Doğrulanan dosya SHA-256 ile proje klasörüne kopyalanır; render yalnızca kopyadan okur

# 8. Zaman aşımı

Üstel geri çekilmeyle yeniden deneme; 30 sn sonra "kararsız dosya" uyarısı, hat çökmez
Kabul testi
Parça parça yavaş yazan bir script ile 100 dosya bırakılır; çökme sayısı 0, yarım dosyayla render sayısı 0 olmalıdır (Faz 0, T0-7).

## 5.9 Render Mimarisi (FFmpeg)

Bileşen
Karar
Motor
FFmpeg; şablon JSON nesne yönelimli Filtergraph derleyiciyle komuta çevrilir (5.9.1); alt süreç olarak çalıştırılır, ilerleme -progress çıktısından okunur
Görsel sahneler
scale + crop (9:16), zoompan hareketi, süre sahne süresinden gelir
Geçişler
xfade
Altyazı
ASS dosyası; kelime bazlı vurgu (karaoke etiketleri); fontlar uygulamayla paketlenir
Ses
ElevenLabs sesi + müzik miksi (volume, amix), loudnorm ile seviye dengeleme
Önizleme
Aynı filtergraph 360x640, hızlı ön ayarla taslak render; nihai: libx264 CRF 18, opsiyonel NVENC
Dayanıklılık
Windows yol ve Unicode normalizasyonu, uzun komutlar için filter_complex_script dosyası, stderr günlüğü, zaman aşımı
Lisans
Kullanılan FFmpeg derlemesinin (LGPL/GPL) koşulları kontrol edilir; yalnızca yerel kullanım, dağıtım yok
Kabul edilen ödünleşimler
FFmpeg ile tarayıcı tabanlı canlı önizleme yoktur; önizleme hızlı taslak renderdır (hedef < 10 sn). Karmaşık altyazı animasyonları (yaylanma, bulanıklık) ASS ile sınırlıdır; şablon tasarımı bu sınıra göre yapılır. FFmpeg render süresi riskini azaltır, sıfırlamaz.

### 5.9.1 Filtergraph Derleyici (nesne yönelimli)

Sahne sayısı, süre ve animasyona göre değişen filter_complex ifadelerini düz metin birleştirmeyle üretmek bakım yapılamaz bir yapı doğurur. Şablon JSON'ı, bir ara temsil (nesne grafı) üzerinden komuta derlenir.
Kural
Filtergraph metni hiçbir yerde elle string birleştirmeyle üretilmez. Metin yalnızca Filter.render() ve FilterGraph.compile() içinde oluşur; kaçış (escape) kuralları tek noktadadır.
Akış: Şablon JSON → TemplateModel (doğrulama) → Timeline (kare cinsinden süreler) → FilterGraph (düğümler ve etiketler) → GraphValidator → Compiler (Draft/Final profili) → filter_complex_script dosyası → FFmpegRunner.
Sınıf
Sorumluluk
Not
TemplateModel / SceneSpec
Şablon şeması ve doğrulama (pydantic)
Şema sürümlü
Timeline / TimeCode
Sahne sürelerini ses ve şablondan tam sayı kare olarak hesaplar
Kayan noktalı süre kayması ve yuvarlama hatası olmaz
Label / LabelAllocator
Benzersiz akış etiketleri üretir
Etiket çakışması yapısal olarak imkânsız
Filter (değişmez)
Ad, parametreler, giriş/çıkış etiketleri; render() tek filtre metnini üretir
Kaçış kuralları tek yerde
FilterChain
Sıralı filtre zinciri (scale → crop → zoompan → fps)
Zincir bir birimdir
FilterGraph
Zincirleri ve bağlantıları tutar; compile() metni üretir
Metin üretiminin tek kapısı
SceneClipBuilder
Görsel sahnesi zinciri: 9:16 scale + crop, zoompan, fps, setsar
Hareket türleri kayıt defteriyle eklenir
TransitionPlanner
xfade ofsetlerini hesaplar
Ofset = önceki sahnelerin toplamı − geçiş toplamı; birim testli
AudioMixer
Ses ve müzik miksi, volume, amix, loudnorm
Süre ses dosyasından gelir
AssDocument / SubtitleStyle
Kelime zamanlı ASS dosyasını üretir
Altyazı filtresi grafa eklenir
GraphValidator
Kopuk veya kullanılmayan etiket, döngü, süre tutarsızlığı, eksik girdi denetimi
Derlemeden önce çalışır
Profile (Draft, Final)
Çözünürlük, preset, codec, CRF, NVENC seçimi (strateji deseni)
Aynı graf, farklı profil
FFmpegRunner
Alt süreç, -progress ayrıştırma, zaman aşımı, iptal, hata ayrıştırma
stderr günlüğü
EscapeUtil
Filtre argümanı ve Windows yolu kaçışı
Örn. sürücü harfi iki noktası
@dataclass(frozen=True)
class Filter:
    name: str
    args: dict[str, str | int | float]
    inputs: tuple[Label, ...] = ()
    outputs: tuple[Label, ...] = ()
    def render(self) -> str: ...   # kaçış kuralları yalnızca burada
620:
graph = FilterGraph()
for scene in timeline.scenes:
    graph.add(SceneClipBuilder(scene, profile).build())
graph.add(TransitionPlanner(timeline).build())
graph.add(AudioMixer(audio, music).build())
GraphValidator(graph).run()
script.write_text(graph.compile(), encoding="utf-8")
Derleyici kalite kuralları
Snapshot testleri: Her şablon için derlenen graf metni altın metinle karşılaştırılır.
Özellik tabanlı testler: 1-12 sahne için rastgele üretimde tüm etiketler bağlıdır ve toplam süre ses süresine ±1 kare uyar.
Kuru çalıştırma: Derlenen komut ffmpeg -f null ile denenir; hata kayda geçer.
Genişletilebilirlik: Yeni geçiş veya hareket, çekirdek değişmeden yeni sınıf ve kayıtla eklenir.
Sürüm uyumu: Şablon şema_sürümü ile derleyici sürümü eşleşmezse şablon açılmaz, net hata verilir.
Performans: zoompan ve crop tabanlı hareket alternatifleri T0-8'de süre açısından karşılaştırılır.
6. Şablon Sistemi Spesifikasyonu
Şablonlar sürümlü JSON dosyalarıdır. Senaryo motoru şablonun yapısını girdi olarak alır; böylece metin baştan şablona uyumlu üretilir ve elle kısaltma ihtiyacı azalır.
{
  "id": "psikoloji-hizli-01",
  "sema_surumu": "1.0",
  "kategori": "Psikoloji",
  "cozunurluk": [1080, 1920],
  "fps": 30,
  "sahne_sayisi": 8,
  "sahne_sure_araligi_sn": [3, 6],
  "sahne_kelime_siniri": 18,
  "hareket": { "tur": "zoompan", "yogunluk": 0.08 },
  "gecis": { "tur": "xfade", "efekt": "fade", "sure_sn": 0.4 },
  "altyazi": { "bicim": "ass", "stil": "kelime-vurgulu", "konum": "alt-orta", "font": "Inter" },
  "muzik_seviyesi_db": -22,
  "render": { "motor": "ffmpeg", "codec": "libx264", "crf": 18 }
}
Şablon kalite kontrol listesi
Şema doğrulaması geçer; eksik alanla şablon kaydedilemez.
Her şablon için referans render (altın dosya) saklanır.
Slot sayısı ve oranı değiştiğinde senaryo motoru uyarılır.
Şablon sürümü değiştiğinde eski projeler eski sürümle açılır.
Şablon geçerli bir filtergraph olarak derlenir; derleme testi geçmeden kaydedilemez.

# 7. Senaryo Motoru Spesifikasyonu

7.1 Çıktı sözleşmesi
Alan
Açıklama
Doğrulama
kanca
İlk 3 sn metni ve kanca türü
≤ 15 kelime
sahneler[]
Metin, süre, görsel prompt, sahne no
Şablon sahne sayısıyla eşit
kapanis
Kapanış ve eylem çağrısı
Zorunlu
iddialar[]
Doğrulanması gereken iddialar
Onaysız render engellenir
kaynak_notu
Analiz edilen video ID'leri
Kopya cümle taraması

## 7.2 Kalite güvenceleri

Özgünlük: Kaynak transkriptle üst üste binen ifade oranı eşiği aşarsa senaryo yeniden üretilir.
Yapı: Sahne sayısı, süre ve kelime sınırı şemayla doğrulanır; sığmayan çıktı otomatik yeniden denenir.
Doğruluk: Psikoloji ve sağlık iddiaları işaretlenir; teşhis, tedavi vaadi ve kesin sonuç dili engellenir.
Tutarlılık: Görsel prompt'lara sabit stil öneki, sahne numarası ve 9:16 notu otomatik eklenir.

## 7.3 LLM Çıktı Güvencesi

Katman
Kural
Şema zorunlu çıktı
Yapılandırılmış çıktı (tool use / JSON şeması) kullanılır; sonuç pydantic veya jsonschema ile doğrulanır
Kontrollü yeniden deneme
Doğrulama hatası, hata mesajıyla modele geri verilir; en fazla 2 yeniden deneme
Başarısızlık davranışı
2 denemeden sonra sessiz kabul yok; kullanıcıya net hata ve elle düzenleme seçeneği
Anlamsal doğrulama
Sahne sayısı, kelime sınırı, süre toplamı, görsel prompt varlığı, kopya taraması
Halüsinasyon
Modelde sıfıra indirilemez. Kontrol yöntemi iddia işaretleme ve zorunlu insan onayıdır; test hedefi hataların yakalanmasıdır

# 8. Kullanıcı Deneyimi İlkeleri

İlke
Uygulama standardı
Tek akış
Konu → Top 20 → Senaryo → Ses → Görseller → Önizleme → Render; her adım tek ekran
Hız hissi
Uzun işlemlerde ilerleme çubuğu ve tahmini süre; arayüz asla donmaz
Az tıklama
Tek tık kopyalama, sürükle-bırak, kayıtlı ayarlar, klavye kısayolları
Güvenli varsayılanlar
Onaysız iddiayla render engellenir; eksik görselde net uyarı
Görünür süre
"15 dk hedefine göre neredesin?" paneli her adımda
Cila
Koyu tema, tutarlı boşluklar, anlaşılır Türkçe hata mesajları

# 9. Yol Haritası

Süreler tek geliştirici için tahmindir; her faz sonunda gerçek süreyle güncellenmelidir. Bir faz, çıkış kriterini karşılamadan sonrakine geçilmez.

## 9.1 Zaman çizelgesi (12 hafta)

Faz
H1
H2
H3
H4
H5
H6
H7
H8
H9
H10
H11
H12
F0 Doğrulama
F1 Veri Motoru
F2 Transkript/Analiz
F3 Senaryo Motoru
F4 Ses ve Altyazı
F5 Şablon ve Render
F6 Arayüz
F7 Cila ve Yayın

## 9.2 Faz detayları

Faz
Teslimatlar
Çıkış kriteri
F0 Doğrulama
4-5 gün
Teknik doğrulama test paketi (T0-1…T0-12) ve elle uçtan uca 3 video (Bölüm 9.3)
Tüm T0 testleri kabul kriterini geçer; geçmeyen için mimari karar revize edilir
F1 Veri Motoru
1-1,5 hafta
YouTube arama, skorlama, önbellek, kota yönetimi, SQLite WAL + yazıcı kuyruğu, arka plan yenileme
Top 20 listesi < 30 sn; eşzamanlılık stres testinde 0 kilit hatası
F2 Transkript ve Analiz
1 hafta
Donanım profili, Whisper devre kesici, yerleşik altyazı önceliği, asenkron Map-Reduce hattı, önbellek, token ve maliyet ölçümü
20 video için transkript + analiz < 3 dk; maliyet tavanın altında
F3 Senaryo Motoru
1 hafta
Şablona uyumlu senaryo, görsel prompt, iddia işaretleme
Sığmayan senaryo < %10; iddia onayı çalışıyor
F4 Ses ve Altyazı
1 hafta
ElevenLabs entegrasyonu, kelime zamanlı altyazı, süre uyumu
Onaydan sese ≤ 2 dk; senkron hatasız
F5 Şablon ve Render
2-3 hafta
6-7 şablon, nesne yönelimli Filtergraph derleyici, kararlılık denetimli klasör izleme, taslak önizleme, render
Render < 2 dk; taslak < 10 sn; snapshot, altın dosya ve yavaş-kopyalama testleri geçer
F6 Arayüz
1,5-2 hafta
Tauri kabuğu, sidecar yaşam döngüsü, akış ekranı, süre paneli, kısayollar, koyu tema
Yeni konu akışı yönergesiz tamamlanır; yetim süreç 0
F7 Cila ve Yayın
1 hafta
Kurulum paketi, yedekleme, kurtarma, günlükleme, güncelleme
Temiz makinede kurulum ve uçtan uca üretim
F8 (opsiyonel)
TikTok servisi, OCR, müzik kütüphanesi, görsel yarı otomasyonu
Veriye dayalı ihtiyaç kanıtlandığında başlar

## 9.3 Faz 0 Test Paketi

Elle analiz içerik kalitesini sınar; API sınırlarını, LLM şema uyumunu, eşzamanlılığı ve render hattını sınamaz. Bu nedenle Faz 0 aşağıdaki mühendislik testlerini de kapsar. Bir test geçmezse ilgili mimari karar Faz 1'e girmeden revize edilir.
ID
Test
Yöntem
Kabul kriteri
T0-1
YouTube API meta veri
En az 5 konu x 20 video çekilir; kota tüketimi, 403/429 hataları ve yeniden deneme davranışı günlüğe alınır
100 video meta verisi eksiksiz; kota günlük limitin altında; işlenmemiş hata 0
T0-2
Shorts sınıflandırma
Süre filtresiyle ayrılan 20 video elle doğrulanır
Yanlış sınıflandırma < %10; güncel süre eşiği doğrulanmış
T0-3
Transkript kapsamı
20 video; yerleşik altyazı yoksa Whisper
Kapsama ≥ %90; Whisper süresi ve kalitesi kayıtlı
T0-4
LLM şema uyumu
30 üretim (3 konu x 10 çalıştırma), şema zorunlu çıktı + doğrulama
İlk denemede ≥ %95 geçerli; ≤ 2 yeniden denemeyle %100 geçerli
T0-5
Map-Reduce A/B
3 konuda map-reduce ile tam bağlam çıktısı körlemesine karşılaştırılır; token maliyeti ölçülür
Belirgin kalite kaybı yok (önerilen eşik: ≤ 1/5 puan); maliyet baz çizgisi ve tavan belirlenir
T0-6
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.


---
# BÖLÜM 2: MÜHENDİSLİK STANDARTLARI VE MİMARİ (v1.1)
---

, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
HUSTLER
Kodlama Yol Haritası ve Mühendislik Standartları
Ürün Yol Haritası v1.2'nin uygulama planı: depo yapısı, kodlama standartları, kalite kapıları, kilometre taşları ve görev listesi.
Doküman kontrolü
Sürüm
1.1 (Taslak - Onay Bekliyor)
Tarih
30 Eylül 2026
Bağlı doküman
Hustler Ürün Yol Haritası ve Geliştirme Yönergesi v1.2
Kullanım
Yerel, kişisel, ticari olmayan
Sınıflandırma
Gizli - Dahili
Kapsam
Mühendislik uygulaması; ürün kararları ürün dokümanında kalır
Sürüm
Tarih
Değişiklik özeti
1.0
30 Eylül 2026
İlk yayın: depo yapısı, standartlar, kilometre taşları M0-M8
1.1
30 Eylül 2026
Dört teknik düzeltme: Tauri IPC köprüsü, CPU bağlı model yönetimi, kuru çalıştırma zorunluluğu, SQLite büyüme bakımı. Ek olarak görev sıralaması düzeltildi (TemplateSpec ve Timeline çekirdekleri öne alındı), kilometre taşı bağımlılık tablosu eklendi

# 1. Amaç ve Mühendislik İlkeleri

Bu doküman, ürün yol haritasındaki kararların nasıl kodlanacağını tanımlar: depo düzeni, araç seti, sözleşmeler, kalite kapıları ve görev bazında kilometre taşları. Ürün dokümanıyla çelişen bir nokta olursa ürün dokümanı geçerlidir ve bu belge güncellenir.
"Standart üstü" ne demek?
Bir belge kaliteyi garanti etmez. Üst seviye mühendislik, kalite kapılarının (tip denetimi, testler, performans bütçesi, güvenlik taraması) CI'da gerçekten zorunlu olmasından ve ihlalde derlemenin kırılmasından gelir. Bu belge o kapıları tanımlar; disiplin uygulamada kazanılır.
İlke
Uygulama
Sözleşme önce
Tüm veri modelleri pydantic ile tek yerde tanımlanır; JSON Schema ve TypeScript tipleri otomatik üretilir. Elle yazılmış ikinci kopya yoktur.
CLI önce
Her modül hustler komutuyla tek başına çalışır. Arayüz yalnızca aynı servisleri çağırır.
Yürüyen iskelet
İlk hafta uçtan uca en ince akış (kabuk → sidecar → veritabanı → CI) çalışır; modüller sonra bu iskelete takılır.
Saf çekirdek, ince kenar
Skorlama, zamanlama, filtergraph derleme saf mantıktır. Ağ, disk ve süreç etkileşimi ince adaptörlerde toplanır (ports and adapters).
Tekrar üretilebilirlik
Kilit dosyaları, sabit sürümler, sahte servisler ve kayıtlı yanıtlarla deterministik testler; her çalıştırma yeniden oynatılabilir.
Ölç, sonra optimize et
Performans bütçeleri otomatik ölçülür; regresyon derlemeyi kırar.
Karar kaydı
Mimariyi etkileyen her değişiklik ADR ile docs/adr altında kayıt altına alınır.

# 2. Depo Yapısı

Tek depo (monorepo). Her bileşenin sorumluluğu ve bağımlılık yönü nettir: arayüz → sözleşmeler ← çekirdek servis.
hustler/
  apps/desktop/          # Tauri 2 kabuk (Rust, ince) + React arayüzü
    src-tauri/bridge/    # IPC köprüsü: rota izin listesi, olay kanalı
  services/core/         # Python paketi: FastAPI sidecar + CLI
    hustler/
      contracts/         # pydantic modelleri (tek doğruluk kaynağı)
      common/            # log, hata sınıfları, ayarlar, zaman ve yol yardımcıları
      storage/           # SQLite: WriterQueue, ReaderPool, göçler
      discovery/  transcribe/  analyze/  script/  voice/
      assets/  templates/  render/  supervisor/  timer/
      adapters/          # youtube, llm, tts, whisper, ffmpeg (gerçek + sahte)
      prompts/           # sürümlü prompt dosyaları
    tests/               # unit, property, contract, integration, golden
  packages/contracts/    # üretilen JSON Schema + TypeScript tipleri
  templates/             # şablon JSON dosyaları + altın (referans) render'lar
  tools/                 # Faz 0 testleri, bench, stres, sahte servisler
  docs/adr/              # mimari karar kayıtları
  .github/workflows/     # CI (veya yerel eşdeğeri)
Bağımlılık yönü: Alan modülleri (discovery, analyze...) yalnızca contracts ve common'a bağlanır; dış dünyaya yalnızca adapters üzerinden çıkar.
Rust sınırı: Kabuk kodu ince kalır (pencere, sidecar yaşam döngüsü, süreç grubu, IPC köprüsü). Köprü genel bir proxy'dir; endpoint başına Rust kodu yazılmaz. İş mantığı Rust'a yazılmaz.
Üretilen dosyalar: packages/contracts altındaki dosyalar elle düzenlenmez; CI güncel olup olmadığını denetler.

# 3. Araç ve Teknoloji Standartları

Sürümler ilk gün kilitlenir. Bu belge sürüm numarası vermez; gerçek kaynak kilit dosyalarıdır (uv.lock, pnpm-lock, Cargo.lock).
Alan
Araç
Kural
Python
Python 3.12, uv (bağımlılık ve ortam)
Kilit dosyası zorunlu; sistem Python'una dokunulmaz
Biçim ve lint
ruff (lint + format)
CI'da hata; pre-commit'te otomatik düzeltme
Tip denetimi
mypy strict (çekirdek paketler)
Any yasak; istisna yorumla gerekçelendirilir
Test (Python)
pytest, pytest-asyncio, hypothesis, syrupy, respx
Özellik ve snapshot testleri çekirdekte zorunlu
HTTP
httpx (async)
Her çağrıda zaman aşımı; kayıtlı yanıtlar için respx
API
FastAPI + uvicorn, SSE
OpenAPI şeması üretilir; istemci tipleri otomatik
Doğrulama / ayar
pydantic v2, pydantic-settings
Sırlar ayarda değil, Credential Manager'da
Log
structlog (JSON)
run_id ve adım bilgisi her satırda
Veritabanı
sqlite3 + WriterQueue; numaralı SQL göçleri
WAL, tek yazıcı, göç öncesi yedek
Arayüz
TypeScript strict, React, Vite, pnpm, Tailwind
Sunucu durumu için TanStack Query
Arayüz testi
Vitest + Testing Library; e2e aracı Faz 6'da seçilir
Ana akış için en az bir e2e
Rust
rustfmt, clippy (uyarılar hata)
Kod hacmi küçük tutulur
Görev çalıştırıcı
just (veya Taskfile)
dev, check, test, gen, bench, package
Kanca ve tarama
pre-commit, gitleaks, pip-audit, pnpm audit, cargo audit
Sırlar ve bilinen açıklar derlemeyi durdurur

# 4. Sözleşmeler ve API Tasarımı


## 4.1 Ana sözleşmeler

Sözleşme
Ana alanlar
Kullanan modüller
VideoRecord
id, kanal, başlık, süre, istatistikler, skor, shorts_mu
discovery, analyze
TranscriptRecord
video_id, kaynak, dil, metin, hash
transcribe, analyze
SummaryCard
video_id, kanca_türü, ana_fikir, yapı, token_sayısı
analyze
AnalysisResult
kalıplar, eksik_açılar, metrikler, prompt_sürümü
analyze, script
ScriptDoc
kanca, sahneler[], kapanış, iddialar[], kaynak_notu
script, voice, render
TemplateSpec
şema_sürümü, sahne_sayısı, hareket, geçiş, altyazı, render
templates, script, render
Timeline
sahneler[] (tam sayı kare aralıkları), ses_süresi
voice, render
RunEvent
run_id, adım, durum, ilerleme, zaman, yük
tüm modüller, arayüz, timer

## 4.2 API kuralları

Kaynak bazlı REST + SSE: Python servisi bunları sunar. Uzun işler 202 ve görev kimliği döner; ilerleme SSE ile akar. Arayüz bunlara doğrudan değil, Tauri IPC köprüsü üzerinden ulaşır (Bölüm 4.3).
Hatalar: RFC 9457 (Problem Details) biçimi; hata türleri sabit ve arayüzde eşlenir.
İdempotens: İş başlatan POST çağrıları idempotency anahtarı alır; tekrarlanan istek ikinci iş üretmez.
İptal: Her uzun görev iptal edilebilir (DELETE /v1/tasks/id); iptal alt süreçlere iletilir.
Sürüm ve güvenlik: Yol /v1 ile sürümlüdür; servis yalnızca 127.0.0.1 üzerinde dinler ve her çağrıda oturum belirteci ister. Port ve belirteç yalnızca Rust köprüsünde bilinir; arayüze verilmez.
Olaylar: Timer, süre panelini ve günlükleri RunEvent akışından üretir; ayrı bir ölçüm yolu yoktur.

## 4.3 Tauri IPC Köprüsü

Arayüz (React) ağa doğrudan erişmez. Tüm çağrılar Tauri invoke komutlarıyla Rust köprüsüne gider; köprü çağrıyı Python servisine iletir.
React --invoke(api_call)--> Rust köprüsü --127.0.0.1 + belirteç--> FastAPI sidecar
React <--Tauri Channel----- Rust köprüsü <--SSE olay akışı------- FastAPI sidecar
Katman
Kural
React
Yalnızca üretilmiş TypeScript istemcisi kullanılır; taşıma katmanı invoke'tur. fetch, XMLHttpRequest ve WebSocket ile ağ çağrısı yasaktır (ESLint no-restricted-globals + CSP connect-src kısıtı).
Tauri capabilities
Yalnızca köprü komutları izinlidir (ör. api_call, subscribe_events, cancel_task, pick_folder); başka komut veya eklenti izni verilmez.
Rust köprüsü
Tek genel proxy komutu; endpoint başına komut yazılmaz. Rota izin listesi OpenAPI şemasından üretilir; istek boyutu ve süre sınırı uygulanır; Problem Details yanıtı aynen iletilir.
Olay akışı
Python SSE akışını Rust okur ve Tauri Channel ile arayüze iletir; geri basınç ve bağlantı kopması yönetilir; kanal kapanınca iptal iletilir.
Python servisi
Yalnızca 127.0.0.1; her istekte oturum belirteci; CORS kapalı; port dinamik.
Test
Sahte sidecar ile köprü sözleşme testi; izin listesi dışı rotanın reddi; CSP ihlali e2e testi (K-709).
Karar notu (ADR-010)
Bu tasarım arayüzü ağ katmanından ayırır; ancak Rust ile Python arasında yerel bir HTTP bağlantısı kalır ve bunu yalnızca oturum belirtecini bilen Rust kullanır. Böylece FastAPI, OpenAPI ve mevcut test araçları korunur. Port gerektirmeyen taşımalar (stdio, named pipe) T0-12'de karşılaştırılır. Bedeli: her istekte küçük ek gecikme ve köprü için yazılacak Rust kodu; bu yüzden köprü genel bir proxy olarak tutulur.

# 5. Kodlama Standartları

Konu
Kural
Tip güvenliği
Çekirdekte mypy strict ve TypeScript strict. Any yalnızca gerekçeli istisnadır.
Hata modeli
HustlerError hiyerarşisi: TransientError (yeniden denenebilir), PermanentError, UserActionRequired, ExternalServiceError. Sessiz except yasaktır; hatalar sınırda Problem Details'e çevrilir.
Asenkron
Event loop'ta bloklayıcı çağrı yok; her ağ çağrısında zaman aşımı; her uzun görevde iptal desteği; sahipsiz (fire-and-forget) görev yok; yapılandırılmış eşzamanlılık (TaskGroup/gather + Semaphore).
CPU bağlı çıkarım
Yerel model ve Whisper gibi CPU bağlı çıkarım event loop dışında çalışır: asyncio.to_thread yalnızca GIL'i bırakan native kütüphanelerde, aksi halde ProcessPoolExecutor. Model süreç başına bir kez yüklenir. Eşzamanlılık CPU bütçesine bağlıdır (Whisper ile paylaşılan semafor); API modundaki 5-8 eşzamanlılık yerel modda geçerli değildir.
Port ve adapter
YouTubePort, LLMPort, TTSPort, TranscriberPort, RendererPort. Her port için gerçek, sahte ve kayıtlı (cassette) uygulama bulunur.
Ayarlar ve sırlar
Ayarlar pydantic-settings ile; sırlar yalnızca Windows Credential Manager'da; kodda ve günlükte anahtar yok.
Zaman ve sayılar
Süreler tam sayı kare veya milisaniye; kayan noktalı süre birikimi yok. Token ve maliyet tam sayı birimde tutulur.
Dosya ve yollar
pathlib; Windows uzun yol ve Unicode testleri; kullanıcı girdisinden yol üretiminde normalizasyon.
Prompt yönetimi
Prompt'lar prompts/ altında sürümlü dosyalardır, kodda gömülü değildir; değişiklik eval setini çalıştırmayı gerektirir.
Yorum ve dokümantasyon
Yorum "neden"i anlatır. Genel API'ler docstring taşır. Mimari değişiklikler ADR ile kayıt altına alınır.
Bağımlılık ekleme
Gerekçe, lisans ve bakım durumu ADR notuyla kaydedilir; yeni bağımlılık varsayılan olarak reddedilir.
Öz-inceleme
Tek geliştirici için PR şablonu kontrol listesi zorunludur (bkz. Bölüm 12).

# 6. Kodlama Yol Haritası

Kilometre taşları ürün fazlarına bağlıdır ve bir kilometre taşı çıkış kriterini karşılamadan kapanmaz. Süreler tahmindir.
6.1 Çizelge (14 hafta)
Kilometre taşı
H1
H2
H3
H4
H5
H6
H7
H8
H9
H10
H11
H12
H13
H14
M0 İskelet
M1 Faz 0 Paketi
M2 Veri Motoru
M3 Transkript/Analiz
M4 Senaryo Motoru
M5 Ses ve Altyazı
M6 Şablon/Derleyici/Render
M7 Arayüz
M8 Sertleştirme
Toplam süre ürün dokümanındaki 12 haftadan 2 hafta uzundur. Fark bilinçli bir yatırımdır: iskelet, CI ve sertleştirme. M6 en belirsiz kilometre taşıdır (3-4 hafta); toplam tahmin için yaklaşık ±%30 belirsizlik varsayılmalıdır.
M0: Yürüyen İskelet
Süre: 4-5 gün  |  Ürün fazı: F0
ID
Görev
Kabul ölçütü
K-001
Monorepo, kilit dosyaları, just görevleri (dev, check, test, gen)
just check tek komutla lint + tip + test çalıştırır
K-002
ruff, mypy strict, ESLint/Prettier, rustfmt/clippy, pre-commit, gitleaks
Hatalı commit engellenir
K-003
CI hattı (Windows): lint → tip → birim; sözleşme denetimi K-004 ile eklenir
Boş projede yeşil
K-004
hustler.contracts, JSON Schema ve TypeScript tipi üretimi
Şema değişince üretilen dosya farkı CI'ı kırar
K-005
FastAPI iskeleti: /health, oturum belirteci, Problem Details, SSE
Entegrasyon testi geçer
K-006
Tauri 2 kabuğu: sidecar başlatma, sağlık yoklaması, Job Object ile kapanış; servis adresi ve belirteci yalnızca Rust'ta tutulur
Zorla kapatmada yetim süreç yok; arayüz belleğinde port veya belirteç yok
K-007
structlog, run_id, Timer ve RunEvent modeli
Adım süresi veritabanına yazılır
K-008
SQLite katmanı: WAL PRAGMA'ları, auto_vacuum=INCREMENTAL (veritabanı oluşturulurken), WriterQueue (bakım işi türüyle), ReaderPool, göç çalıştırıcı
1 yazıcı + 5 okuyucu stres testinde 0 kilit hatası
K-009
hustler doctor: ffmpeg, WebView2, GPU/CUDA, disk, veritabanı ve runs/ boyutu, API anahtarları
Eksikleri ve büyüme uyarılarını tek raporda listeler
K-010
Tauri IPC köprüsü (önkoşul: K-005, K-006): genel proxy komutu, OpenAPI'den üretilen rota izin listesi, SSE → Tauri Channel akışı, istek boyutu ve süre sınırı; üretilmiş TypeScript istemcisinin taşıması invoke olur
Köprü sözleşme testi geçer; izin listesi dışı rota reddedilir; arayüzde doğrudan ağ çağrısı lint ile engellenir
Çıkış kriteri
Arayüzdeki bir düğme Tauri invoke ile sidecar'ı çağırır (arayüz doğrudan ağ çağrısı yapmaz), sonuç veritabanına yazılır ve olay Tauri Channel ile arayüze döner; CI yeşildir.
M1: Faz 0 Doğrulama Paketi
Süre: 4-5 gün  |  Ürün fazı: F0  |  Konum: tools/
ID
Görev
Kabul ölçütü
K-101
T0-1 ve T0-2: 5 konu x 20 video, kota ve hata günlüğü, Shorts sınıflandırma doğrulaması
100 video eksiksiz; yanlış sınıflandırma < %10
K-102
T0-3: transkript kapsama ölçümü (altyazı / Whisper)
Kapsama ≥ %90
K-103
T0-4 ve T0-5: şema uyumu koşucusu (30 üretim) ve map-reduce A/B kıyas aracı
İlk denemede ≥ %95; 2 denemede %100; maliyet baz çizgisi
K-104
T0-6 ve T0-7: eşzamanlılık stres testi ve yavaş-kopyalama simülatörü
Kilit hatası 0; çökme 0
K-105
T0-8: FFmpeg prototipi (8 görsel + ses + ASS), snapshot ve kuru çalıştırma
Nihai < 2 dk; taslak < 10 sn
K-106
T0-10, T0-11, T0-12: Whisper CPU ve devre kesici, asenkron Map (yerel model adayıyla event loop gecikme ölçümü dahil), sidecar paketleme ve taşıma alternatifleri (loopback + belirteç, stdio, named pipe) karşılaştırması
Bütçe içinde; yetim süreç 0; taşıma kararı ADR-010'a işlenir
K-107
Sonuç raporu: her test için ölçüm ve geç/revize kararı; eşiklerin kalibrasyonu
ADR'ler ölçülen değerlerle güncellenir
Çıkış kriteri
Tüm T0 testleri geçmiş veya ilgili mimari karar revize edilmiştir; varsayılan eşikler (5 video, 90 sn, %80 kart) ölçülmüş değerlerle değişmiştir.
M2: Veri Motoru
Süre: 1,5-2 hafta  |  Ürün fazı: F1
ID
Görev
Kabul ölçütü
K-201
YouTubeClient (httpx async): arama, videolar, kanallar, sayfalama, zaman aşımı
Cassette testleri geçer
K-202
Kota izleyici ve SQLite önbellek: TTL ve tablo başına saklama politikası (öneri: video önbelleği kısa, transkript ve özet kartı uzun ömürlü), boyut üst sınırı; aynı sorgu tekrar çekilmez
Kota göstergesi olayı; ikinci çağrı önbellekten; saklama süreleri ayardan
K-203
Shorts sınıflandırıcı: süre eşiği ayardan gelir
Güncel eşik doğrulama testi
K-204
Skorlama (saf fonksiyonlar): log-ölçekli izlenme/abone, saatlik hız, minimum abone eşiği, gizli abone işareti
hypothesis: sınırlı, monoton, NaN yok
K-205
Discovery servisi, hustler discover CLI, Top 20 sıralaması
Top 20 < 30 sn
K-206
Arka plan zamanlayıcısı: kayıtlı konuların yenilenmesi; yenileme ve bakım işleri tek zamanlayıcıda, aktif üretim sürerken ertelenir
Yenileme sırasında arayüz okuması kilitlenmez
K-207
Önbellek bakımı (önkoşul: K-008, K-202): süresi dolan kayıtlar toplu (batch) silinir; wal_checkpoint(TRUNCATE); serbest sayfa oranı eşiği aşılınca ve yeterli boş disk varken VACUUM (yazıcı kuyruğunda, boşta); runs/ klasörü için yaş ve toplam boyut kotası
30 günlük büyüme simülasyonunda veritabanı boyutu platoya oturur; bakım sırasında okuma kilitlenmez; aktif üretimde bakım ertelenir
Çıkış kriteri
Bir konu için sıralı Top 20 listesi < 30 sn; eşzamanlılık stres testinde 0 kilit hatası; 30 günlük büyüme simülasyonunda veritabanı boyutu sınırlı kalır.
M3: Transkript ve Analiz
Süre: 1,5 hafta  |  Ürün fazı: F2
ID
Görev
Kabul ölçütü
K-301
HardwareProfile: GPU/CUDA tespiti, RTF benchmark, kalıcı profil
Profil veritabanında; CUDA yokken doğru işaretlenir
K-302
TranscriptProvider: yerleşik altyazı önceliği, Whisper yedeği, dil algılama
Kapsama ≥ %90
K-303
CircuitBreaker: kapalı/açık/yarı açık durum makinesi; video sayısı, süre ve video uzunluğu bütçesi
Durum makinesi birim ve özellik testleri
K-304
Map A: kanca adayı, kelime sayısı, dakikadaki kelime, CTA kuralları
Deterministik; LLM maliyeti sıfır
K-305
LLMPort + adapter, LlmCall maliyet defteri, token tavanı
Aşımda uyarı olayı
K-306
CpuBudget ve yerel çıkarım altyapısı (önkoşul: K-301): Whisper ve yerel Map modeli için paylaşılan CPU semaforu ve çekirdek bütçesi; InferencePort (API ve yerel uygulama); yerel çıkarım event loop dışında (asyncio.to_thread yalnızca GIL'i bırakan native kütüphanelerde, aksi halde ProcessPoolExecutor); model süreç başına bir kez yüklenir
Çıkarım sırasında event loop gecikmesi eşik altında (öneri: < 100 ms); iptalde çıkarım süreci sonlanır
K-307
Map B çalıştırıcı (önkoşul: K-305, K-306): API modunda asyncio eşzamanlılığı (Semaphore 5-8, zaman aşımı, 429 için geri çekilme + jitter, kısmi başarısızlık); yerel modda eşzamanlılık CpuBudget'a bağlı (varsayılan 1)
API modunda 20 kart < 60 sn; 429 simülasyonu geçer; yerel modda süre ölçülür (bütçeyi aşarsa API modu seçilir)
K-308
Reduce, AnalysisResult; önbellek anahtarı (transkript_hash + prompt_sürümü)
İkinci çalıştırmada LLM çağrısı yok
K-309
Prompt eval harness: sabit veri seti, otomatik puan raporu
Prompt değişikliği raporla kıyaslanır
Çıkış kriteri
20 video için transkript + analiz < 3 dk; üretim başına maliyet tavanın altında; CUDA kapalıyken devre kesici doğru tetiklenir; CPU bağlı çıkarım sırasında event loop yanıt verir.
M4: Senaryo Motoru
Süre: 1 hafta  |  Ürün fazı: F3
ID
Görev
Kabul ölçütü
K-401
ScriptDoc modelleri ve JSON Schema
Sözleşme üretimi CI'da güncel
K-402
TemplateSpec sözleşmesinin yapısal çekirdeği (sahne sayısı, süre aralığı, kelime sınırı) ve 1-2 örnek şablon; render alanları M6'da eklenir
Senaryo üretici örnek şablonla çalışır
K-403
Senaryo üretici (önkoşul: K-402): şablon yapısı prompt'a girdi, şema zorunlu çıktı, doğrulama, ≤ 2 yeniden deneme
Sığmayan senaryo < %10
K-404
Anlamsal doğrulayıcı: sahne sayısı, kelime sınırı, süre toplamı, n-gram kopya taraması
Kopya eşiği aşılınca yeniden üretim
K-405
İddia işaretleyici ve onay durumu; onaysız render engeli domain kuralı olarak uygulanır
Onaysız senaryo render'a giremez (test)
K-406
Görsel prompt derleyici: stil öneki, sahne no, 9:16, toplu kopya çıktısı
Snapshot testi
K-407
Senaryo eval seti: 3 konu x şablon; şema geçerlilik raporu
≥ %95 ilk denemede; %100 yeniden denemeyle
Çıkış kriteri
Şablona sığan, doğrulanmış, iddiaları işaretlenmiş senaryo; eval raporu eşikleri geçiyor.
M5: Ses ve Altyazı
Süre: 1 hafta  |  Ürün fazı: F4
ID
Görev
Kabul ölçütü
K-501
TTSPort + ElevenLabs adapter: zaman aşımı, yeniden deneme, kota
Cassette testleri
K-502
Zaman damgası normalleştirici: kelime zamanları tam sayı ms/kare
Property testi: sıralı, çakışmasız
K-503
AssDocument + SubtitleStyle (kelime vurgusu), font paketleme
ASS snapshot testi
K-504
Ses profili yönetimi ve önbellek (aynı metin, aynı dosya)
İkinci istekte API çağrısı yok
K-505
Timeline / TimeCode çekirdeği (tam sayı kare), ses süresi girişi ve sahne süresi uyarlaması
Property testleri: toplam süre = ses süresi ± 1 kare, kayma yok
Çıkış kriteri
Onaydan sese ≤ 2 dk; altyazı senkronu hatasız.
M6: Şablon, Derleyici, Render ve Assets
Süre: 3-4 hafta (en belirsiz kilometre taşı)  |  Ürün fazı: F5
ID
Görev
Kabul ölçütü
K-601
TemplateSpec'i render alanlarıyla genişlet (M4'teki çekirdeğin üzerine), sürümlü şema, 6-7 şablon dosyası
Şema doğrulaması geçer
K-602
Timeline'ı derleyiciye bağla (M5'teki çekirdek): sahne kare aralıkları → SceneClip ve geçiş süreleri
Derlenen grafta toplam süre = ses süresi ± 1 kare
K-603
Filter, FilterChain, FilterGraph, LabelAllocator, EscapeUtil (saf sınıflar) ve kuru çalıştırma test yardımcısı assert_compiles(graph): derlenen graf sentetik girdilerle (lavfi kaynakları) ffmpeg -f null - ile çalıştırılır
Elle string birleştirme yok (lint kuralı); zorunlu: derleme yapan her test assert_compiles kullanır; kaçış matrisi (iki nokta, virgül, tırnak, Windows yolu, Unicode) kuru çalıştırmadan geçer
K-604
SceneClipBuilder (scale/crop/zoompan/fps) ve hareket kayıt defteri
Snapshot testleri
K-605
TransitionPlanner (xfade ofset) ve AudioMixer
Ofset hesabı birim testli
K-606
GraphValidator, Profile (Draft/Final), derleyici-şema sürüm eşleşmesi; tüm şablon x profil matrisi kuru çalıştırılır
Kopuk etiket ve süre tutarsızlığı yakalanır; matrisin tamamı kuru çalıştırmadan geçer (CI kapısı K4)
K-607
FFmpegRunner: progress ayrıştırma, zaman aşımı, iptal, hata ayrıştırma
İptalde alt süreç ölür
K-608
Altın dosya ve snapshot altyapısı; her şablon için referans render
Kare farkı eşiği CI'da
K-609
Assets: izleme durum makinesi (aday → kararlılık → doğrulama → kopya)
Yavaş-kopyalama testinde çökme 0
K-610
Slot eşleme, oran ve eksik dosya uyarıları
Yanlış oranda net uyarı
K-611
Taslak önizleme akışı
Taslak < 10 sn; nihai < 2 dk
Çıkış kriteri
Bir senaryo, ses ve görsel seti klasöre bırakıldığında otomatik yerleşir; taslak < 10 sn, nihai render < 2 dk; kuru çalıştırma, altın dosya ve kararlılık testleri geçer.
M7: Arayüz ve Süreç Yönetimi
Süre: 2 hafta  |  Ürün fazı: F6
ID
Görev
Kabul ölçütü
K-701
Tasarım sistemi (renk/aralık tokenları, bileşenler), koyu tema
Bileşen testleri
K-702
Akış ekranları: Konu → Top 20 → Senaryo → Ses → Görseller → Önizleme → Render
Ana akış e2e testi; arayüz kodunda doğrudan ağ çağrısı yok
K-703
Olay istemcisi (Tauri Channel üzerinden), ilerleme çubuğu, iptal, Problem Details hata gösterimi
Hata türleri arayüzde eşlenir; bağlantı kopmasında yeniden abone olur
K-704
Senaryo editörü ve iddia onay paneli
Onaysız render düğmesi kapalı
K-705
Tek tık toplu prompt kopyalama ekranı
Kopya içeriği snapshot testli
K-706
Şablon yöneticisi: kategori, klonla, içe/dışa aktar
Şema doğrulamalı
K-707
Süre paneli: 15 dk hedefine göre durum
Timer olaylarından beslenir
K-708
Supervisor tamamlama: yeniden başlatma politikası, kapanış, yetim temizliği
Zorla kapatma senaryoları
K-709
Arayüz güvenlik e2e testi: doğrudan ağ çağrısı CSP ile engellenir, izin listesi dışı komut reddedilir
Test yeşil; ihlal denemesi günlüğe düşer
Çıkış kriteri
Yeni konu akışı yönergesiz tamamlanır; render sırasında arayüz donmaz; yetim süreç 0; arayüz hiçbir ağ çağrısı yapmaz.
M8: Sertleştirme ve Yayın
Süre: 1,5-2 hafta  |  Ürün fazı: F7
ID
Görev
Kabul ölçütü
K-801
Kurulum paketi (Tauri bundler), WebView2 bootstrapper, temiz makine testi
Temiz VM'de kurulum ve çalıştırma
K-802
Yedekleme/geri yükleme (SQLite backup API; önbellek tabloları hariç), proje kurtarma
Çökme sonrası devam testi
K-803
Tanılama paketi: günlükler, doctor raporu, sürümler (zip)
Tek komutla üretilir
K-804
Performans bütçesi CI kapısı (tools/bench)
Regresyon derlemeyi kırar
K-805
Güvenlik gözden geçirme: Tauri izinleri, CSP, IPC izin listesi, bağımlılık ve lisans taraması
Rapor ve açık madde 0
K-806
yt-dlp güncelleme politikası ve bozulma tespiti (kanarya testi)
Bozulmada net uyarı, hat durmaz
K-807
5 kronometreli üretim, CHANGELOG, v1.0 etiketi
Medyan ≤ 15 dk
Çıkış kriteri
Temiz makinede kurulup uçtan uca 15 dk içinde Shorts üretilir; tüm kalite kapıları yeşildir.

## 6.2 Kilometre Taşı Sıralaması ve Bağımlılıklar

Kural: Bir kilometre taşı, önkoşulu olan kilometre taşlarının çıkış kriteri geçilmeden başlamaz. Tek planlı çakışma M2 ile M3 arasındadır: M3, M2'nin K-205'i bitince başlayabilir; K-206 ve K-207 M3 ile paralel yürür ve M3 kapanmadan doğrulanır.
Kilometre taşı
Önkoşul
Devrettiği çıktı
Kapı
M0
-
İskelet, CI, IPC köprüsü, veritabanı katmanı
K1-K3 yeşil
M1
M0
Ölçülmüş eşikler, mimari kararların doğrulanması
T0 raporu
M2
M0 (K-008, K-010), M1 (T0-1, T0-2, T0-6)
Top 20 servisi, önbellek ve bakım
Top 20 < 30 sn; büyüme simülasyonu
M3
M2 (K-205), M1 (T0-3, T0-10, T0-11)
Analiz sonucu, CpuBudget, maliyet defteri
20 video < 3 dk
M4
M3
Doğrulanmış senaryo, TemplateSpec çekirdeği
Eval eşikleri
M5
M4
Ses, altyazı, Timeline çekirdeği
≤ 2 dk; senkron
M6
M5, M1 (T0-8)
Derleyici, render, assets
Render bütçesi; kuru çalıştırma (K4)
M7
M6, M0 (K-010)
Tam arayüz
Yönergesiz akış; güvenlik e2e
M8
M7
Kurulum paketi ve v1.0
Yayın kapısı

## 6.3 Sonraki sürümler

Sürüm
Kodlama işi
v1.5
Yayın sonrası performans girişi (tutma, izlenme), şablon ve kanca türü başına raporlama
v2.0
TrendSourcePort üzerinden TikTok adaptörü (kırılgan kabul edilir, özellik bayrağı arkasında), ekran yazısı için OCR, müzik kütüphanesi

# 7. Kalite Kapıları ve Test Mühendisliği


## 7.1 Kapılar

Kapı
Ne zaman
Eşik
Pre-commit
Her commit
ruff, format, ESLint, gitleaks, hızlı tip denetimi
K1: Lint ve tip
Her push
0 hata (mypy strict, tsc strict, clippy)
K2: Birim ve özellik
Her push
Tümü geçer; çekirdek modüllerde dal kapsamı ≥ %90, genel ≥ %75 (öneri)
K3: Sözleşme ve entegrasyon
Her push
Cassette ve sahte servis testleri; üretilen şemalar güncel
K4: Kuru çalıştırma ve altın render
Her push (şablon/derleyici değişince)
Derlenen tüm graflar ffmpeg -f null ile geçer (zorunlu); snapshot ve kare farkı eşiği
K5: Performans bütçesi
Gece ve sürüm öncesi
Bütçeye göre %20'den fazla regresyon derlemeyi kırar (öneri)
K6: Güvenlik ve lisans
Her push ve haftalık
Açık bağımlılık zafiyeti, sızmış sır, uyumsuz lisans yok
Yerel GPU kapısı
Sürüm öncesi, elle
@gpu işaretli testler CUDA makinesinde çalışır
Yayın kapısı
Sürüm
Temiz VM kurulumu + 5 kronometreli üretim

## 7.2 Test türleri

Tür
Hedef
Not
Birim
Saf mantık: skor, zamanlama, doğrulayıcılar
Hızlı, ağ yok
Özellik tabanlı
Skor sınırları, Timeline toplamı, graf bağlantıları, dosya durum makinesi
hypothesis
Snapshot
Derlenen filtergraph, ASS, prompt derleyici çıktısı
Değişiklik bilinçli onaylanır
Sözleşme (cassette)
Dış API yanıt biçimleri
Kayıtlar gözden geçirilerek yenilenir
Entegrasyon
Sahte servislerle modül zincirleri
Sidecar dahil
Altın render
Şablon çıktılarının kare karşılaştırması
FFmpeg sürümü sabit
Kuru çalıştırma
Derlenen her filter_complex, sentetik girdilerle ffmpeg -f null
Söz dizimini ve bağlantıyı doğrular; görsel doğruluğu altın render doğrular
Olay döngüsü gecikmesi
CPU bağlı çıkarım sırasında event loop gecikmesi
Yerel model ve Whisper modları
Büyüme simülasyonu
30 günlük sentetik kullanımla veritabanı ve runs/ boyutu
Bakım görevinin etkisini ölçer
Köprü güvenliği
İzin listesi dışı rota reddi, CSP ihlali, port/belirteç sızıntısı yok
Sahte sidecar + e2e
Kaos / hata enjeksiyonu
API kesintisi, 429, disk dolu, yarım dosya, süreç öldürme
Dayanıklılık kanıtı
Prompt eval
Şema geçerliliği, kopya oranı, kalite puanı
Prompt değişiminde zorunlu
Performans
Bütçe tablosundaki ölçümler
tools/bench
e2e
Konu → render ana akışı
Sahte dış servislerle

# 8. Gözlemlenebilirlik ve Tanılama

Yapılandırılmış log: JSON; her satırda run_id, adım, modül. Sırlar maskelenir.
Çalıştırma klasörü: Her üretim runs/run_id altında senaryo JSON'unu, prompt'ları, LLM çağrı özetini, FFmpeg komutunu ve günlüğünü saklar.
Yeniden oynatma: hustler replay run_id, kayıtlı LLM ve TTS yanıtlarıyla aynı çalıştırmayı deterministik tekrarlar; hata ayıklama ve regresyon için kullanılır.
Metrikler: Adım süresi, LLM maliyeti, kota, hata oranı, devre kesici tetiklenmesi süre panelinde görünür.
Uyarılar: Kota %80, maliyet tavanı, devre kesici açık, kararsız dosya, sidecar yeniden başlatma.
Tanılama paketi: Tek komutla günlükler, doctor raporu ve sürüm bilgisi zip olarak toplanır.

# 9. Güvenlik ve Tedarik Zinciri

Alan
Kural
Sırlar
Credential Manager; gitleaks kancası; günlüklerde maskeleme
Tauri
Asgari izin listesi (capabilities); sıkı CSP (connect-src ile arayüzden ağ çağrısı yok); IPC yalnızca tanımlı köprü komutlarına açık
IPC köprüsü
Rota izin listesi OpenAPI'den üretilir; istek boyutu ve süre sınırı; izin listesi dışı rota reddedilir; port ve belirteç yalnızca Rust'ta
Yerel servis
Yalnızca 127.0.0.1, dinamik port, oturum belirteci; CORS kapalı
Bağımlılıklar
Kilit dosyaları, düzenli pip-audit / pnpm audit / cargo audit; yeni bağımlılık için gerekçe ve lisans notu
Dış araçlar
yt-dlp ve FFmpeg sürümleri sabitlenir; güncellemeler kanarya testinden sonra alınır; FFmpeg derleme lisansı kaydedilir
Girdi güvenliği
Dosya yolu normalizasyonu, görsel decode doğrulaması, boyut sınırları
Platform şartları
Kullanım şartı değişiklikleri sürüm başına gözden geçirilir; hesap ayrımı sürdürülür (ürün dokümanı Bölüm 11)

# 10. Sürüm ve Geliştirme Akışı

Dal stratejisi: Trunk-based; kısa ömürlü dallar; ana dal her zaman yeşil.
Commit ve sürüm: Conventional Commits, SemVer, CHANGELOG. Kilometre taşı sonunda etiket.
Özellik bayrakları: Tamamlanmamış veya kırılgan özellikler (ör. TikTok) bayrak arkasında.
Göç politikası: Veritabanı göçlerinden önce yedek; geri alma yolu; şablon şema sürümü ile derleyici sürümü eşleşir.
ADR: Karar değişikliği yeni ADR ile yapılır; eski ADR silinmez, geçersiz kılınır.

# 11. Performans Bütçeleri

Aşağıdaki değerler ürün dokümanındaki KPI'lardan gelir ve tools/bench ile otomatik ölçülür. Faz 0 sonucunda kalibre edilir.
Ölçüm
Bütçe
Nerede ölçülür
Uygulama açılışı
< 3 sn
e2e / bench
Top 20 listesi
< 30 sn
discovery bench (sahte ve gerçek)
Map aşaması (20 kart)
< 60 sn (tahmin)
analyze bench (sahte servis)
Transkript + analiz
< 3 dk
entegrasyon bench
Onaydan sese
≤ 2 dk
voice bench
Taslak önizleme
< 10 sn
render bench
Nihai render (30-45 sn)
< 2 dk
render bench, donanım profiliyle
DB kilit hatası
0
stres testi
Event loop gecikmesi (CPU bağlı çıkarım sırasında)
< 100 ms (öneri)
analyze ve transcribe bench
IPC köprüsü ek gecikmesi
Küçük ve ölçülür (bütçe M0'da belirlenir)
e2e / bench
Veritabanı boyutu
Bakım sonrası plato (eşik M2'de belirlenir)
büyüme simülasyonu
Bakım görevi
Aktif üretimi bekletmez (ertelenir); süre kaydedilir
storage bench
Uçtan uca üretim
≤ 15 dk (medyan)
hustler run, Timer

# 12. Kritik Yol, Riskler ve Tamamlanma Tanımı


## 12.1 Kritik yol

K-006 (sidecar) → K-010 (IPC köprüsü) → K-008 (veritabanı) → K-201 (YouTube) → K-302 (transkript) → K-306, K-307 (CPU bütçesi ve Map) → K-403 (senaryo) → K-505 (Timeline) → K-603…K-607 (derleyici ve runner) → K-702 (akış ekranları). Bu zincirdeki gecikme bitiş tarihini doğrudan kaydırır.

## 12.2 Kodlama riskleri

Risk
Önlem
Filtergraph derleyici kapsamı büyür
Kapsam T0-8 sonucunda dondurulur; yeni hareket/geçiş ancak kayıt defteriyle ve testle eklenir
Python sidecar paketleme (Whisper bağımlılıkları) sorun çıkarır
M1'de prototip (T0-12); sorun varsa erken karar
yt-dlp veya altyazı erişimi bozulur
Adapter arkasında; kanarya testi; Whisper yedeği
Prompt kayması (kalite düşüşü)
Sürümlü prompt'lar, eval seti, karşılaştırmalı rapor
Kapsam kayması (editöre dönüşme)
MoSCoW disiplini; ürün dokümanı Bölüm 3 kapsam matrisi
Rust bilgisi darboğazı
Kabuk ince tutulur; hazır Tauri eklentileri tercih edilir
IPC köprüsü Rust kodunu şişirir
Genel proxy ve OpenAPI'den üretilen rota izin listesi; endpoint başına komut yok; köprü sınırı ADR ile korunur
Yerel model CPU'yu kilitler
CpuBudget, süreç izolasyonu, event loop gecikme testi; bütçe aşılırsa API modu
Önbellek ve runs/ kontrolsüz büyür
Bakım görevi (K-207), kotalar, doctor uyarısı
Tahmin belirsizliği (özellikle M6)
Her kilometre taşı sonunda gerçek süreyle yeniden planlama

## 12.3 Tamamlanma tanımı (görev ve PR)

Tip denetimi ve lint temiz; yeni kod için testler yazıldı ve geçiyor.
Sözleşme değiştiyse üretilen şema ve tipler güncel.
Hata yolları ve zaman aşımı düşünüldü; log ve olay eklendi.
Performans bütçesi etkilendiyse bench çalıştırıldı.
Mimari etki varsa ADR yazıldı veya güncellendi.
Kullanıcıya görünen davranış değiştiyse CHANGELOG ve gerekiyorsa belge güncellendi.
Ek A. hustler CLI Komut Seti
Komut
İşlev
Kilometre taşı
hustler doctor
Ortam ve bağımlılık denetimi
M0
hustler discover konu
Top 20 listesi ve skorlar
M2
hustler transcribe run_id
Transkript çıkarma (devre kesicili)
M3
hustler analyze run_id
Map-Reduce analiz
M3
hustler script run_id --template t
Senaryo ve görsel prompt'ları
M4
hustler voice run_id
Ses ve altyazı
M5
hustler render run_id --profile draft|final
Taslak veya nihai render
M6
hustler run konu --template t
Uçtan uca akış, adım süreleri
M6
hustler replay run_id
Kayıtlı yanıtlarla deterministik yeniden oynatma
M6-M8
hustler bench
Performans bütçesi ölçümü
M8
hustler gen
Şema ve TypeScript tipi üretimi
M0
Ek B. İlk 10 Günlük Görev Listesi
Depoyu kur; uv, pnpm, cargo kilit dosyaları ve just görevleri (K-001).
Lint, tip, pre-commit ve gitleaks kancaları; CI hattının ilk yeşil çalışması (K-002, K-003).
hustler.contracts ve şema/TypeScript üretimi (K-004).
FastAPI iskeleti ve Tauri sidecar bağlantısı; Job Object ile kapanış (K-005, K-006).
SQLite WAL katmanı (auto_vacuum dahil) ve stres testi (K-008); log ve Timer (K-007).
IPC köprüsü (K-010) ve hustler doctor (K-009); yürüyen iskelet demosu.
Faz 0: YouTube ve transkript scriptleri (K-101, K-102).
Faz 0: şema uyumu ve map-reduce A/B (K-103).
Faz 0: FFmpeg prototipi ve Whisper CPU benchmark (K-105, K-106).
Faz 0 sonuç raporu ve eşik kalibrasyonu (K-107).
Ek C. Sürüm 1.1 Düzeltme İzlenebilirliği
#
Bulgu
Değerlendirme
Uygulandığı yer
1
Tauri IPC
Kabul, uyarlanarak. Arayüz yalnızca invoke kullanır. Rust ile Python arasında 127.0.0.1 + belirteç bağlantısı kalır (port ve belirteç arayüze verilmez); SSE, Tauri Channel ile iletilir. Köprü genel proxy olarak tutulur.
Bölüm 2, 4.2, 4.3, 5, 9; K-006, K-010, K-703, K-709
2
CPU bağlı model
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
