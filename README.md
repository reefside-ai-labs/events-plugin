# Jellyfin Events

A Jellyfin server plugin for curated seasonal discovery. Create an event, select movies and individual TV episodes, and choose when a client should promote them. Christmas can run December 1–31; Halloween can include Harry Potter because it fits the event you curate.

Based on the [official Jellyfin plugin template](https://github.com/jellyfin/jellyfin-plugin-template) at commit `c93225a0a5a76d3843db05b4b5b77fcfc482fba3`. This version targets **Jellyfin 12.1.0 / .NET 10**. It provides administration and an authenticated API; a client must implement event display. Installing it does not add discovery rows to stock clients.

## Features

- Server-wide events maintained by administrators in plugin settings.
- Title, optional description, optional artwork from a library movie or episode.
- Searchable selection and ordering of movies and individual episodes, plus event ordering.
- Annual month/day ranges by default, with optional one-time date ranges.
- Inclusive boundaries in the server's local timezone. Cross-year annual ranges are supported; equal boundaries mean one day. February 29 is rejected for annual boundaries and accepted for valid one-time dates.
- Enabled toggle, schedule overlap warnings, and preview for any date and existing user.
- Viewer results respect library access and parental controls, skip deleted items, and omit empty events. Watched content remains eligible.
- Missing selections retain their saved label for administrator repair. Media metadata and ordinary library visibility are unchanged.
- Conflict detection protects against overwriting edits saved by another administrator.

Overlap warnings consider schedules, even when an event is empty. They never block saving. For recurring events, the displayed warning dates are an example occurrence around the current year; the overlap repeats annually.

## Build and install

Install the .NET 10 SDK, then:

```sh
dotnet test -c Release
./dev/package.sh
```

Extract `artifacts/Jellyfin.Plugin.Events-0.1.0.0.zip` into a dedicated directory under the server's plugins directory, such as `/config/plugins/Events_0.1.0.0/`. Restart Jellyfin. Open **Dashboard → Plugins → Events → Settings** and create your events. Remove any older Events DLL installation before installing another version.

Use the settings page to save changes before previewing. For annual dates, enter `MM-dd`, such as `10-18` through `10-31`. Pick artwork with **Use artwork** beside a selected item or search result. Artwork uses the source item's Primary image; choose an item with that image available.

The displayed server timezone must match your intended location. For Docker, set `TZ` (the development compose file uses `America/Denver`). A container using UTC will evaluate events in UTC. Changes take effect on the next API request; clients should refresh on resume and periodically across date boundaries.

Configuration is persisted in Jellyfin's plugin configuration directory as `Jellyfin.Plugin.Events.xml`; include it in normal server backups. Selections use server-local Jellyfin IDs and do not automatically rematch content after deletion/reimport or migration to another server.

## Docker verification

Requires Docker, .NET 10, Python 3, and FFmpeg on the host:

```sh
./dev/run.sh
```

This pulls **`jellyfin/jellyfin:latest`**, generates tiny local media fixtures, builds and installs the plugin, starts a uniquely named development server, and runs integration checks including a container restart. The resolved server version and image digest are recorded in `artifacts/verification.json`. If `latest` advances to an incompatible Jellyfin version, the compatibility check fails; update the project/package references and test before claiming support.

The disposable server is available at <http://localhost:8097/web/>. Login: `admin` / `admin`. It is bound to localhost, separate from other Jellyfin containers. Verification also creates `limited` and `child` accounts and example events. **The verification script owns this development server's fixture configuration; rerunning it replaces event definitions.**

```sh
# Stop the development container while preserving its data:
docker compose -f dev/docker-compose.yml down

# Rerun API checks against the running development container:
python3 dev/verify.py
```

See [the API contract](docs/API.md) and [verification results](docs/VERIFICATION.md).

## Test client

A minimal Vite client is available in [test-app](test-app/README.md). It supports real Jellyfin login, live event rows, administrator date/user previews, and an API inspector.

```sh
cd test-app
npm ci
npm run dev
```

Open <http://localhost:5173>, leave the server URL as `/jellyfin`, and sign in to the local test server with `admin` / `admin`. Preview December 15 to see the Christmas fixtures outside their active season.

### Placeholder library

`./dev/run.sh` also seeds 16 movie and 6 fictional episode placeholders, with NFO metadata and original test posters, using Jellyfin's [`.disc` placeholder support](https://jellyfin.org/docs/general/server/media/placeholders/). These are browsable items without playable video. Separate **Placeholder Movies** and **Placeholder TV** libraries keep them distinct from the three playable verification fixtures.

To add or restore the placeholders on the already configured development server:

```sh
python3 dev/seed-placeholders.py
```

The seed preserves existing events/selections, adds the seasonal placeholders to Christmas and Halloween, and creates **Placeholder spotlight**, a clearly labeled event active January 1–December 31 so live discovery has items today. Disable that event in plugin settings when testing seasonal boundaries; its intentional overlaps produce normal schedule warnings. Running the seed again preserves an existing spotlight event's enabled flag. Metadata matching is local, so no external accounts or downloads are needed.


## Scope

Version one delivers the plugin only. A minimal test client exercises the API. Integration into a full client, automatic tag/rule membership, generated recommendations, personal events, and custom artwork uploads are future work.

GPL-3.0; see [LICENSE](LICENSE).
