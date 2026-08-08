# Security and reliability status

This document is the single current security and reliability summary for the
active 0.0.x pre-release line. Release-specific changes and limitations belong
in `CHANGELOG.md`; dated audit documents describe only the commit they audited
and remain historical baselines.

## Current verified protections

- **Package checks:** the Windows installer and Linux AppImage pass launch
  smoke tests in CI. The Windows workflow also exercises installation,
  previous-release upgrade, profile persistence, and removal.
- **Financial correctness:** dashboard period/30-day metrics and budget totals
  do not count corrupt encrypted records as zero. A shared Decimal policy
  defines fiat, quantity, and percentage boundaries where migration is
  complete.
- **Data protection:** new sensitive values are written only with AEAD. Backup
  validates the database and password-protected recovery key together; restore
  is rollback-safe. The database records which schema generation wrote it, and
  an older build refuses to open a newer one rather than writing to a schema it
  does not understand.
- **Dependency vulnerabilities:** the packaged dependency set is scanned on
  every pull request and the scan blocks. The published SBOM remains the
  authoritative component inventory.
- **External price data:** third-party price results carry source, age, and
  freshness status rather than being presented as guaranteed current values.

## Known limitations

- The 0.0.x line is pre-release and is not recommended as the sole store for
  day-to-day financial records. It is not banking or accounting certification.
- The legacy CBC reader remains deprecated for compatibility with old profiles
  and backups. New data cannot be written in that format.
- Yahoo Finance is the primary price provider. When it returns nothing for a
  symbol, cryptocurrency falls back to CoinGecko and foreign currency to
  Frankfurter (ECB), and the reported source names whichever provider actually
  answered. **BIST equities and gold have no fallback** — no free source for
  them is currently integrated, so those stay on Yahoo Finance alone. A very
  old cache is not presented as a definitively current price.
- Broad exception handlers and `print()` calls remain in UI mixins. CI blocks
  new broad or silent handlers and freezes a decreasing baseline.
- Packages are not code-signed. Windows SmartScreen may warn, and the AppImage
  has no cryptographic signature. SHA-256 checksums and an SBOM are published.
- Windows DPAPI and Linux Secret Service/KWallet integrations exist, with a
  visible permission-restricted file fallback, but packaged keystore and
  recovery behavior still needs broader real-system validation.
- Existing 4-digit credentials are not automatically upgraded to the password
  policy introduced for new or changed credentials.

Losing both the active key and usable recovery material can make encrypted
records unrecoverable. See [Key management](KEY_MANAGEMENT.md) and
[Backup and recovery](BACKUP_RECOVERY.md).
