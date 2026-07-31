# Security and reliability status

This document is the single current security and reliability summary for the
0.0.2 source tree. Dated audit documents describe only the commit they audited
and are archived baselines, not the current status.

## What “stable” means

- **Package and usage stability:** the Windows installer and Linux AppImage
  pass real launch smoke tests in CI; the Windows workflow also verifies
  installation and removal.
- **Financial correctness:** dashboard period/30-day metrics and budget totals
  do not count corrupt encrypted records as zero. A shared Decimal policy
  defines fiat, quantity, and percentage boundaries.
- **Data protection:** new sensitive values are written only with AEAD. Backup
  validates the database and password-protected recovery key together; restore
  is rollback-safe.
- Stable does not mean banking or accounting certification. Third-party price
  data carries source, age, and freshness status.

## Known limitations

- The legacy CBC reader remains deprecated for compatibility with old profiles
  and backups. New data cannot be written in that format.
- Yahoo Finance is the only price provider. A second adapter is planned; a
  very old cache is not presented as a definitively current price.
- Broad exception handlers and `print()` calls remain in UI mixins. CI blocks
  new broad or silent handlers and freezes a decreasing baseline.
- Packages are not code-signed. Windows SmartScreen may warn, and the AppImage
  has no cryptographic signature. SHA-256 checksums and an SBOM are published.
