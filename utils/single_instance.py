"""Cross-platform, OS-released exclusive lock for one Archlence profile."""

import os
import sys
from pathlib import Path

# Kilit dosyasının BİRİNCİ baytı saf bir nöbetçidir: kilit hep bu tek bayt
# üzerine konur ve o bayt bir daha ASLA yeniden yazılmaz/kırpılmaz. Teşhis
# için yazdığımız PID, 1. bayttan itibaren SABİT genişlikte bir alana yazılır.
#
# NEDEN BU DÜZEN (Windows CI'da ampirik olarak yakalandı): eski kod baytı
# kilitledikten SONRA `truncate()` çağırıyordu. `msvcrt.locking` bayt ARALIĞI
# kilitler; dosyayı kırpmak kilitli aralığı geçersizleştiriyor ve sonraki
# `LK_UNLCK` şu hatayla düşüyordu:
#
#     PermissionError: [Errno 13] Permission denied   (release() içinde)
#
# Sonucu yalnız gürültü değildi: istisna `__exit__`ten dışarı sızıyor, kilidi
# tutan süreç çıkarken patlıyor ve testlerde kilit bir daha alınamıyordu
# (test_lock_is_recoverable_after_owner_exits). POSIX'te `flock` bayt aralığı
# değil dosyanın tamamını kilitlediği için aynı hata orada hiç görünmüyordu.
_SENTINEL_BYTE = b"\0"
_PID_OFFSET = 1
_PID_FIELD_WIDTH = 32


class AlreadyRunningError(RuntimeError):
    """Another process owns the same profile lock."""


class SingleInstanceLock:
    def __init__(self, lock_path):
        self.path = Path(lock_path)
        self._stream = None

    @staticmethod
    def _lock_sentinel(stream):
        """Dosyanın 0. baytı üzerine bloklamayan özel kilit koyar."""
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock_sentinel(stream):
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def acquire(self):
        if self._stream is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # "a+b" KULLANILMAZ: append modunda yazmalar seek'ten bağımsız olarak
        # hep dosya SONUNA gider, yani PID'i sabit bir ofsete yazmak mümkün
        # olmaz ve nöbetçi bayt farkında olmadan kaydırılabilir.
        descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        stream = os.fdopen(descriptor, "r+b")
        try:
            # Nöbetçi bayt yoksa oluştur — kilit konabilmesi için dosyanın en
            # az 1 bayt olması gerekir.
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(_SENTINEL_BYTE)
                stream.flush()

            self._lock_sentinel(stream)
        except (OSError, BlockingIOError) as exc:
            stream.close()
            raise AlreadyRunningError(
                "Archlence bu kullanıcı profili için zaten çalışıyor."
            ) from exc

        # PID yalnız teşhis içindir. Nöbetçi bayta DOKUNULMAZ ve `truncate`
        # ÇAĞRILMAZ; sabit genişlikli alan sayesinde eski, daha uzun bir PID'in
        # artığı geride kalmaz.
        stream.seek(_PID_OFFSET)
        stream.write(
            str(os.getpid()).encode("ascii").ljust(_PID_FIELD_WIDTH, b" ")
        )
        stream.flush()
        os.fsync(stream.fileno())
        self._stream = stream

    def release(self):
        if self._stream is None:
            return
        stream, self._stream = self._stream, None
        try:
            try:
                self._unlock_sentinel(stream)
            except OSError:
                # Handle'ı KAPATMAK kilidi hem Windows'ta hem POSIX'te işletim
                # sistemi düzeyinde zaten bırakır. Açma hatasını yukarı
                # sızdırmak `__exit__` içinde asıl istisnayı maskeler ve
                # uygulamayı çıkışta çökertir — bu yol bir kez tam olarak böyle
                # kırılmıştı, bir daha kırılmasın.
                pass
        finally:
            stream.close()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()


def notify_already_running(message):
    """Show a native Windows notice before Kivy/SQLite startup."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None, message, "Archlence", 0x00000030
            )
            return
        except (AttributeError, OSError):
            pass
    print(message, file=sys.stderr)
