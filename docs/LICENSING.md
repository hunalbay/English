# Lisans anahtarları (program sahibi için)

English Master deneme sürümü, davetle verilen ücretsiz lisans anahtarlarıyla çalışır.
Bu belge anahtarların nasıl üretildiğini ve programın bunları nasıl doğruladığını anlatır.

## Nasıl çalışır?

1. Kullanıcı programı kurup açar. Lisans yoksa yalnızca **Lisans** ve **Geri bildirim** sayfaları açılır.
   Lisans sayfasında o bilgisayara özel bir **bilgisayar kodu** görünür, ör. `7KQ2-M9XA-P4TD-WR3H`.
2. Kullanıcı bu kodu size gönderir (e-posta, WhatsApp…).
3. Siz **lisans aracıyla** o kod için, kişinin adı ve sizin belirlediğiniz bitiş tarihiyle bir anahtar üretirsiniz.
4. Anahtarı kullanıcıya gönderirsiniz; o da Lisans sayfasına yapıştırır. Program bundan sonra internetsiz çalışır.

Teknik olarak:

- Anahtar, sizin bilgisayarınızdaki **gizli anahtarla** (Ed25519) imzalanır. Programın içinde yalnızca imzayı
  doğrulayan **açık anahtar** vardır. Bu yüzden başkası sahte anahtar üretemez, anahtardaki tarihi ya da adı değiştiremez.
- Anahtar bilgisayar koduna bağlıdır; başka bir bilgisayarda çalışmaz (anahtar dosyası kopyalansa bile).
- Bilgisayar kodu, Windows'un kurulumda ürettiği bilgisayar kimliğinden (MachineGuid) türetilir ve geri çevrilemez.
  Program kaldırılıp yeniden kurulunca **değişmez**; Windows yeniden kurulursa **değişir** (yeni anahtar gerekir).
- Anahtar, bitiş tarihinin **sonuna kadar** (o gün dâhil) geçerlidir. Süre dolunca program lisans ekranına döner;
  kullanıcının çalışmaları silinmez, yeni anahtarla kaldığı yerden devam eder.
- Program bilgisayarın tarihinin geri alındığını (2 günden fazla) fark ederse lisansı geçici olarak kabul etmez.
- Hiçbir bilgi internete gönderilmez; IP adresi kullanılmaz, kayıt tutulmaz.

## Sınırlar (bilmeniz gerekenler)

- **Verilen bir anahtar geri alınamaz.** Bu yüzden bitiş tarihini ihtiyacınıza göre seçin; süre dolunca yenisini verirsiniz.
- Program kullanıcının bilgisayarında çalışır. Kararlı ve bilgili biri programı değiştirerek lisans denetimini
  atlatabilir. Bu yöntem anahtarın paylaşılmasını ve sahte anahtar üretilmesini önler; tam koruma sağlamaz.
- Gizli anahtarınızı kaybederseniz yeni anahtar üretemezsiniz (yeni bir anahtar çifti oluşturup programın yeni
  sürümünü dağıtmanız gerekir; eski anahtarlar yeni sürümde çalışmaz). **Yedek alın.**

## İlk kurulum (bir kez)

1. Lisans aracını alın: GitHub'da **Actions → Windows paketi** iş akışının yapıtlarından
   `EnglishMaster-LisansAraci-<sürüm>` (ya da kendi bilgisayarınızda `scripts\build_windows.ps1` →
   `dist\tool\EnglishMaster-LisansAraci.exe`). Python kuruluysa `python scripts\license_tool.py` da olur.
2. Aracı çalıştırın (çift tıklayın) ve **1) Anahtar çifti oluştur**'u seçin.
   - Gizli anahtar `C:\Users\<siz>\EnglishMaster-Lisans\private_key.pem` dosyasına yazılır.
   - Ekranda `em-pub-1:...` ile başlayan **açık anahtar** görünür (aynı klasörde `public_key.txt`).
3. **Gizli anahtarı yedekleyin:** `EnglishMaster-Lisans` klasörünü bir USB belleğe ya da güvendiğiniz bir yere kopyalayın.
   Bu dosyayı kimseyle paylaşmayın, e-postayla göndermeyin, GitHub'a koymayın.
4. **Açık anahtarı programa ekleyin:** `em-pub-1:...` satırını geliştiriciye iletin (paylaşmak güvenlidir) ya da
   kendiniz `app/core/license_keys.py` dosyasındaki listeye yazın:

   ```python
   PUBLIC_KEYS: tuple[str, ...] = ("em-pub-1:....",)
   ```

5. Programın yeni sürümünü üretin (sürüm etiketi `v*` ya da iş akışını elle çalıştırın). Bu sürümden itibaren
   programınız yalnızca sizin ürettiğiniz anahtarları kabul eder.

Açık anahtar eklenmemiş bir program kopyası hiçbir anahtarı kabul etmez ve "yapılandırılmamış" uyarısı gösterir.

## Anahtar üretmek

Aracı çalıştırın → **2) Lisans anahtarı üret**:

```
Bilgisayar kodu (ör. 7KQ2-M9XA-P4TD-WR3H): A4GQ-MZUI-XZOU-57Y6
Kişinin adı: Ayşe Yılmaz
Bitiş tarihi (GG.AA.YYYY): 01.03.2027
```

Araç anahtarı ekrana yazar ve ayrıca `EnglishMaster-Lisans\anahtarlar\` klasörüne bir metin dosyası olarak kaydeder.
Bu dosyanın içeriğini kullanıcıya gönderin. Bilgisayar kodunda yazım hatası varsa araç bunu fark eder ve anahtar üretmez.

Verdiğiniz bütün anahtarlar `EnglishMaster-Lisans\verilen_lisanslar.csv` dosyasına (Excel'de açılabilir) kaydedilir:
veriliş tarihi, kişi, bilgisayar kodu, bitiş tarihi, lisans numarası.

Komut satırından da kullanılabilir:

```
EnglishMaster-LisansAraci.exe issue --kod A4GQ-MZUI-XZOU-57Y6 --isim "Ayşe Yılmaz" --bitis 01.03.2027
EnglishMaster-LisansAraci.exe check EM1.eyJ...
```

## Yenileme ve bilgisayar değişikliği

- **Süre uzatma:** Aynı bilgisayar kodu için yeni bitiş tarihli bir anahtar üretin. Kullanıcı **Ayarlar → Lisans
  bilgileri** sayfasında yeni anahtarı girer; eski anahtar yedeklenir. Program, bitişe 14 gün kala uyarı gösterir.
- **Yeni bilgisayar / Windows yeniden kurulumu:** Kullanıcı yeni bilgisayar kodunu gönderir, siz yeni anahtar üretirsiniz.
  Eski bilgisayardaki anahtar kendi bitiş tarihine kadar orada çalışmaya devam eder (çevrimdışı yöntemde geri alınamaz).

## Geri bildirim

Programdaki **Geri bildirim** sayfası, kullanıcının yazdığı mesajı (isterse program sürümü, işletim sistemi,
seviye, tamamlanan ders sayısı ve bilgisayar kodunu da ekleyerek) kendi e-posta programında
**onurgulcicek@hotmail.com** adresine hazır bir e-posta olarak açar ya da panoya kopyalar.
Program hiçbir şeyi kendiliğinden göndermez. Adres `app/services/license.py` içindeki `FEEDBACK_EMAIL` değişkenindedir.

## İleride: satış

Satışa geçildiğinde lisans sayfasına satın alma bağlantısı ve isteğe bağlı çevrim içi etkinleştirme
(ör. bir lisans hizmetiyle) eklenebilir. Deneme kullanıcılarının verileri (`user.db`) bu değişiklikten etkilenmez.
