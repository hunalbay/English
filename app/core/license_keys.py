"""Lisans anahtarlarını doğrulayan açık anahtarlar.

Buraya yalnızca AÇIK anahtar yazılır (lisans aracının `init` komutunun çıktısı).
Gizli anahtar hiçbir zaman depoya, GitHub'a ya da programa konmaz.
Birden fazla açık anahtar yazılabilir (anahtar değiştirme döneminde eski
anahtarla verilmiş lisanslar da geçerli kalsın diye).

Liste boşsa program hiçbir lisansı kabul etmez ve lisans ekranında
"bu kopya lisans doğrulaması için yapılandırılmamış" uyarısı gösterir.
"""

PUBLIC_KEYS: tuple[str, ...] = ()
