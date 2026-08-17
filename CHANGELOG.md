# Changelog

## [Unreleased]

### Features

- Search now covers transaction descriptions as well as account and category
  names. Descriptions are encrypted, so the filter cannot be pushed into SQL;
  the search decrypts a bounded window of the most recent transactions
  instead. The window is 500 rows, chosen by measurement rather than taste:
  200, 500 and 1000 rows decrypt in 7,3ms, 17,5ms and 34,8ms here, and 500
  stays under a single frame's budget even if a slower machine triples it.
  The cost is explicit — a transaction older than that window will not be
  found by its description — and the search box's empty state now says what
  it searched so the boundary is visible rather than mysterious.
- A write-time search index was **not** built, though it would be faster. It
  puts plaintext-adjacent data back on disk, which defeats the reason the
  descriptions are encrypted, and that is not a change to make without a
  threat review.
- The notification bell works. It lists pending transactions and recurring
  payments falling due within seven days, using the same seven-day rule as
  the "Yaklaşan Ödemeler" card — showing the same data under two different
  thresholds would tell the user two different truths. The data is gathered
  on a background thread, because collecting it decrypts each row.

### UI and accessibility

- The bell icon had no handler at all until this release. That is the same
  defect class as the search bar reported against 0.0.10, and in one respect
  worse: the magnifier was an `MDIcon` and could not receive a click, so it
  never responded, while the bell was a real `MDIconButton` that rippled
  under the finger and then did nothing. A scan of the whole interface found
  it to be the only remaining control in that state.

### Testing and packaging

- The key's user scoping is now pinned by a test. Cross-user DPAPI isolation
  rests on one thing: whether `CryptProtectData` is given
  `CRYPTPROTECT_LOCAL_MACHINE`. With that flag the blob binds to the machine
  and any Windows user on it can decrypt; without it, it binds to the calling
  user. The code passes `dwFlags=0`, and that is now measured behaviourally —
  the real call is intercepted and the flag captured, for both protect and
  unprotect — rather than asserted by reading the source. Verified against a
  known-broken state: setting the flag turns the test red.

  This does **not** replace running the check as a second Windows user, which
  the validation machine cannot do. It proves Windows is being asked for user
  scope, and it means a future change that widens the scope fails loudly
  instead of silently. See Known limitations.

- The tab scrolling gate no longer depends on where cards happen to land. It
  started its synthetic drag at the window centre, which at some densities and
  account layouts fell on an `MDCard`; the card claims the touch, so the gate
  reported a sound build as broken and — worse — stopped distinguishing the
  fix from its absence. The start point is now selected rather than computed:
  candidates inside the card strip are probed against the widget tree with
  `collide_point` until one lands clear of every card, and if none does the
  measurement is reported as skipped rather than failed. Verified by A/B at
  three densities: green with the fix and red without it at 1.0, 1.25 and 1.5,
  where 1.0 previously failed in both directions.

### Known limitations

- **Cross-user DPAPI isolation cannot be run on the validation machine** and
  will stay that way: there is no second Windows account and one will not be
  created. The mechanism behind the claim is now pinned by a test (see Testing
  and packaging), which is a narrower guarantee than an end-to-end run and is
  recorded as such rather than as a verification.
- Multi-monitor behaviour remains unverified for the same class of reason —
  the machine has one display.
- **Description search reaches back 500 transactions, not further.** This is
  the deliberate trade-off described under Features, not an oversight. Account
  and category search is unaffected — those are plain text and filtered in
  SQL.

### Financial correctness and reliability

- The BIST and crypto pickers can find Turkish names again. Both filtered with
  `.lower()`, which does not fold Turkish: measured against the real BIST-100
  list, typing `is bankasi` or `tupras` returned **no results at all**, so
  İş Bankası and Tüpraş were unreachable by name and only findable by ticker.
  The budget category picker had the same class of bug through `.casefold()`.
  All three now share the folding introduced in 0.0.11, so accents and the
  ı/İ/I/i family all compare equal.

## [0.0.11] — 2026-08-17

A single-feature release. The search bar in the home header, which 0.0.10
removed because it had never been connected to anything, is back and now does
what it looks like it does.

### Highlights

- **Search works.** Typing in the home header filters account and category
  names and shows matches inline; tapping an account opens the accounts tab,
  tapping a category opens the settings tab with that category type loaded.
- **The magnifier is a button.** It was an `MDIcon`, which inherits no button
  behaviour and cannot receive a click at all — the literal reason the
  reported control did nothing. It is now an `MDIconButton` and focuses the
  field.
- **Turkish search actually folds Turkish.** `"I".casefold()` gives `"i"` but
  `"ı".casefold()` stays `"ı"`, so typing `ISI` could never find `ısı`; and
  `"İ".casefold()` produces `i` followed by a combining dot, which looks
  identical and does not compare equal. All three now normalise to the same
  key, and accents fold as well, so `sirket` finds `Şirket`.

### Financial correctness and reliability

- No changes. This release does not touch balances, transactions, encryption
  or migrations.

### Performance

- No measured change. Search reads two small tables and filters in SQL; the
  query is debounced by 300ms, following the pattern already used by the
  budget and asset search boxes after both were measured as janky when
  redrawing on every keystroke.
- The 50.000-transaction decrypt cost measured for 0.0.10 is what keeps
  transaction descriptions out of search scope; see Known limitations.

### UI and accessibility

- Results render inline under the header rather than in a dropdown.
  KivyMD's `MDDropdownMenu` is built on a `ModalView` that captures focus, so
  reopening it on each keystroke would have prevented typing a second
  character.
- The results panel occupies no space when there is nothing to show, and its
  rows are removed rather than merely hidden — hiding by height alone leaves
  rows clickable, the same defect class fixed for empty cards in 0.0.10.
- An empty search reports "Sonuç bulunamadı" with a line naming what was
  searched, so the narrow scope is visible rather than surprising.
- The hint text now says what the box actually searches. "Archlence'ta ara..."
  implied everything, and searched nothing.

### Testing and packaging

- 21 unit tests cover the search service, most of them on Turkish folding.
  The suite is 955 tests.
- The folding gate is verified against a known-broken state: removing the
  `ı`→`i` fold turns five tests red, restoring it turns them green.
- `verify_search_bar_visual.py` comes out of the park it was placed in for
  0.0.10 and gets its own XDG directories, so the shared-directory ordering
  dependency that broke the asset dialog gate cannot recur. Its docstring now
  states plainly that it measures how the bar looks and not whether it does
  anything — that gap is why a dead control stayed green for so long.

### Additional issues found and fixed

- The i18n gate caught a real omission during this work: the new hint string
  had no English translation. Fixed rather than worked around, along with the
  three other new strings.

### Known limitations

- **Search does not cover transaction descriptions.** Those fields are
  encrypted, so matching them cannot be pushed into SQL — it means decrypting
  a working set, and a full decrypt of 50.000 rows measures 1,1s. Doing it
  properly needs a choice between a write-time index (which puts
  plaintext-adjacent data back on disk and needs its own threat review), a
  cancellable background worker, or a bounded recent window. The options are
  recorded in `docs/ROADMAP.md` Phase 2 rather than guessed at.
- **The two older search boxes still fold incorrectly.** The category picker
  in the budget dialog and the asset search both still use plain
  `.casefold()`, so they carry the Turkish bug this release fixes elsewhere.
  Moving them onto the shared `normalize()` is queued rather than bundled
  here.
- Cross-user DPAPI isolation and multi-monitor behaviour remain unverified,
  unchanged from 0.0.10 — both blocked by the validation machine having one
  active user account and one monitor.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.11.exe`
- Linux: `Archlence-0.0.11-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.11-sbom.cdx.json`.

## [0.0.10] — 2026-08-17

This release closes the Windows hardware validation round that v0.0.9 left
open. Almost everything it fixes was found by running the packaged
installer on a real Windows machine rather than in CI: tabs that could not be
scrolled at all, cards that reserved screens of blank space for content they
did not have, icons laid out without a width that spilled into the text beside
them, and a second copy of the application that opened an empty black window
before explaining it would not run. The financial changes continue the move to
`Decimal`, where binary floating point had been rounding portfolio values a
kuruş away from the arithmetically correct number.

It remains a **pre-release**, and the version number now says so plainly. This
work was first tagged `v0.1.0` on the reading that dropping the pre-release
label was warranted. It was not: a user found within the hour that the search
control in the home header does nothing and never had, and the release
workflow was marking the build as a pre-release regardless, because it treats
every `0.x` version that way. That tag and its release were deleted before
anyone depended on them and the work was re-cut as `0.0.10`, which is where it
belongs. Nothing about the code changed in the move; only the number and this
paragraph did.

### Highlights

- **The "Kartlarım" tab can be scrolled.** On a real Windows install nothing
  below the heading could be reached — the horizontal card strip is taller
  than the visible area and Kivy offers a touch to the child scroll view
  first, which claimed every drag whether or not it had anywhere to go.
- **The wheel works over lists inside cards.** Kivy's scroll view claims a
  wheel event even when its content fits entirely in view, so over the asset
  history list — anywhere below that card's heading — the wheel did nothing.
- **Empty cards take the space of their message.** Four areas had fixed
  heights of 220, 190, 320 and 400dp, so an empty profile scrolled through
  screens of blank card.
- **A second copy no longer opens a black window.** The single-instance check
  ran after every import in `main.py`, including the one that creates the
  window.
- **Portfolio values round to the arithmetically correct kuruş.** Fifteen
  units priced at 0,045 TL is exactly 0,675 TL; it was reported as 0,67
  because the multiplication ran in binary floating point and never produced
  the half-kuruş the rounding needed to see.

### Financial correctness and reliability

- Deleting an account no longer leaves its recent transactions behind in the
  cached snapshot. The entry was removed under a text key while it had been
  stored under a numeric one, so it never matched. Nothing was displayed
  wrongly — the account leaves the list in the same operation and the screen
  only walks that list — but the snapshot held state that no longer described
  the profile.
- Profit/loss, current value and cost for a portfolio asset are computed in
  `Decimal` and rounded once, at the end, by the shared rounding policy. The
  four steps previously ran in binary floating point: a unit price of 0,045
  bought fifteen times cost 0,675 exactly, but was reported as 0,67 rather
  than 0,68 because the multiplication never produced the half-kuruş the
  rounding needed to see. Displayed numbers can therefore move by one kuruş —
  towards the arithmetically correct value.
- A portfolio row whose price or quantity is not a finite number is now
  reported as unpriceable instead of showing `nan` or `inf` as profit,
  breakeven or total value.
- The portfolio's current value is added up in `Decimal` and rounded once, at
  the point it is handed to the screen. Each position was previously multiplied
  in binary floating point: fifteen units of a coin priced at 0,045 TL is
  exactly 0,675 TL, but showed as 0,67 rather than 0,68. The quantities and
  prices involved are ordinary ones — eight decimals for a crypto amount, six
  for an equity — not extremes.
- A portfolio price that is not a finite number no longer stops the total from
  being calculated. That asset is skipped, as an unpriced one already was,
  instead of leaving the value on screen waiting forever.
- A savings goal that still holds its target no longer falls back to "active"
  after money is withdrawn from it. Whether a goal counts as reached is now
  decided to the kuruş everywhere in the service; one of the three places that
  asks that question compared the raw stored amount instead, so a goal showing
  10,40 / 10,40 could be labelled unfinished.

- Buying an asset now decides whether the account can afford it inside the same
  database transaction that writes the purchase. The check previously ran on a
  separate connection before the transaction opened, so two purchases starting
  at the same moment could both read the same credit-card limit and both pass:
  a card with a 100 TL limit could end up 120 TL in debt. The rule that governs
  spending — account exists, not frozen, credit limit not exceeded — now lives
  in one place and is applied by both the transaction and the asset-purchase
  paths, rather than each carrying its own copy.

- A recurring charge now records the identifier of the transaction it actually
  wrote. The marker read the cursor's last inserted row after the ledger entry
  had already been written through that same cursor, so it stored the ledger
  row's identifier instead — a charge whose transaction was row 1 was filed
  against row 2. Nothing on screen was wrong, because that column is not read
  anywhere yet; what was wrong was the record of where the money came from.

- The recurring charge asks whether the account may spend from inside the
  transaction that writes the charge, using the same cursor, instead of opening
  a second connection while holding the write lock. This is the same rule the
  transaction and asset-purchase paths already follow, and the function it used
  before says in its own documentation that it must not guard a write.

- A recurring payment can no longer be created or repriced with an amount that
  is not a finite, positive number. `nan` and `inf` passed every check, because
  no comparison against them is ever true, and were encrypted and stored. The
  charge itself always refused them, so no money moved; what broke was the
  monthly budget, which read such a row back as valid and then could not add it
  up. Amounts are also stored rounded to the kuruş now, so a subscription shows
  the figure it will actually charge. A row left behind by an older build is
  reported as unreadable rather than silently valid.

- Paying a credit-card debt rejects a non-finite amount at the service boundary.
  `nan` previously reached the first balance update — it was rolled back when
  the following conditional update did not match, so nothing was persisted, but
  the decision belonged before the first write, not after it.

- The one-off cleanup that removes raw card numbers left over from older builds
  now distinguishes a corrupt record from an unavailable encryption key. It
  caught only `ValueError`/`TypeError` under a note claiming decryption never
  raises; decryption has raised typed errors since the AEAD migration, so a
  single unreadable card row aborted startup *and* left the raw number on disk —
  the opposite of both of the migration's goals. An unreadable record now loses
  only its mask and card network while the raw number is still removed; a
  missing key stops the migration untouched, because the same data will decrypt
  perfectly once the key is back.

- Refunding a subscription charge whose stored amount is not a usable number no
  longer moves money. An infinite amount left by an older build was refunded in
  full: the refund committed and the account balance became infinity, together
  with a transaction row and a ledger entry. A `nan` amount reached the ledger's
  NOT NULL constraint and surfaced as a raw database error. Both are now
  reported as a data-integrity failure before anything is written, and so is a
  zero or negative charge — which was previously read as "nothing was charged
  this month" and hid a real charge from the user.

- A recurring payment left behind with a zero or negative amount is reported as
  unreadable instead of being added up. The read path already refused amounts
  that were not finite, but a `-10,00` row entered the monthly budget as a
  `-10,00` reservation and showed ten lira more as spendable than there was. The
  amount column is a magnitude — direction is carried by the income/expense type
  — so a negative value is an invalid record, not a payment in the other
  direction. The stored row is left exactly as it is; nothing is silently
  corrected.

- Selling an asset whose stored price or quantity cannot be read now reports a
  data-integrity failure rather than a generic value error, matching what
  reading the portfolio already did for the same row. Values supplied by the
  caller keep failing as ordinary invalid input; the two cases are no longer the
  same error.

- `insert_asset` rejects an amount that is not finite and positive. It was the
  only monetary write in the service and database layers that accepted `nan` and
  `inf`; the portfolio's real entry point already refused them.

- Opening the restore file picker no longer terminates the application on
  Windows. Kivy asks pywin32 whether each file is hidden, and pywin32 imports a
  timezone helper at the moment of that call rather than at import time, so the
  packager never saw it and left it out. The picker therefore crashed the whole
  process the first time it listed a folder. Backups themselves were never
  affected, and no data was damaged. The packaged build now fails loudly if that
  helper is ever missing again while its parent module is present.

- The My Cards tab scrolls again. The horizontal strip of cards sits inside the
  vertical page, and it is taller than the visible area, so it covered
  practically the whole screen; Kivy offers a touch to the inner scroller first,
  and that one claimed every gesture without checking whether it had anything to
  scroll sideways. Dragging and the mouse wheel both did nothing, which left the
  accounts list below permanently out of reach. The strip now takes only its own
  scrollbar, so dragging reaches the page, and it declines vertical wheel events
  outright — restricting it to the scrollbar was not enough on its own, because
  the wheel is handled earlier than that and was swallowed even though nothing
  moved. That wheel rule is no longer specific to this strip; it is the shared
  behaviour of every list that sits inside the page, described under UI and
  accessibility below. Dragging directly on a card still does not scroll; cards
  absorb touches everywhere in the app.

- Budget plan items are saved through the service layer, which validates the
  amount the same way every other monetary write does. This was the only write
  into a money-bearing table whose SQL lived in the interface layer, so the
  amount was checked only by the form. The form cannot produce a `nan` or an
  infinity, so nothing was reachable through the app; what was missing was a
  rule that a second caller would have to pass. Copying an item to other months
  now happens in the same transaction as the item itself, rather than as
  separate writes that could stop halfway.

- On Windows, a process that loses the race to create the encryption key now
  continues with the key that was actually stored, instead of its own. The file
  provider already worked this way — it orders the write so the loser reads the
  winner's key — but the DPAPI subclass discarded that answer and returned the
  key it had generated, which was never written anywhere. Anything encrypted
  with it would have become unreadable once the process ended. The race is not
  hypothetical: the crypto warm-up and the first data read can both trigger key
  creation during startup, and DPAPI is the provider on that path. Verified with
  an injected protector, so the fix is covered on every platform.

- Identifiers of freshly inserted rows are captured immediately in the asset
  sale, instalment payment and subscription refund paths, and the ledger helper
  now returns the row it wrote instead of leaving callers to read the cursor
  afterwards. All of these were correct, but each depended on no other insert
  landing in between — the assumption that had already failed once.

### Performance

- The large-dataset benchmark has a Windows baseline for the first time, at
  1.000, 10.000 and 50.000 transactions, measured in an isolated temporary
  profile. Scaling is linear across all three sizes; nothing degrades
  faster than the data grows.
- At 10.000 transactions — a realistic upper end for several years of daily
  use — the dashboard summary takes 129ms, the monthly summary 13ms and a
  full decrypt of the dataset 138ms.
- At 50.000 transactions the dashboard summary reaches 779ms and a year of
  insights 1,7s. Backup and restore reach roughly 12s and 11s. These remain
  usable but are the first numbers in this project a user could notice; they
  are recorded here so the next release can be compared against them.
- Windows runs 2-3x slower than the Linux baseline on the sizes both cover.
  The ratio is uninteresting at these absolute times and no Windows-specific
  bottleneck was found; the two runs also used different Python versions.
- Results are committed as `docs/performance/benchmark-results-windows.json`,
  beside the existing Linux baseline rather than replacing it.

### UI and accessibility

- The search bar has been removed from the home screen header. It was never
  connected to anything: the magnifier was an `MDIcon` rather than an
  `MDIconButton`, so it inherited no button behaviour and received no click at
  all, and the field had zero handlers bound to `on_text_validate`, so pressing
  Enter did nothing either. There is no search service behind it. It arrived in
  a commit whose subject was fixing a rendering seam, not adding a feature, and
  it shipped in every release since, looking like a working control. Reported
  by a user. Rather than leave an inviting control that does nothing, it is
  hidden until search is actually implemented. The `SearchBar` component, its
  kv rule, its visual gate and `docs/SEARCH_RENDER_ARTIFACT.md` are all kept —
  the seam fix they cover was real work and will be needed when search is
  built, so the gate's CI step is parked rather than deleted and restoring the
  feature means putting the block back and uncommenting the step. What search
  should actually do is written up in `docs/ROADMAP.md` Phase 2.
- The page can be scrolled with the wheel while the pointer rests over a list
  inside a card. Kivy's scroll view claims a wheel event even when its content
  fits entirely in view, so the event never reached the page behind it: over
  the asset history list — anywhere below that card's heading — the wheel did
  nothing at all. The same applied to the subscription, income, debt, upcoming
  payment, recent transaction, active asset and account movement lists. Those
  lists now hand the wheel back to the page whenever they cannot move in that
  direction, including at the top and bottom of their own content. The card
  strip on the "Kartlarım" tab is covered by the same rule, which replaces the
  strip-specific one that fixed it first.
- Cards no longer reserve space for content they do not have. The active
  debts, upcoming payments, asset history and recent transactions areas had
  fixed heights — 220, 190, 320 and 400dp — so an empty profile scrolled
  through screens of blank card. The debts and upcoming payments cards now
  take their content's height up to a limit, and the limit is a whole number
  of rows, so a populated card no longer cuts the last row in half either. The
  asset history card and the recent transactions list keep their previous
  height when they have rows and close up when they have none. Empty states
  keep their message: the labels that carry it are laid out with an explicit
  height, without which a content-driven card would collapse to nothing and
  hide them.
- The 620dp card strip on the "Kartlarım" tab keeps its fixed height. Closing
  it up when no card exists was tried and reverted against a measurement: with
  the strip shortened, the account cards move under the point a drag starts
  from, and a card absorbs the touch — so the tab stopped scrolling by drag,
  which is the defect that tab was just fixed for. Reclaiming that blank space
  is not worth the tab.
- A note on why the two lists are sized by a switch rather than by their
  contents: a `RecycleView` lays its rows out from its own height, so binding
  that height back to the row count (or to the row layout's `minimum_height`)
  closes a loop. It resolves to a size that renders rows outside the card,
  over the card beneath it. Measured on the assets tab and reverted.
- The recent transactions list says "Bu dönemde işlem bulunmuyor." when the
  selected period has none, in place of what used to be an empty 400dp block.
- Starting a second copy of the application no longer opens an empty black
  window before saying why it will not run. The single-instance check sat at
  the end of `main.py`, so Python had already executed every import above it —
  including `kivy.core.window`, which creates the window as it is imported. The
  notice then arrived on top of a window the user had no use for and could not
  close. The check now runs before any Kivy import and releases through
  `atexit`, so the early exits between the two are covered as well. Measured
  from source: the second instance now produces no Kivy startup output at all,
  where it previously ran the whole of it.
- The robot icon on the "Algoritmik Öngörü" card no longer overlaps its text.
  Reported from a real Windows install; same defect as the heading icons
  below — the icon was laid out without a width, so its glyph spilled into the
  paragraph beside it. Measured after the fix: 44dp icon, 15dp of space before
  the text.
- The heading icons on the "Aktif Borçlarım", "Yaklaşan Ödemeler", "Bekleyen
  İşlemler" and "Varlık Geçmişi" cards no longer overlap the heading text.
  They were laid out without an explicit width, unlike the icons on the
  neighbouring cards, and the glyph spilled into the label beside it. The
  monthly change indicator and the negative-balance warning carried the same
  defect.

### Testing and packaging

- The full suite is 934 tests and runs green on Windows, up from 796 at the
  v0.0.9 gate.
- The scroll gate was proved to measure what it claims. Its red result on a
  populated profile had been suspected of being an artefact of where the
  synthetic touch starts, since a card absorbs a touch that lands on it.
  Toggling the strip's `scroll_type` between `bars` and `content` and running
  the gate both ways settles it: drag scrolls with the fix in place and fails
  without it, from the same untouched point. Had a card been swallowing the
  touch, both runs would have failed.
- The icon and label layout gate scans all five tabs at 1.0, 1.25 and 1.5
  density and is wired into the CI visual-regression matrix, so heading icons
  cannot silently start overlapping their text again.
- The single-instance startup order is pinned by a test, so the lock check
  cannot drift back below the Kivy imports.
- Dependency, type and lint gates were run against this tree on Windows:
  `pip-audit` reports no known vulnerabilities, `mypy` is clean over
  `services` and `database`, and the version mutation matrix catches all 16
  cases. The one High-severity `bandit` finding is a false positive: it
  blacklists the `Crypto.*` import namespace as the abandoned pyCrypto, while
  the actual dependency is its maintained fork, pycryptodome.

### Additional issues found and fixed

- Six release and audit gates reported themselves red on Windows after
  passing. Each prints its result in Turkish, and a redirected stdout falls
  back to a code page that cannot encode those characters, so the script
  raised `UnicodeEncodeError` once its work was already done. The version
  consistency gate exited 1 on a fully consistent tree, and the version
  mutation matrix exited 1 after catching all 16 mutations. CI never saw any
  of it because those steps run on Linux; anyone driving a release from
  Windows would have hit a red gate on a green tree. The scroll gate was the
  worst of the six — its unencodable character appears only in the failure
  line, so it would have crashed without a report at the exact moment it
  turned red.

### Known limitations

- Real OS display scaling at 125% and 150% has since been verified on a
  physical Windows machine and is no longer a limitation. At both scales the
  window reports `PER_MONITOR_AWARE` — at 120 and 144 DPI respectively — so
  Windows does not bitmap-scale it, and Kivy resolves the scale to a density
  of exactly 1.25 and 1.5. Icon and label layout and tab scrolling were
  measured at both with no override, and all pass. Note that the DPI
  awareness comes from SDL2 at runtime; nothing in this project declares it,
  so an SDL2 upgrade should re-measure.
- A physical Turkish Q keyboard has since been exercised by hand with no
  problems found, closing the last part of that item.
- Some Windows environment combinations remain unverified: cross-user DPAPI
  isolation and multi-monitor. Both are blocked by the validation machine
  itself — one active user account, one monitor — not by a defect.
- `accounts.balance` and `savings_goals.current_amount` remain `REAL`
  columns. The `Decimal` migration has moved the arithmetic that reads them,
  not the storage itself.
- Broad exception-handler debt is still open, though the gate holds it flat.
- A 0.x version number still applies: the database schema and the on-disk
  profile layout may change in a future release, with migration provided.
- The plaintext CSV export is written owner-only on POSIX. Windows has no
  equivalent permission bit here, so the file inherits its directory's ACL —
  export to a shared location with that in mind.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.10.exe`
- Linux: `Archlence-0.0.10-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.10-sbom.cdx.json`.

## [0.0.9] — 2026-08-11

This release came out of an audit rather than a feature plan, and most of what
it fixes could lose or corrupt data silently: an infinity typed into an amount
field that quietly removed an account from the portfolio total, a recurring
payment charged twice for the same period, an asset sale that credited cash
while leaving the asset in the portfolio, and a backup whose contents could be
rewritten without the application noticing. It remains a **pre-release**.

### Highlights

- **An amount field can no longer corrupt your balances.** Entering `Infinity`
  as an expense drove an account balance to `-inf`, then to `NULL`, at which
  point the account dropped out of the portfolio total with no error shown — a
  5.000 TL account made 7.500 TL read as 2.500 TL.
- **Money can no longer be moved twice by one action.** Recurring charges and
  refunds are idempotent per period, concurrent card spends can no longer both
  pass the same limit check, and asset sales and debt instalments now complete
  or roll back as a whole.
- **A tampered backup is rejected.** Rewriting the financial data and
  recomputing the stored SHA-256 previously produced a package the application
  accepted; packages are now authenticated.
- **An interrupted restore no longer leaves a mixed profile.** The database,
  key and config move as one generation, and startup finishes or rolls back the
  interrupted attempt before anything reads them.
- **An older build refuses to open a newer database** instead of writing to it
  and dropping the columns it does not recognise.

### Financial correctness and reliability

- Non-finite amounts (`NaN`, `±Infinity`) are rejected at the service boundary
  before any write. Previously an infinity expense drove an account balance to
  `-inf` and then to `NULL`, at which point the account silently dropped out of
  the portfolio total — a 5.000 TL account made 7.500 TL read as 2.500 TL, with
  no error raised.
- A recurring payment can no longer be charged twice for the same due period,
  and the same charge can no longer be refunded twice.
- The credit-card limit check and the write that follows it are now serialised,
  closing a race where two concurrent spends could both pass the same check.
- Asset sales and automatic debt instalments each run in a single database
  transaction. A failure part-way through no longer leaves cash credited with
  the asset still in the portfolio, or an instalment marked paid with no ledger
  entry.
- Asset sale entries record quantity, unit price and profit/loss again. Without
  them a partial sale was indistinguishable from a full one in the ledger.

### Backup, restore and migration

- Backup packages are authenticated. Rewriting the financial data and
  recomputing the stored SHA-256 no longer produces a package the application
  accepts.
- Archive members are validated against an allow-list; unexpected entries and
  traversal-style paths are rejected before extraction.
- Restore treats the database, encryption key and config as one profile
  generation. A failure rolls all three back together — previously the config
  was left from the backup while the database was rolled back, leaving a mixed
  profile.
- An interrupted restore is now recovered at startup, before the key, database
  or config is used. A crash after the restore committed keeps the new
  generation and only finishes cleanup; a crash before it rolls back. A journal
  that cannot be read stops startup rather than guessing.
- Database migrations are retry-safe. A crash after `ALTER TABLE` but before
  the backfill no longer leaves the column permanently unpopulated: completion
  is decided by a postcondition, not by the column's existence.
- The database now records which schema generation wrote it, and an older
  build refuses to open a newer one instead of writing to it and dropping the
  columns it does not recognise. Existing profiles are unaffected: they all
  carry the pre-marker value, which is older than the current generation, and
  they pick up the marker on first start.

### Security and privacy

- Plaintext CSV exports are created with owner-only permissions on POSIX
  systems.
- A restore failure shows a fixed message that carries no key, passphrase,
  journal content, file path or traceback.
- Pillow, cryptography and setuptools are updated to versions without known
  vulnerabilities (18 advisories across the three). The Pillow ones were
  reachable: brand icons are fetched from third-party icon services for a
  user-supplied domain and the response bytes go straight into `Image.open`,
  so a crafted image from a compromised source or an intercepted connection
  could reach decoder bugs that corrupt the native heap.
- Dependencies are now scanned for known vulnerabilities on every pull
  request, and the scan blocks. Nothing had scanned them before, which is why
  eighteen advisories had accumulated unnoticed.

### Performance

- No performance-affecting changes. The reliability fixes add a transaction
  boundary around asset sales and debt instalments and a `BEGIN IMMEDIATE`
  around the card limit check; both are per-operation and were measured as no
  change in the startup and rapid-tap tests that already cover those paths.

### UI and accessibility

- A failed restore recovery and a database written by a newer build each stop
  startup with a plain explanation instead of proceeding. Both messages state
  that no file was touched, and neither carries a path, key, version number or
  traceback.

### Testing and packaging

- The exception-handler gate now recognises `except (Exception,)`,
  `except (Exception, OSError)`, `except builtins.Exception` and aliased forms,
  all of which were previously invisible. It also fails when the baseline holds
  more entries than reality, which is how 44 unused slots accumulated in 0.0.6.
- The Windows installer no longer falls back to a hard-coded `0.0.1` when no
  version input is supplied; the version comes from the single source and a
  mismatch fails the build.
- The upgrade smoke test selects the real previous release by semantic version
  instead of a fixed `v0.0.1`, and reads the expected checksum from that
  release's own manifest.
- The pyflakes scan blocks now that its backlog is empty. It had been
  informational since the debt made it unenforceable; 15 dead imports and 100
  unused assignments were cleared, two of which were stale copies of logic that
  had moved into the service layer.
- `initialize_database()` now closes its connection on every exit path. A
  failure part-way through schema setup previously left it open, which on
  Windows means a lock on the database file — the same lock that would block
  the restore step this release hardened.
- The test suite on both platforms, the reliability gates, lint, the four
  visual-regression combinations and both package builds are now required
  status checks on `main`, so a red run blocks a merge instead of merely
  reporting. The AppImage build was the last one outside that list: Linux
  packaging could break without blocking anything, and it had in fact not been
  built once against this release until it was verified explicitly. The
  expected list is pinned in the repository, which is what makes a silently
  dropped check visible.
- Database connection ownership is pinned by regression tests that count
  connection opens against closes rather than file descriptors, so the
  guarantee also holds on Windows. The earlier descriptor-based measurement
  that reported a leak turned out to be the audit probe's own: it used
  sqlite3's context manager, which commits but does not close. The probe is
  fixed; no production path ever used that pattern.

### Additional issues found and fixed

- A reported connection leak turned out to be the audit probe's own. The probe
  used sqlite3's context manager, which commits but does not close, so it
  leaked one connection per iteration; the same measurement is identical on the
  commit before the reliability work and on the one after, and production never
  used that pattern. The probe is fixed and the finding is recorded rather than
  deleted.
- Two copies of logic that had already moved into the service layer were still
  being computed and discarded in the UI mixins — a sale description and a debt
  is-active flag. Both are removed; keeping second copies is how they drift.
- The mock data generator and the ledger baseline query were the last two
  places not covered by the connection-ownership and identifier rules the rest
  of the codebase follows.

### Known limitations

- Real Windows validation has not been performed: DPAPI, SmartScreen,
  installer upgrade/uninstall and DPI scaling are unverified.
- The visual presentation of a restore-recovery failure is verified only at the
  orchestration level; actual widget rendering was not exercised.
- `accounts.balance` and `savings_goals.current_amount` remain `REAL` columns.
- Broad exception-handler debt is still open, though the gate holds it flat.
- Packaged keystore and recovery behaviour still needs validation on real
  machines rather than in CI.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.9.exe`
- Linux: `Archlence-0.0.9-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.9-sbom.cdx.json`.

## [0.0.8] — 2026-08-06

Every defect in this release comes from the same place: money handled as binary
floating point. Instalment plans that did not add up to the amount financed,
purchase and sale amounts written to the ledger with ten decimal places, and a
savings balance the application displayed but refused to hand over. It remains a
**pre-release**.

### Highlights

- **An instalment plan now adds up to what was financed.** A 1.000,00 TL
  purchase over three instalments showed a 999,99 TL debt; 12.500,00 TL over
  twelve showed 12.500,04 TL. The rounding difference now lands on the final
  instalment, so the parts sum to the principal exactly.
- **The application no longer refuses to give you money it is showing you.**
  A savings goal built from many small deposits could hold 299,99999999 TL
  internally, display "300,00 TL", and then reject a 300,00 TL withdrawal with
  "Hedefte bu kadar birikim yok".
- **Asset purchases and sales record exact kuruş amounts.** Buying with a
  fractional quantity stored figures like `2419.1000000000004` and
  `303.3061479684` as the transaction amount and deducted them from the balance.
- **Loan instalments record exact kuruş amounts.** The loan calculator produced
  an unrounded annuity payment — `5493.320123592063` — which the automatic
  instalment run then wrote to the ledger every month.
- The Arch package installs a scalable (SVG) icon alongside the high-resolution
  PNG, so the icon stays sharp at panel and notification sizes.

### Financial correctness and reliability

- Instalment division uses `Decimal`, and the outstanding balance is derived
  from the **principal minus what has been paid** rather than from
  `monthly x remaining`. The old pair rounded each instalment independently and
  then multiplied the rounded figure back up, so the product did not return to
  where it started — missing in both directions.
- The cash side of an asset trade is quantised on both the buy and the sell
  path. Nothing is lost: price and quantity are stored in their own columns at
  full precision and portfolio value is derived from them; only the cash
  movement is rounded. On a sale, the profit shown now matches the change the
  wallet actually saw, because both figures come from the same quantised
  amounts.
- Loan amounts are quantised in `insert_debt`, the boundary where money becomes
  stored data, so every caller is covered rather than each having to remember.
- Three threshold comparisons now decide at kuruş precision rather than at float
  precision: the savings withdrawal guard, savings goal completion, and the
  credit-card limit check. The limit check previously failed in a way the user
  could not act on, printing the same figure twice — "kullanılabilir limit
  1.000,00 ₺, harcama 1.000,00 ₺".
- Storage is unchanged. `accounts.balance` and `savings_goals.current_amount`
  stay `REAL` columns: measured across realistic deposit patterns the drift does
  not reach the second decimal place, so a schema migration would have carried
  real data-loss risk for a gain that could not be measured. What moved is the
  arithmetic and the decisions, not the schema.

### Performance

- No intentional performance changes in this release.

### UI and accessibility

- No interface changes beyond the amounts themselves now being correct. Figures
  that displayed as rounded while holding a longer number on disk are now the
  same value in both places.

### Testing and packaging

- **The encrypted-field inventory is now anchored to the real schema.**
  `ENCRYPTED_FIELDS` decides what is backed up, what the legacy-format migration
  converts, and what key verification checks; a column missing from it is
  silently absent from all three. Its guard verified the map against a schema
  the test itself built, so the map and the fixture only agreed with each other.
  The new test runs the application's own write paths and scans every column of
  every table on disk for values carrying the `AEADv1:` marker, so detection
  comes from the data rather than from a hand-maintained list. Both directions
  are covered — an undeclared encrypted column, and a declared column that no
  longer exists.
- Regression coverage was verified by reverting each fix and confirming the new
  tests fail with the exact measured discrepancies, then pass again. Several
  tests also assert their own input is still unrounded, so a case cannot quietly
  stop being a test.
- There were no debt tests at all before this release.
- The `PKGBUILD` checksums for 0.0.7 were verified and filled in after that
  release published. They are placeholders again here for the same reason.

### Additional issues found and fixed

- Two guards in this project have now been found self-consistent but not
  anchored to what they guard — the exception-handler baseline in 0.0.6 and the
  encrypted-field inventory here. A coverage threshold written during this work
  repeated the mistake: it passed at eleven encrypted columns while one table
  was never written at all, because a card-only interceptor silently returned
  nothing. A count does not measure coverage; the guard now asserts every
  declared table actually received data.
- The existing instalment tests used 6000/6, which divides exactly, so they
  could not see the defect they were meant to cover.

### Known limitations

- This is still a pre-release and is not considered stable.
- Packages are unsigned; Windows SmartScreen may warn on first launch.
- Automatic instalment runs close a debt on instalment **count**, not on amount.
  A loan carrying recurring extra expenses therefore closes having paid
  `instalment x term`, which is less than the recorded total. Whether those
  extras are meant to be paid through this ledger is a product decision, so this
  is recorded rather than changed.
- `accounts.balance` and `savings_goals.current_amount` remain `REAL` columns,
  deliberately — see above.
- Two functions still close their database connection without protection:
  `initialize_database()` and `generate_mock_data.main()`, both unchanged and
  both deliberate.
- Broad exception-handler debt and the pyflakes backlog are both still open.
- DPAPI and OS-keystore behaviour still deserves verification on real Windows
  hardware rather than CI runners.
- The price fallback covers cryptocurrency and foreign currency only. BIST
  equities and gold still depend on Yahoo Finance alone.
- The legacy CBC reader remains deprecated for old profiles and backups.
- Existing 4-digit PINs are still not migrated to the password policy
  introduced in 0.0.3; unaffected by this release.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.8.exe`
- Linux: `Archlence-0.0.8-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.8-sbom.cdx.json`.

## [0.0.7] — 2026-08-06

The dashboard's period cards were answering a different question than the one
they appeared to ask: the percentage compared this period's cash flow with the
previous period's, which is a growth rate, not a balance change — and it forced
±100% whenever the previous period happened to be empty. Switching the
interface to English also left Turkish text inside every chart. Both are fixed
here. It remains a **pre-release**.

### Highlights

- **Dashboard period cards now measure what they claim to.** The nominal
  change, the percentage, the heading and the active filter all come from one
  shared period definition, and the percentage is a genuine balance change
  measured against the balance at the end of the day before the period starts.
- **An unknown or zero baseline no longer produces a fabricated number.** A
  move away from an actual zero balance has no finite percentage, so the card
  shows `—` instead of ±100%. Zero to zero is the one well-defined no-change
  case and reads as 0%.
- **Switching to English now translates the charts too.** Legends, month
  abbreviations, day labels, asset-type names and the asset history all rebuild
  on a language change instead of leaving Turkish text in an English view.
- The README is rebuilt around the application itself, with a full screenshot
  set generated from a synthetic profile rather than hand-edited images.

### Financial correctness and reliability

- `services/dashboard_period_service.py` is the single definition of the four
  dashboard periods (Today, 1 Week, 1 Month, 1 Year) and of the change
  calculation. The periods use inclusive bounds, and the baseline is the end of
  the day immediately before the period begins.
- The percentage is `(current − starting) / |starting| × 100`, computed in
  `Decimal` rather than binary floating point.
- `percentage_change` returns no value — rendered as `—` — when the baseline is
  unknown or when the balance moved away from an actual zero. Both cases
  previously produced a confident number that meant nothing.
- Dashboard totals are taken from account balances directly, so savings
  transfers and other ledger-only movements no longer make the dashboard
  disagree with the Accounts screen.
- Stale background results are discarded after a filter change, so a slow
  query for the previous period can no longer overwrite the selected one.

### Performance

- No intentional performance changes in this release. The dashboard metrics
  cache introduced in 0.0.6 is unaffected; its tests were extended to cover the
  new period key so a filter change cannot serve a cached result from a
  different period.

### UI and accessibility

- Chart legends ("Income", "Expense", "Opening Balance"), month abbreviations
  and day labels are generated from the application language instead of
  hardcoded Turkish or the process locale.
- Asset types display as Currency, Gold, Crypto and Stock in English.
- A language change clears the chart texture cache and re-renders active assets
  and asset history; previously those kept their original-language text until
  the view was rebuilt some other way.
- Turkish remains unchanged.

### Testing and packaging

- New coverage: `test_dashboard_period_change.py`, `test_chart_localization.py`
  and `test_readme_sample_profile.py`, alongside extensions to
  `test_dashboard_metrics_cache.py`. Cases include each period boundary,
  positive and negative change, a zero baseline, a missing snapshot with ledger
  replay, no data at all, a stale cache result after a filter change, and
  dashboard/accounts agreement after a savings transfer.
- 680 tests pass locally; 2 are skipped for platform reasons (one needs a real
  Kivy window, one is Windows-only `chmod` behaviour).
- `scripts/dev/seed_readme_profile.py` and
  `scripts/dev/capture_readme_screens.py` make the screenshots reproducible
  from a seed rather than from a private profile. The seeding tool refuses to
  touch a real Archlence data directory, refuses home, the repository root and
  anything beneath it, and will only reset a profile it marked itself.
- `scripts/check_version_consistency.py` no longer requires a per-version
  heading in the README, which now carries a dynamic latest-release badge
  instead of a pinned version.
- The `PKGBUILD` checksums for 0.0.6 were verified and filled in after that
  release published. They are placeholders again here for the same reason.

### Additional issues found and fixed

- These two defects were found while regenerating the README screenshots — the
  screenshots were the test. Reviewing what the application actually rendered,
  rather than what the tests asserted, is what surfaced both.
- The README carried pinned checksums and version-specific download links that
  went stale on every release; general downloads now point at
  `/releases/latest`.

### Known limitations

- This is still a pre-release and is not considered stable.
- Packages are unsigned; Windows SmartScreen may warn on first launch.
- The shared `Decimal` policy is not yet applied across every financial path.
  The new period service uses `Decimal` throughout; older paths are unchanged.
- Two functions still close their database connection without protection:
  `initialize_database()` and `generate_mock_data.main()`, both unchanged since
  0.0.6 and both deliberate.
- Broad exception-handler debt and the pyflakes backlog are both still open.
- DPAPI and OS-keystore behaviour still deserves verification on real Windows
  hardware rather than CI runners.
- Some GitHub Actions versions emit a Node.js 20 deprecation warning and are
  forced to Node.js 24 by the runner. CI is unaffected, but the action versions
  should be updated.
- The price fallback covers cryptocurrency and foreign currency only. BIST
  equities and gold still depend on Yahoo Finance alone.
- The legacy CBC reader remains deprecated for old profiles and backups.
- Existing 4-digit PINs are still not migrated to the password policy
  introduced in 0.0.3; unaffected by this release.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.7.exe`
- Linux: `Archlence-0.0.7-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.7-sbom.cdx.json`.

## [0.0.6] — 2026-08-06

This release is about failures the application was hiding from itself. A
fail-closed decryption contract added in 0.0.3 had never reached its callers,
so on real corruption the handlers written to catch it never ran; the CI gate
meant to hold the line on broad exception handlers had 44 unused slots and was
accepting new ones silently; and a dashboard summary was decrypting ten
thousand records on every render. It remains a **pre-release**.

### Highlights

- Corrupt or unreadable financial data no longer produces a confident wrong
  number. Values that feed a **total** now refuse rather than silently counting
  as zero, while values that only feed a **list** still degrade per-row — a
  wrong row is visible and correctable, the same zero inside a sum is not.
- The dashboard summary is cached on the data revision. At 10,000
  transactions a repeat render drops from **328 ms to 0 ms**.
- After **Settings → Delete Data**, the forecast and asset-history sections
  clear along with everything else. They previously kept showing results
  derived from records that no longer existed.
- **TAB** moves between fields in the add-account dialog instead of inserting a
  tab character, and the optional card-number field now reads as optional.

### Financial correctness and reliability

- `utils.crypto.decrypt()` was made fail-closed in 0.0.3, raising typed errors
  for corrupt envelopes, tampered ciphertext and an unreachable key. Its 21
  call sites were never updated and still caught `except (ValueError,
  TypeError)`, written for the old contract. Measured: all four corruption
  modes raise `DecryptionError` subclasses, and **none** is a `ValueError` or
  `TypeError` — so on real corruption those handlers never ran at all and the
  exception escaped to wherever it happened to land. Four files even carried a
  comment asserting the opposite; those comments are gone.
- `KeyUnavailableError` is now deliberately distinguished from per-value
  corruption everywhere. An unreachable key means *no* row can be read, so
  swallowing it per-row would render a total failure as "every amount is
  0,00 TL". It propagates; per-value corruption still degrades locally.
- `get_transactions_by_period` raises instead of zeroing. Its only production
  consumer already wraps the call, logs, and degrades to an empty chart — a
  visible-but-graceful failure rather than a wrong one.
- Seven functions across `main.py`, `calendar_service.py` and
  `transaction_service.py` opened a database connection and closed it as a
  plain statement, leaking the handle on any exception in between. This was not
  theoretical: it is how `export_all_to_csv` began leaking once the key error
  started propagating, and on Windows a leaked handle keeps the database file
  locked. All now use the repository's `managed_connection()`.

### Performance

- `_compute_dashboard_metrics` was profiled at 10,000 transactions: 328 ms,
  with **99% of it in AES-GCM decryption** — 10,800 `decrypt` calls, the cost
  sitting in cipher construction rather than in any Archlence code. Amounts are
  encrypted TEXT, so SQL cannot sum them and every row must be decrypted in
  Python. There is nothing meaningful to shave off the decryption itself; the
  win is not repeating it when nothing changed. The cache key is (revision,
  period filter, today), and each of the three parts earns its place — removing
  any one of them breaks a test.

### UI and accessibility

- TAB inserted a literal tab character into account fields instead of advancing
  focus. Measured: Kivy's `write_tab` defaults to `True`, and turning it off
  alone does not advance focus — `focus_next` must be set too. Both are now
  handled, with a wrap-around focus ring that the account dialog rebuilds
  whenever the account type changes, because the visible fields change with it.
- The card-number field was already optional in both the UI and the service,
  but did not read as optional. It now says so.
- The add-account empty state clears correctly.
- After a data reset, "Algoritmik Öngörü" and "Varlık Geçmişi" no longer show
  stale results. Both are computed only at startup or from their own triggers,
  and neither trigger fires during a reset, so both kept their last computed
  state indefinitely.

### Testing and packaging

- **The exception-handler CI gate had 44 free slots and was only half
  working.** Real broad handlers on `main` numbered 143; the baseline file
  recorded 187, because it was never regenerated after the 0.0.5 narrowing work
  took the count from 184 down. Measured by injection: a new broad handler in a
  *new* function was caught either way, but one added to an *existing* function
  with baseline slack was **silently accepted**. That is the more likely
  direction, and it is how the condition was found — a handler added during
  this release passed the gate while the count rose. The baseline is
  regenerated to the true count and both directions are verified.
- Windows installer smoke tests could hang indefinitely. Five
  `Start-Process -Wait` calls were bounded first; a subsequent hang proved the
  audit incomplete, and three further unbounded operations were found — an
  `Invoke-WebRequest` with no `-TimeoutSec` (the PowerShell default is `0`,
  meaning indefinite), an argument-less `WaitForExit()` that also waits on
  child processes holding inherited handles, and an unbounded recursive
  directory walk. Both smoke steps now carry a step-level timeout, which
  matters less for the minutes saved than because a step that times out
  **keeps its log**; a force-cancelled job does not, and that is why the first
  hang could not be diagnosed.
- The `PKGBUILD` checksums for 0.0.5 were verified and filled in after that
  release published. They are placeholders again here for the same reason.

### Additional issues found and fixed

- `export_all_to_csv` leaked its database connection whenever export raised.
  Found by a Windows CI failure (`WinError 32`, file in use) on a new
  key-unavailable test — a real production leak the test exposed, not a
  test-setup mistake. Local Linux runs stayed green because the same leak is
  silent there.
- A documentation entry still described `decrypt()` as fail-open, three
  releases after it stopped being so.
- A reset test could leave a background thread running past its own end.

### Known limitations

- This is still a pre-release and is not considered stable.
- Packages are unsigned; Windows SmartScreen may warn on first launch.
- Two functions still close their database connection without protection:
  `initialize_database()` (~590 lines, runs once at startup) and
  `generate_mock_data.main()` (a development script that is never packaged).
  Wrapping either means re-indenting the entire body for negligible gain.
- The price fallback covers cryptocurrency and foreign currency only. BIST
  equities and gold still depend on Yahoo Finance alone.
- The legacy CBC reader remains deprecated for old profiles and backups.
- Existing 4-digit PINs are still not migrated to the password policy
  introduced in 0.0.3; unaffected by this release.
- Checking accounts that go negative still show only the raw negative balance,
  with no dedicated overdrawn indicator.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.6.exe`
- Linux: `Archlence-0.0.6-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.6-sbom.cdx.json`.

## [0.0.5] — 2026-08-04

This release lets you record an asset you already owned without disturbing your
wallet balance, gives the price service a fallback so a single upstream outage
no longer freezes every quote, and reports which provider actually answered.
It remains a **pre-release**.

### Highlights

- Adding an asset now asks whether the amount should come out of your wallet
  balance. Choose **Yes** for something you just bought; choose **No** for an
  asset you already owned and are only recording. Previously every entry was
  treated as a purchase, so recording an existing holding retroactively
  distorted today's balance and expense reports.
- Prices no longer depend on a single provider. When Yahoo Finance returns
  nothing for a symbol, cryptocurrency falls back to CoinGecko and foreign
  currency to Frankfurter (ECB).
- The price source shown for an asset now names the provider that actually
  answered, instead of always claiming Yahoo Finance.

### Financial correctness and reliability

- `AssetPurchaseService.create_purchase` takes `deduct_from_balance`. When it
  is false, only the portfolio row is written — no liquid-account transaction,
  no balance mutation, no balance-event entry. When it is true the operation
  stays exactly as before: one atomic transaction covering all four writes.
- Foreign-exchange rates are the linchpin of the price pipeline: crypto and
  gold are both converted to lira by multiplying with USD/TRY. Recovering that
  one rate from Frankfurter therefore keeps crypto and gold priceable even
  when Yahoo Finance is the side that failed.
- Fallback providers deliberately return values in Yahoo Finance's units
  rather than converting to lira themselves, so every downstream conversion
  path is unchanged regardless of which provider supplied the number.

### Performance

- No intentional performance changes in this release. The fallback only runs
  for symbols the primary provider did not return, so a fully successful fetch
  costs exactly what it did before — verified by a test asserting the fallback
  is not called in that case.

### UI and accessibility

- Two English strings were unreachable because the same Turkish key was
  defined twice in the translation table, so the second definition silently
  replaced the first. Affected the recurring-payment day prompt and the
  "days from now" suffix.
- The month-end forecast sentence carried a misleading `f` prefix implying the
  amount was interpolated before translation — the exact mistake that made the
  English locale fall back to Turkish in 0.0.4. The prefix was inert, and is
  now removed with a comment so it is not reintroduced.

### Testing and packaging

- The Arch package's `sha256sums` were four zero placeholders, so `makepkg`
  failed for every AUR user. Real 0.0.4 checksums were verified end to end;
  they are placeholders again here only because the 0.0.5 assets do not exist
  until this release publishes, and will be filled in immediately afterwards.
- The installer and AppImage launch smoke tests now check `crash.log` the way
  the raw-executable test already did. An application that starts, catches an
  exception, logs it and keeps running with a broken screen previously passed
  two of the three packaging paths.
- Continuous integration reports the pyflakes backlog on every run without
  blocking, and no longer mistakes a locally built package's bundled copy of
  KivyMD for project source.
- Broad exception handlers dropped from 184 to 143. Handlers that must stay
  broad — the boundaries where an escaping exception would leave the interface
  waiting forever — are now marked as reviewed rather than counted as
  unexamined debt.

### Additional issues found and fixed

- The legacy-to-AEAD encryption migration was covered by tests that all passed
  even when an entire table stopped being migrated. Coverage now asserts every
  encrypted table is included and pins the field list, so adding an encrypted
  column without extending the migration fails the build.
- A failure while computing the "today's change" figure could kill the asset
  loading thread before any list was drawn, leaving the loading skeleton on
  screen permanently and blocking every later refresh.

### Known limitations

- This is still a pre-release and is not considered stable.
- Packages are unsigned; Windows SmartScreen may warn on first launch.
- The price fallback covers cryptocurrency and foreign currency only. BIST
  equities and gold still depend on Yahoo Finance alone — no free alternative
  source for them is integrated.
- The legacy CBC reader remains deprecated for old profiles and backups.
- Existing 4-digit PINs are still not migrated to the password policy
  introduced in 0.0.3; unaffected by this release.
- Checking accounts that go negative still show only the raw negative balance,
  with no dedicated overdrawn indicator.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.5.exe`
- Linux: `Archlence-0.0.5-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.5-sbom.cdx.json`.

## [0.0.4] — 2026-08-03

This release lets checking accounts go negative on purpose, overhauls brand-icon
quality and performance, virtualizes the subscriptions list, and routes every
previously-silent background failure into the on-disk log. It remains a
**pre-release**.

### Highlights

- Checking accounts, savings goals, and credit-card debt payments can now go
  negative on purpose — the "insufficient balance" guard that blocked this is
  gone. Net worth math is unaffected: the signed-balance convention that
  already let credit-card debt show as a negative balance covers this too.
- Brand-icon logos are noticeably sharper. A multi-provider fallback (Google
  Favicon → icon.horse → Unavatar) replaces the single-provider lookup, and
  every downloaded image is now decoded and re-encoded as a real PNG instead
  of trusting the response's declared content type.
- The "Active Subscriptions" / "Active Incomes" cards are now backed by a
  `RecycleView`. Rendering cost no longer grows with subscription count.
- Background failures that used to `print()` to a console nobody sees in the
  packaged Windows build (`console=False`) are now written to the rotating
  log file with a full traceback.

### Financial correctness and reliability

- **Insufficient-balance guard removed.** `AccountService.check_spending_
  allowed`, `SavingsService.deposit_to_goal`, and `AssetPurchaseService.
  _pick_funding_account` no longer reject a transaction that would take an
  account negative; the atomic `WHERE balance >= ?` guards were removed.
  Asset purchases that no account can fully afford now fund from the
  richest available account and drive it negative, instead of raising.

### Performance

- **Brand-icon matching, 14x.** `classify_brand` re-normalized all 176
  known aliases on every call (~220µs for a non-matching description,
  measured). Alias normalization now happens once at import time
  (~16µs/call after).
- **Health score / forecast, 1.9x.** `compute_financial_health_score` and
  `generate_monthly_forecast` decrypted every transaction's `description`
  even though neither reads it — only `amount` and `date` are used.
  `_load_transactions` now takes `decrypt_description=False` on those two
  paths (measured on 10k transactions: 419ms → 226ms combined). The
  subscription radar and anomaly detector, which do need the description,
  are unaffected.
- **Subscription cards, O(1) instead of O(n).** Rendering used to build
  ~11 KivyMD widgets per active subscription in a single frame (~440
  widgets at 40 subscriptions). Cards now come from a `RecycleView`;
  measured widget count plateaus at 4 regardless of whether the list holds
  10, 50, or 200 entries.

### UI and accessibility

- Two Data & Privacy menu icons (`key-arrow-left`, `key-sync`) referenced
  names that don't exist in the bundled KivyMD 1.2.0 icon set and rendered
  blank; replaced with `key-plus` and `lock-reset`.
- The Calendar dialog no longer lets a day with many transactions push the
  month grid off-screen — the daily transaction list is now a bounded,
  independently-scrolling area sized to the window.
- English-locale monthly forecast text no longer mixes Turkish and English.
  The dynamic balance amount was interpolated into the string *before*
  translation, so the literal (amount-specific) string never matched the
  English dictionary and fell back to the untranslated Turkish template.
  Translation now happens on the static template; the amount is filled in
  afterward.
- "Contact Us" now opens the project's GitHub page instead of a `mailto:`
  link — issues are triaged there, not in an inbox.
- Small brand-icon logos (as low as 16px, the ceiling several providers
  publish for Turkish telecom brands) are upscaled instead of being
  discarded; a prior attempt dropped them below a fixed pixel threshold and
  made those brands' icons disappear entirely.

### Testing and packaging

- New `tests/test_icon_names.py` scans every literal icon name in `.py`/
  `.kv` source against KivyMD's bundled MDI set — the class of bug that
  shipped the two blank Data & Privacy icons above can no longer land
  silently.
- The complete suite (615 tests) passes; `flake8 --select=F821,F822,F823,
  E722` and the exception-baseline gate are both clean.

### Additional issues found and fixed

- `utils/toast.py` (the shared `MDSnackbar`-based toast, introduced this
  cycle) imported KivyMD's snackbar module unconditionally, which crashed
  two test modules on import under the headless test harness. It now
  follows the same headless-fallback contract as `main.py`'s KivyMD import
  guard.
- 108 of 109 `except`-block `print()` calls were converted to `logger.
  exception(...)`, which captures the full traceback instead of just
  `str(exception)`. The one exception (`main.py`'s headless-only mock
  `MDApp.run()`) is informational output, not a swallowed failure, and was
  left as-is. Exception *types* were intentionally left broad in this
  pass — narrowing them requires per-call-site behavioral verification and
  is tracked as follow-up work, not blocking this release.

### Known limitations

- This is still a pre-release and is not considered stable.
- Packages are unsigned; Windows SmartScreen may warn on first launch.
- The price service has a single provider (yfinance).
- The legacy CBC reader remains deprecated for old profiles and backups.
- Most `except` blocks still catch broad exception types (`Exception`);
  they are now logged with a full traceback, but not yet narrowed to
  specific exception classes.
- Checking accounts that go negative show only the raw (negative) balance
  number — there is no dedicated "overdrawn" indicator the way credit
  cards show a `debt` field. Deferred as a UX follow-up.
- Existing 4-digit PINs are still not migrated to the password policy
  introduced in 0.0.3; unaffected by this release.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.4.exe`
- Linux: `Archlence-0.0.4-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.4-sbom.cdx.json`.

## [0.0.3] — 2026-08-02

This release replaces the numeric-only PIN with a password policy, splits
recurring incomes into their own dashboard card, and fixes Borsa Istanbul
stocks reporting ₺0.00. It remains a **pre-release**.

### Highlights

- Local sign-in now requires a password (minimum length, one uppercase
  letter, one special character) instead of a 4-digit PIN, and a new
  Settings entry lets you change it without leaving the app.
- Recurring incomes (salary, etc.) moved out of the subscriptions card into
  their own "Active Incomes" card, so they no longer read as expenses.
- Assets typed as "Hisse Senedi" (stock) now resolve to their Borsa
  Istanbul ticker again and fetch a live price instead of showing ₺0.00.

### Financial correctness and reliability

- **Stock assets stopped pricing.** `normalize_asset_type` only recognized
  the tokens `STOCK`/`HISSE`/`HİSSE`, not the literal label
  `"Hisse Senedi"` the UI actually stores. Unrecognized assets fall through
  to no live price, so every stock entered through the normal flow showed
  ₺0.00 instead of its Yahoo Finance quote. The matcher now also accepts
  `"Hisse Senedi"` (both the Turkish "İ" and ASCII "I" spelling), and the
  equivalent `"Kripto Para"` spelling for crypto, restoring the existing
  `.IS`-suffix resolution in `ticker_mapper`/`asset_service`.

### Performance

- No performance-relevant changes in this release.

### UI and accessibility

- Recurring incomes render in a dedicated "Active Incomes" card with a
  green, filled `cash-multiple` icon, visually distinct from the gray
  repeat icon used for expense subscriptions.
- The Calendar and Monthly Budget dialogs, both of which do heavy
  calculation while building their view, now show a "Please wait,
  loading..." dialog for one frame instead of appearing to freeze.
- Password fields no longer insert a stray character when Tab is pressed
  to move to the next field, and now show persistent helper text stating
  the password rule inline.
- All PIN wording ("PIN", "PIN Değiştir", ...) was renamed to
  "Şifre"/"Password" throughout the UI and the i18n table to match the
  password-based flow.

### Testing and packaging

- The complete 600-test suite passes with this release, including a new
  assertion that the budget planner's deferred build (behind the new
  loading dialog) actually runs under `Clock.tick()`.
- No installer or packaging changes in this release.

### Additional issues found and fixed

- **PIN brute-force search space.** A 4-digit numeric PIN has only 10,000
  possible values; even with Argon2id hashing and the existing
  exponential login lockout, that is a small space for an attacker with
  physical/file access to a device to work through offline. The new
  password policy (minimum length, uppercase, special character) moves
  the character set from digits-only to alphanumeric-plus-symbols, adding
  orders of magnitude of combinations on top of the existing lockout and
  hashing.
- The brand-icon lookup table now recognizes roughly twenty additional
  Turkish banks and fintech wallets (Garanti BBVA, İş Bankası, Yapı
  Kredi, Ziraat, Akbank, VakıfBank, Halkbank, Enpara, QNB Finansbank,
  TEB, DenizBank, Kuveyt Türk, Türkiye Finans, Albaraka, Papara, Ininal,
  Tosla, Paycell, Nays, Pokus, Ozan), so recurring payments to these show
  their real logo instead of the generic fallback.

### Known limitations

- This is still a pre-release and is not considered stable.
- Packages are unsigned; Windows SmartScreen may warn on first launch.
- The price service has a single provider.
- The legacy CBC reader remains deprecated for old profiles and backups.
- Broad exception handlers and `print()`-based reporting remain in parts of
  the UI layer.
- **Existing 4-digit PINs are not migrated.** The new password policy is
  only enforced at setup/change time; a user who upgrades without
  changing their password keeps signing in with their old 4-digit PIN
  until they use Settings > Change Password.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.3.exe`
- Linux: `Archlence-0.0.3-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.3-sbom.cdx.json`.

## [0.0.2] — 2026-07-30

This release fixes two Windows-specific defects that could lead to lost work or
an unclean shutdown. It remains a **pre-release**.

### Highlights

- The complete test suite now runs in Windows CI as well as Linux. Both fixes
  in this release were found directly through that coverage.

### Financial correctness and reliability

- **Turkish error text could terminate a transaction on Windows.** Legacy
  Windows consoles commonly use cp1252, which cannot encode several characters
  used in Turkish messages. Many application messages are emitted inside exception
  handlers, so a `UnicodeEncodeError` there escaped the original handler and
  could terminate the operation. In the confirmed case, a subscription-radar
  failure caused the complete transaction to be lost. Console streams now use
  UTF-8 with replacement for unsupported output, preventing the reporting path
  from terminating the operation.
- **The Windows single-instance lock could fail during shutdown.** The lock
  file was truncated after its byte was locked. Windows byte-range locking
  could then reject the unlock call and crash shutdown. The lock now uses a
  fixed byte that is never truncated, and release is guarded on every exit
  path.

### Performance

- Fixing Windows `multiprocessing` spawn safety made `run_tests.py` up to three
  times faster in the measured CI job. Previously, tests that created a child
  process could rerun the complete suite in every child. This result is from CI
  and has not been independently benchmarked on user hardware.

### UI and accessibility

- This release has no user-visible UI change. Both fixes concern background
  error reporting and process lifecycle.

### Testing and packaging

- The complete suite now runs on Windows CI.
- `run_tests.py` is safe under the Windows `multiprocessing` spawn method; the
  suite is no longer recursively executed inside child processes.
- Test isolation now uses the cross-platform `ARCHLENCE_HOME` override. The
  previous mechanism did nothing on Windows and could write into a real user
  profile.
- The v0.0.1 → v0.0.2 upgrade smoke test installs the real baseline release,
  writes a sentinel record, upgrades in place, and verifies preservation.

### Additional issues found and fixed

- Several test helpers left SQLite connections open. A context manager around
  `sqlite3.connect(...)` controls a transaction but does not close the
  connection. Linux allows deletion of an open file, masking the defect;
  Windows kept it locked and failed cleanup. The helpers now close their
  connections explicitly.

### Known limitations

- This is still a pre-release and is not considered stable.
- Packages are unsigned; Windows SmartScreen may warn on first launch.
- The price service has a single provider.
- The legacy CBC reader remains deprecated for old profiles and backups.
- Broad exception handlers and `print()`-based reporting remain in parts of
  the UI layer.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.2.exe`
- Linux: `Archlence-0.0.2-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.2-sbom.cdx.json`.

## [0.0.1] — 2026-07-30

Initial public release. This is a **pre-release**: packages install and launch,
and the flows below are covered by tests, but it is not yet considered stable
or recommended for everyday financial tracking.

### Highlights

- Fixed a cursor defect that rearranged digits while entering an amount.
- Removed UI stalls from the calendar, monthly budget, category settings, and
  transaction-add flows.
- Asset purchases now select an account that can actually fund the purchase.

### Financial correctness and reliability

- **Amount-entry corruption:** the thousands-separator mask ran inside Kivy's
  `on_text` event, leaving the cursor one character behind. Typing `1234567`
  could produce `1.235.674`, recording a different amount from the one entered.
  Formatting now occurs after editing and was verified in a real SDL2/OpenGL
  window.
- **Extreme-amount guard:** the integer portion is limited to 12 digits. Larger
  values can exceed the reliable integer range used by `float64` and silently
  corrupt balance arithmetic. The limit is applied during input and does not
  rewrite existing records.
- **Funding-account selection:** asset purchases were always deducted from
  `DEFAULT_ACCOUNT_ID` (`1`). That row may not exist, or the user's funds may
  be held elsewhere. Archlence now selects a checking account that can cover
  the amount and reports the named account and shortfall when none can.
- **Backdated transaction entry removed:** a past-dated record changed the
  current balance immediately but could not be placed correctly in the
  historical balance ledger. Future-dated pending transactions remain
  supported.

### Performance

These results measure call counts and work performed, not elapsed time, and are
protected by regression tests.

- **Calendar:** selecting a day no longer rebuilds all 42 cells or opens
  unbounded threads and SQLite connections. Twelve rapid selections now
  coalesce into one database read, and only the affected cells are repainted.
- **Monthly budget:** twelve rapid month changes now coalesce into one list
  rebuild.
- **Category settings:** ten rapid toggles now coalesce into one chart refresh.
- **Transaction entry:** four heavy refreshes are spread across separate
  frames instead of blocking one frame together.

### UI and accessibility

- Asset-add failures now show the actual cause, such as the funding account and
  missing amount, instead of a generic error.
- The transaction date picker no longer offers past dates.

### Testing and packaging

- **Test reporting restored.** Kivy replaces `sys.stderr` during import. The
  runner previously captured the stream afterward, hiding test names,
  tracebacks, and the final summary after roughly the 69th test. It now
  captures the real stream before any Kivy import while retaining a correct
  failure exit code.
- Price and portfolio failures now use the persistent rotating log instead of
  `print()`, which disappears from Windows `console=False` packages.
- Test suite at release: 595 passing tests, including 26 new regression tests.

### Additional issues found and fixed

- The fake text field in `tests/test_formatters.py` updated its cursor in the
  opposite order from Kivy and allowed the production amount bug to pass. It
  now follows real `insert_text` ordering.
- `tests/test_asset_price_worker.py` treated a `print()` call as proof of
  logging. It now verifies the persistent logger used by packaged builds.

### Known limitations

- This is not stable and is not recommended for daily financial tracking.
- The Windows gold/asset-add fix still needs broader user-hardware validation.
  Failures are recorded under
  `%LOCALAPPDATA%\Archlence\Archlence\Logs\archlence.log`.
- Packages are unsigned; Windows SmartScreen may warn on first launch.
- The price service has a single provider.
- The legacy CBC reader remains deprecated for old profiles and backups.
- Broad exception handlers and `print()`-based reporting remain in parts of
  the UI layer.
- Decimal rules exist, but not every monetary path has completed migration.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.1.exe`
- Linux: `Archlence-0.0.1-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.1-sbom.cdx.json`.
