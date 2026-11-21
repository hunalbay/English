# Kurulum, güncelleme ve kaldırma

## Sistem gereksinimleri

- Windows 10 ya da 11 (64 bit)
- Yaklaşık 150 MB boş disk alanı
- Güncel bir web tarayıcısı (Edge, Chrome ya da Firefox). Program arayüzünü tarayıcıda açar;
  **internet bağlantısı gerekmez**.

## Kurulum

1. `EnglishMaster-Setup-<sürüm>.exe` dosyasını çalıştırın.
2. Windows "Windows bilgisayarınızı korudu" uyarısı gösterirse **Ek bilgi → Yine de çalıştır**'a
   tıklayın. Bu uyarı, kurulum dosyası ücretli bir kod imzalama sertifikasıyla imzalanmadığı için çıkar.
   İsterseniz dosyanın SHA-256 özetini, yanındaki `.sha256` dosyasıyla karşılaştırabilirsiniz:
   `Get-FileHash .\EnglishMaster-Setup-<sürüm>.exe`
3. Sihirbazdaki adımları izleyin. Yönetici izni gerekmez; program kendi kullanıcı klasörünüze kurulur
   (`%LOCALAPPDATA%\Programs\English Master`). İsterseniz masaüstü kısayolu da eklenir.

## İlk açılış: lisans anahtarı

English Master şu an davetle verilen ücretsiz bir deneme sürümüdür. İlk açılışta **Lisans** sayfası görünür:

1. Sayfadaki **bilgisayar kodunu** (ör. `7KQ2-M9XA-P4TD-WR3H`) **Kodu kopyala** ile kopyalayıp
   onurgulcicek@hotmail.com adresine gönderin.
2. Size yalnızca bu bilgisayarda çalışan, `EM1.` ile başlayan bir lisans anahtarı gönderilir.
3. Anahtarın tamamını Lisans sayfasındaki kutuya yapıştırıp **Lisansı etkinleştir**'e tıklayın.

Bundan sonra internet gerekmez. Lisans bitiş tarihinin sonuna kadar geçerlidir; bitişe 14 gün kala program
uyarır. Süre dolarsa çalışmalarınız silinmez; yeni anahtar girdiğinizde kaldığınız yerden devam edersiniz.
Programı kaldırıp yeniden kurmak lisansı silmez. Windows yeniden kurulursa ya da başka bir bilgisayara geçerseniz
yeni bilgisayar kodu için yeni anahtar istemeniz gerekir.

Görüş, öneri ya da hata bildirimi için menüdeki **Geri bildirim** sayfasını kullanın.

## Programı kullanmak

- **Başlat** menüsünden ya da masaüstü kısayolundan **English Master**'ı açın. Program varsayılan
  tarayıcınızda bir sekme açar.
- Program açıkken saatin yanındaki **sistem tepsisinde** mavi "EM" simgesi görünür. Simgeye tıklayarak
  sekmeyi yeniden açabilir, sağ tıklayıp **Çıkış** ile programı kapatabilirsiniz. Program ayrıca
  **Ayarlar → Programı kapat** ile de kapatılabilir.
- Program açıkken kısayola yeniden tıklarsanız ikinci bir kopya açılmaz; açık olan sekme yeniden gösterilir.
- Program yalnızca bu bilgisayardan erişilebilen yerel bir adreste (`127.0.0.1`) çalışır; ağdaki başka
  cihazlar bağlanamaz. Hiçbir veri internete gönderilmez.

## Verileriniz nerede?

İlerlemeniz, test sonuçlarınız, kelime listeniz ve ayarlarınız şu klasördedir:

```
%LOCALAPPDATA%\EnglishMaster
```

| Dosya / klasör | İçerik |
|---|---|
| `user.db` | Bütün kişisel kayıtlarınız |
| `license.json` | Lisans anahtarınız (yalnızca bu bilgisayarda çalışır) |
| `backups\` | Program her güncellemede verilerinizi değiştirmeden önce buraya yedek alır |
| `logs\` | Hata ayıklama kayıtları (yalnızca bu bilgisayarda kalır) |

Bu klasör program klasöründen ayrıdır; programı kaldırmak ya da güncellemek verilerinizi silmez.
Başka bir bilgisayara taşımak için programı kapatıp `user.db` dosyasını yeni bilgisayardaki aynı klasöre
kopyalayın.

## Güncelleme

Yeni sürümün kurulum dosyasını çalıştırın; eskisinin üzerine kurulur. Kurulumdan önce programı kapatın
(sihirbaz açık olduğunu fark ederse sizi uyarır). İlk açılışta veri dosyanız gerekiyorsa yeni sürüme
uyarlanır; bundan önce `backups\` klasörüne otomatik yedek alınır. Bir sorun çıkarsa yedek
kendiliğinden geri yüklenir.

## Kaldırma

**Ayarlar → Uygulamalar → English Master → Kaldır** ya da Başlat menüsündeki **English Master kaldır**.

Kaldırma sihirbazında **"Kişisel verilerimi de sil"** seçeneği **varsayılan olarak işaretli değildir**:
İşaretlemezseniz ilerlemeniz korunur ve programı yeniden kurduğunuzda kaldığınız yerden devam edersiniz.
Verilerinizi de silmek isterseniz bu kutuyu işaretleyin; silmeden önce ayrıca onay istenir.

## Sorun giderme

| Sorun | Çözüm |
|---|---|
| Tarayıcı açılmadı | Sistem tepsisindeki "EM" simgesine tıklayın. Simge görünmüyorsa veri klasöründeki `instance.json` dosyasında yazan port numarasıyla tarayıcıda `http://127.0.0.1:<port>/` adresini açın. |
| "Kişisel verilerinizin bulunduğu dosya bozuk görünüyor" | Mesajdaki adımları izleyin: programı kapatın, `user.db`'yi başka bir yere taşıyın, `backups\` klasöründeki en yeni dosyayı `user.db` adıyla geri koyun. |
| "Eğitim içeriği bulunamadı / bozuk" | Programı yeniden kurun (verileriniz silinmez). |
| Ses çalmıyor | Bilgisayarın ses düzeyini ve tarayıcı sekmesinin sessize alınmadığını denetleyin. Bir içerikte "ses dosyası yok" yazıyorsa o içerik için kayıt bulunmuyordur. |
| Mikrofon izni sorulmadı | İzin yalnızca telaffuz sayfasında **Kaydet**'e bastığınızda istenir. Daha önce reddettiyseniz tarayıcının adres çubuğundaki kilit simgesinden izni değiştirin. |
