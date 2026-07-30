"""Typed application errors for security and data-integrity boundaries.

Messages are deliberately metadata-only.  Plaintext, keys, ciphertext and
financial values must never be embedded in these exceptions because callers
may safely include the exception in a production log.
"""


class ArchlenceError(Exception):
    """Base class for expected, user-presentable application failures."""


class EncryptionError(ArchlenceError):
    """Sensitive data could not be encrypted and was not persisted."""


class DecryptionError(ArchlenceError):
    """Encrypted data could not be decoded."""


class IntegrityVerificationError(DecryptionError):
    """Authenticated ciphertext failed integrity verification."""


class KeyUnavailableError(ArchlenceError):
    """The encryption key is missing, corrupt, or cannot be accessed."""


class DataMigrationError(ArchlenceError):
    """A data migration failed and its database transaction was rolled back."""


class FinancialDataIntegrityError(ArchlenceError):
    """A financial result is invalid because a contributing record is unreadable."""

    def __init__(self, table, record_id, field, *, reason=None):
        self.table = str(table)
        self.record_id = record_id
        self.field = str(field)
        self.reason = reason
        super().__init__(
            f"Finansal kayıt doğrulanamadı "
            f"(table={self.table}, id={self.record_id}, field={self.field})."
        )
