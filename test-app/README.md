# Events test client

Minimal vanilla TypeScript Jellyfin client, scaffolded with create-vite. Reads real server/plugin APIs; no fixture data is embedded in the app.

The CLI help was inspected before scaffolding:

```sh
npx --yes create-vite@latest --help
npx --yes create-vite@latest test-app --template vanilla-ts --no-interactive --no-immediate
```

## Run

From this directory:

```sh
npm ci
npm run dev
```

Open <http://localhost:5173>. Keep the development Jellyfin container running on port 8097. If it has already been configured:

```sh
# From the repository root:
docker compose -f dev/docker-compose.yml up -d
```

For a fresh plugin installation and generated media fixtures, run `./dev/run.sh` from the repository root. That script owns the disposable server's accounts and event definitions; rerunning it replaces fixture events.

Leave the client server URL set to `/jellyfin`. The [Vite proxy](https://vite.dev/config/server-options#server-proxy) forwards requests to `http://127.0.0.1:8097`, including authenticated artwork requests. To point the proxy elsewhere, copy `.env.example` to `.env.local`, change the target and Web URL, and restart Vite. An absolute HTTP(S) Jellyfin server URL can also be entered at login if its CORS settings permit this origin. Include the server's base path if configured.

The dev server binds to loopback and uses port 5173 with `strictPort`, so a port collision fails rather than silently choosing another port. `npm run build` typechecks and produces `dist/`; `npm run preview` serves the build on port 4173 with the same local proxy. Static hosting requires an equivalent proxy or an absolute server URL.

## Exercise events

1. Sign in with `admin` / `admin` for the local verification server. **Live events** uses the current server-local date. After placeholder seeding, **Placeholder spotlight** provides seven items year-round.
2. Choose **Preview a date**, set `2026-12-15`, leave **View as** set to **Me**, and click **Apply**. Christmas movies/episodes and Winter favorites should appear.
3. Preview `2026-10-20` for Halloween. Select **child** and apply to verify parental filtering, or **limited** to verify no library access. Controls only appear to administrators; normal logins use the viewer endpoints.
4. Click an item to inspect its Jellyfin DTO or open its detail page in Jellyfin Web. This client tests discovery; playback is handled by Jellyfin Web.
5. Expand **API inspector** to see recent endpoint/status/timing records and the latest feed JSON. Use **Refresh** after editing events in the plugin settings page.

Cards include type, episode series/season/number, watched status, and primary artwork when available. Event/item order follows the server response. Lists load 24 items initially with **Load more** for subsequent pages. Missing artwork falls back to a placeholder. Refresh happens on window focus and every two minutes while visible, using the last applied mode/date/user.

Authentication tokens stay in memory and are sent in headers, including image requests; they are not stored in browser storage or image URLs. Reloading requires another login. Sign out clears the UI and attempts to revoke the Jellyfin session. The client does not edit events or library metadata.

## Verification

`npm run build` passed with strict TypeScript checking. Browser verification against the installed plugin on `jellyfin/jellyfin:latest` (Jellyfin 12.1.0) covered:

- Invalid credentials, administrator login, sign out, and empty live state.
- December preview with movie/episode ordering, loaded artwork, watched status, episode details, and the Jellyfin Web link.
- Halloween preview as a child account with restricted media/artwork omitted.
- Live events with a temporary all-year event: three items as admin, two permitted items as child, none as limited; administrator controls hidden for ordinary accounts.

The temporary event was removed and original schedules restored after testing. Placeholder libraries can be seeded with `python3 dev/seed-placeholders.py` from the repository root; cards label these items **Placeholder**. Pagination is implemented, but the initial small fixture library did not exercise **Load more**. The plugin's API pagination has separate integration coverage.
