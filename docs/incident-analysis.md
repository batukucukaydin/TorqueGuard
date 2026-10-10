# Olay incelemesi — 10 Ekim 2026

## Güncel birincil bulgu

[FIA'nın 8 Ekim soruşturma sonucu](https://api.fia.com/news/fia-concludes-investigation-bahrain-gp-malaysia-formation-lap-software-bug), düşük motor devriyle belirli güç kısıtlı sektörlerin birleşiminde amaçlanandan fazla ve o sektör içinde geri alınamayan güç kaybını bildiriyor. Yazılım öncesinde takım/üretici simülasyonlarında ve Belçika ile Hollanda FP1 seanslarında test edilmiş. Dolayısıyla “test edilmedi” yerine “yapılan testler bu birleşimi yakalayamadı” demek doğru.

FIA zaman çizelgesinde 15:45 askıya alma, 15:50 ilk konfigürasyon düzeltmesinin yayımlanması, 16:03 ek teknik rehberlik ve 16:20 bütün araçların entegrasyonu tamamlaması var. İlk günkü yaklaşık 20 dakika ifadesi toplam entegrasyon süresinin kesin karşılığı değil.

## İlk haberlerin katkısı

[Motorsport, 4 Ekim](https://www.motorsport.com/f1/news/fia-reveals-why-f1-cars-stopped-in-rain-at-bahrain-gp-in-malaysia/10861947/), yağmurda formation lap sırasında concertina ve neredeyse durma sonrasında gücün yeniden devreye giremediğini aktarıyor. [Autosport](https://www.autosport.com/f1/news/how-fia-software-bug-caused-chaos-in-bahrain-gp-in-malaysia-and-the-emergency-fix-that-saved-the-ra/10861989/) ise minisektör etkisini ve recharge yönlendirmesini ilk teknik olasılık olarak tartışıyor. [RACER](https://racer.com/2026/10/04/fia-explains-software-glitch-behind-delayed-bahrain-gp-in-malaysia-start) de düşük grip, düşük hız ve wet ayarları birleşimini aktarıyor.

## Kanıt sınırı

| İddia | Durum |
| --- | --- |
| Düşük RPM + kısıtlı sektörlerde geri alınamayan güç kaybı | FIA soruşturmasıyla destekleniyor |
| Islak formation lap ve aşırı düşük hızın rolü | İlk haberler ve açıklamalarla destekleniyor |
| Gerçek ECU'da `ENERGY_RECOVERY → DEPLOYMENT_DISABLED` geçişi | Açıklanmamış; hipotez |
| ICE torkunun tamamının MGU-K şarja gitmesi | İlk değerlendirmede olasılık; kesin sonuç değil |
| Motor/bataryanın fiziksel arızalı olması | İncelenen kaynaklar bunu göstermiyor; yazılım konfigürasyonu sorunu bildiriyor |
| Hiç test yapılmaması | FIA açıklamasına aykırı |
| Islak koşulların her yerde sabit 250 kW limiti anlamına gelmesi | Fazla genelleme; sektör ve uygulama ayrıntıları gerekiyor |

## Projeye çevirme

TorqueGuard'ın değeri, FIA kodunu tahmin etmekten değil, kontroller arasındaki etkileşimlerin bir sürücü talebini kalıcı olarak engelleyip engellemediğini tekrarlanabilir koşullarda sınamaktan geliyor. MVP'de bilinçli bir circular exit guard hatası kullanılıyor. Referans kontrolcü bu hipotezi düzeltiyor; gerçek yarış hotfix'inin kodu olduğu iddia edilmiyor.

Doğru araştırma sorusu: “Meşru inhibisyonlar ve fiziksel kapasite hesaba katıldığında, sürekli yeniden hareket talebi sonlu sürede torka dönüşüyor mu?” Bu bir bounded-liveness özelliği; rastgele anlık sinyal kombinasyonları yerine durum geçmişi içeren closed-loop yörüngeler gerektiriyor.
