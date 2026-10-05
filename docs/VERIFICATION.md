# Verification

Verified 2026-10-05T04:40:09.560818+00:00 against `jellyfin/jellyfin:latest`, resolved to **Jellyfin 12.1.0** on Linux ARM64.

Image digest: `jellyfin/jellyfin@sha256:78d3ea1207d1322471fcac39a614f004f2ccf7e878f95ab2977d752f07e4dd7e`.

- Release build: passed with zero warnings/errors.
- Calendar and validation tests: **24 passed** (`dotnet test -c Release`).
- Installed-plugin integration checks: **36 passed** (`./dev/run.sh`).
- Settings-page browser checks: creating an event, searching/adding a movie and individual episode, selecting library artwork, saving, preserving the selected event after save, reordering items, previewing the saved order, and previewing as a user with no library access passed. The page rendered in Jellyfin Web without console errors; multiple overlap warnings are collapsible.

Integration coverage includes date boundaries, annual recurrence, cross-year ranges, one-time leap dates, enabled flags, missing/empty items, normal Jellyfin image/episode DTO fields, pagination, event ordering, watched eligibility, authentication/admin policy, library restrictions, parental restrictions for both items and artwork, validation, stale-write conflicts, and configuration persistence after a container restart. The plugin was loaded and active before and after restart.

The tiny media fixtures are generated locally with FFmpeg and NFO metadata. No external content matching or client discovery implementation is required for these checks. After browser verification, the development server was left with Christmas, Halloween, and Winter favorites examples.

Machine-readable results are in `artifacts/verification.json`. Reproduce with `./dev/run.sh`; it owns the disposable server's fixture events and accounts. It pulls `latest` again, so record the new image/version when rerunning. Verification establishes compatibility with this resolved version, not future releases.

## Placeholder library

Added and verified 22 `.disc` placeholders (16 movies, 6 fictional episodes) in separate placeholder libraries, each with local NFO metadata and original typographic artwork. The seed script was run twice without duplicating events or selections. The plugin returns 7 items in the always-active Placeholder spotlight event and 13 accessible items in each populated Christmas/Halloween event (including the original playable fixtures). The limited account sees none; the child account sees 3 permitted spotlight items.

All 36 integration checks were rerun successfully with the additional libraries present, and the populated events were restored afterward. The verification login now retries during restart initialization, rather than assuming the public-info endpoint means authentication is ready. The test client build passed and its live discovery row displays the placeholder items with explicit labels. Machine-readable results are in `artifacts/placeholders-verification.json`.
