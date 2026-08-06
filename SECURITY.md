# Security policy

Archlence is in active 0.0.x pre-release development. No release line is
declared stable or long-term supported. Security reports are evaluated against
the latest public pre-release and current `main`; older pre-releases may not
receive a separate fix.

For current guarantees and limitations, read the
[security and reliability status](docs/SECURITY_RELIABILITY_STATUS.md).

## Report a vulnerability privately

Do not open a public issue for a suspected vulnerability. Use a
[private GitHub security advisory](https://github.com/superuser-d0/archlence/security/advisories/new).
No project security email address is currently published.

Include as much of the following as is safe:

- affected Archlence version or commit;
- operating system and installation method;
- vulnerability class and potential impact;
- minimal reproduction steps or proof of concept;
- whether the issue affects confidentiality, integrity, recovery, or financial
  calculations;
- sanitized logs or screenshots;
- any known workaround.

Do not attach a real database, encryption key, recovery package, recovery
password, credentials, or unredacted financial information. Construct a minimal
profile with generated sample data when a database is needed to reproduce the
problem.

## What happens next

The report will be reviewed in the private advisory. The maintainer may ask for
clarification, reproduce the issue, prepare regression tests and a fix, and
coordinate disclosure through the advisory. The project does not promise a
fixed response or release deadline during the pre-release period.

Keep details private until the maintainer confirms that coordinated disclosure
is appropriate. If a report is not a security issue, it can be moved to the
public issue tracker after sensitive details are removed.

## Security boundaries

Archlence reduces exposure by keeping core financial records local, encrypting
sensitive fields at rest, and providing backup and recovery workflows. These
controls do not protect data from an attacker who fully controls the signed-in
operating-system account or the running application process.

Packages are not code-signed. Published SHA-256 checksums detect download
changes but do not replace publisher authentication. Recovery requires matching
key material; losing both the active key and usable recovery material can make
encrypted records unrecoverable.

See [Key management](docs/KEY_MANAGEMENT.md) and
[Backup and recovery](docs/BACKUP_RECOVERY.md) for the detailed contracts.
