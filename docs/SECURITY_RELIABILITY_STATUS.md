# Security and reliability status

This document is the single current security and reliability summary for the
active 1.x stable line. Release-specific changes and limitations belong
in `CHANGELOG.md`; dated audit documents describe only the commit they audited
and remain historical baselines.

## Current verified protections

- **Package checks:** the Windows installer and Linux AppImage pass launch
  smoke tests in CI. The Windows workflow also exercises installation,
  previous-release upgrade, profile persistence, and removal. Its frozen EXE
  creates an isolated DPAPI-backed profile that completes a verified
  backup/mutation/restore round trip without producing a raw key file.
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
- **Credentials:** new and changed passwords use the shared strong-password
  policy. A user who successfully authenticates with an older weak credential
  must renew it before reaching financial screens.

## Known limitations

- Stable describes the verified software and recovery scope. It is not banking
  or accounting certification, and verified backups remain the user's
  responsibility.
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
- Windows DPAPI is exercised through the packaged application on Windows CI.
  Linux Secret Service/KWallet integrations exist and have an explicit,
  visible permission-restricted file fallback; desktop keyring availability
  still varies by Linux distribution and session configuration.

Losing both the active key and usable recovery material can make encrypted
records unrecoverable. See [Key management](KEY_MANAGEMENT.md) and
[Backup and recovery](BACKUP_RECOVERY.md).
