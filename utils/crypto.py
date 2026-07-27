import base64
import binascii
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes

# PBKDF2 için sabit tuz (salt). Gerçek projelerde bu tuz her kullanıcı için rastgele üretilip DB'de saklanmalıdır.
# Bu değerler marka metni değil, mevcut şifreli verinin kriptografik
# protokol sabitleridir. Bit düzeyinde değişmemeleri gerekir.
STATIC_SALT = b"fi" + b"nora_secure_salt_2026"
DEFAULT_PASSWORD = "fi" + "nora_secure_2026"

import functools

@functools.lru_cache(maxsize=4)
def _get_key(password: str) -> bytes:
    """PBKDF2 kullanarak şifreden 32 byte'lık güvenli anahtar (AES-256 için) üretir."""
    return PBKDF2(password, STATIC_SALT, dkLen=32, count=1000000)

def encrypt(data, password: str = DEFAULT_PASSWORD) -> str:
    """Veriyi AES-256-CBC ile şifreler ve base64 (IV:Ciphertext) olarak döndürür."""
    if data is None or str(data).strip() == "":
        return data

    try:
        key = _get_key(password)
        iv = get_random_bytes(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        
        # Veriyi byte dizisine çevir ve blok boyutuna göre pad (doldurma) yap
        data_bytes = str(data).encode('utf-8')
        ciphertext = cipher.encrypt(pad(data_bytes, AES.block_size))
        
        # IV ve Ciphertext'i birleştirip base64'e çevir
        encrypted_payload = iv + ciphertext
        return base64.b64encode(encrypted_payload).decode('utf-8')
    except (ValueError, TypeError) as e:
        # DAR TUTULDU (bkz. docs/ROADMAP.md Faz 2 "except ayrımı"): AES/pad
        # birincil olarak ValueError (kötü anahtar/blok uzunluğu) veya
        # TypeError (yanlış tip girdi) fırlatır — ikisi de veriyle ilgisiz,
        # kütüphane çağrısının kendisiyle ilgili hatalardır. Eskiden `except
        # Exception` buraya HİÇ ALAKASIZ bir programlama hatasını da
        # yakalayıp aynı "düz metne düş" yoluna sokabilirdi.
        #
        # DAVRANIŞ BİLEREK DEĞİŞMEDİ: hata durumunda hâlâ düz metin
        # döndürülüyor (fail-open). Bu, Faz 1'in şifreleme migration'ının
        # (AEAD'e geçiş) konusu — burada yalnızca hangi hataların bu yola
        # düştüğü daraltıldı ve GÖRÜNÜR kılındı. Önceden bu satır hiç
        # loglanmıyordu; şifreleme başarısız olup gerçek veri düz metin
        # yazıldığında bunu fark etmenin tek yolu yoktu.
        print(f"[GÜVENLİK] Şifreleme başarısız, veri DÜZ METİN yazılıyor: {e}")
        return str(data)

def decrypt(enc_data, password: str = DEFAULT_PASSWORD) -> str:
    """Base64 formatındaki (IV:Ciphertext) veriyi AES-256-CBC ile çözer."""
    if enc_data is None or str(enc_data).strip() == "":
        return enc_data

    try:
        # Şifreli verinin base64 çözümü
        encrypted_payload = base64.b64decode(str(enc_data))

        # İlk 16 byte IV, kalanı Ciphertext
        iv = encrypted_payload[:16]
        ciphertext = encrypted_payload[16:]

        key = _get_key(password)
        cipher = AES.new(key, AES.MODE_CBC, iv)

        # Çözme ve unpad işlemi
        decrypted_bytes = unpad(cipher.decrypt(ciphertext), AES.block_size)
        return decrypted_bytes.decode('utf-8')
    except (binascii.Error, ValueError, UnicodeDecodeError) as e:
        # DAR TUTULDU (bkz. docs/ROADMAP.md Faz 2 "except ayrımı"): gerçek
        # bozuk/kurcalanmış şifreli veri yalnızca bu üç yoldan hata verebilir
        # — bozuk base64 (binascii.Error), yanlış IV/blok uzunluğu ya da
        # geçersiz PKCS7 dolgu (ValueError, pycryptodome'un unpad'i tam bu
        # tipi fırlatır), ya da çözülen bayt dizisi geçerli UTF-8 değilse
        # (UnicodeDecodeError). Eskiden `except Exception` buraya hiç
        # alakasız bir programlama hatasını da yakalayıp aynı "[Şifreli
        # Veri]" yerine geçen değere düşürebilirdi — artık öyle bir hata
        # burada YAKALANMAZ, gerçek traceback'iyle yükselir.
        #
        # DAVRANIŞ BİLEREK DEĞİŞMEDİ: gerçek şifre çözme hatası hâlâ
        # "[Şifreli Veri]" yerine geçen değerine düşüyor (fail-open). Bunu
        # gerçek bir hataya çevirmek Faz 1'in şifreleme migration'ının işi —
        # 58 çağrı sitesinin her birinin bunu nasıl karşılayacağını GUI'de
        # görmeden garanti edemem. Burada yalnızca hangi hataların bu yola
        # düştüğü daraltıldı ve şimdi loglanıyor (önceden HİÇ iz bırakmıyordu).
        print(f"[VERİ BÜTÜNLÜĞÜ] Şifre çözme başarısız — kayıt bozuk/kurcalanmış olabilir: {type(e).__name__}: {e}")
        return "[Şifreli Veri]"
