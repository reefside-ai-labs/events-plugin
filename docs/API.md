# Events API v1

All routes are relative to the Jellyfin server/base path. Use the normal Jellyfin authenticated session, for example `Authorization: MediaBrowser Token="<access-token>"`. Viewer routes derive the user from that session and do not accept a user override. API keys without a user context cannot retrieve viewer feeds.

Responses follow the server's normal JSON conventions (PascalCase by default; GUIDs are returned without hyphens). Optional null fields may be omitted. Viewer and preview responses use `Cache-Control: private, no-store` because membership and access can change.

## Viewer routes

| Route | Behavior |
| --- | --- |
| `GET /Events/Active` | Server timezone, current server-local date, and ordered summaries of active events containing accessible content. |
| `GET /Events/{id}/Items?startIndex=0&limit=50` | Ordered Jellyfin `BaseItemDto` objects for an active event, filtered for the calling viewer. |

`StartIndex` must be nonnegative; `Limit` is 1–200. Paging happens after filtering/deduplication. An unknown, disabled, inactive, or inaccessible/empty event returns 404. Anonymous requests return 401. A page beyond the last item returns an empty `Items` array with the filtered total.

Example active response:

```json
{
  "ServerTimeZone": "America/Denver",
  "Date": "2026-12-15",
  "Events": [
    {
      "Id": "32ae7a02c9f84dc2b90220d4d2386aaf",
      "Title": "Christmas",
      "Description": "Christmas favorites and TV specials",
      "ScheduleType": "Annual",
      "StartDate": "12-01",
      "EndDate": "12-31",
      "ArtworkItemId": "fe17a7247f0640b185d82ea3d3d4381e",
      "ItemCount": 12
    }
  ]
}
```

The item response is `{ "Event": <summary>, "Items": [<BaseItemDto>, ...], "TotalRecordCount": 12, "StartIndex": 0 }`. Standard Jellyfin DTO fields include item ID, type, artwork tags, and episode series/season/episode information. Use the normal Jellyfin navigation/playback APIs for each item. Content may appear in multiple event lists; duplicates within a list are removed.

`ArtworkItemId` is returned only if that item is visible to the viewer. Load its image through Jellyfin's normal `/Items/{id}/Images/Primary` endpoint using the viewer's credentials. Handle a missing image with your normal placeholder; source artwork can change or disappear.

Clients should fetch the feed on discovery entry/resume, refresh while open (e.g. every few minutes), and clear stale rows after edits or date changes. The server does not push activation notifications. A missing plugin endpoint (404) should disable the client feature gracefully.

## Administrator routes

All require Jellyfin's `RequiresElevation` policy; ordinary users receive 403.

| Route | Behavior |
| --- | --- |
| `GET /Events/Configuration` | Revision, timezone/date, ordered full event definitions, overlap warnings, selection/artwork diagnostics. |
| `PUT /Events/Configuration` | Validate and replace the ordered event list. Body: `{ "Revision": n, "Events": [...] }`. |
| `POST /Events/Validate` | Validate a draft and compute warnings/diagnostics without persisting. Same body shape. |
| `GET /Events/Search?term=Christmas&startIndex=0` | Up to 50 movie/episode DTOs matching the search term. Term maximum 200 characters. |
| `GET /Events/Preview?date=2026-12-15&userId=<optional-id>` | Same feed evaluation on a supplied calendar date; defaults to the administrator. |
| `GET /Events/Preview/{id}/Items?date=2026-12-15&userId=<optional-id>&startIndex=0&limit=50` | Same item filtering/paging for the supplied date and user. |

Use the custom configuration endpoint for validated, conflict-aware editing. Jellyfin's built-in generic plugin configuration API remains a host facility, but is not the supported event-editing contract.

An event definition:

```json
{
  "Id": "32ae7a02c9f84dc2b90220d4d2386aaf",
  "Title": "Christmas",
  "Description": "Christmas favorites and TV specials",
  "Enabled": true,
  "ScheduleType": "Annual",
  "StartDate": "12-01",
  "EndDate": "12-31",
  "ArtworkItemId": "fe17a7247f0640b185d82ea3d3d4381e",
  "Items": [
    { "ItemId": "fe17a7247f0640b185d82ea3d3d4381e", "Label": "Christmas Movie (2020)" }
  ]
}
```

- Event IDs are stable, unique, and nonempty. Array position determines event/item order.
- Title: 1–200 characters. Description: up to 4000 characters. Saved selection label: up to 500 characters.
- Maximum 200 events, 5000 selections per event. Duplicate selections are normalized to their first occurrence.
- `ScheduleType`: `Annual` or `OneTime`. Annual boundaries use strict `MM-dd`; one-time boundaries use strict `yyyy-MM-dd` with end on/after start. Boundaries are inclusive. Annual February 29 boundaries are invalid.
- Existing selected items must be movies or individual episodes; missing item IDs are retained for repair. Labels of existing selections are refreshed from library metadata on save.
- Empty events may be saved while being curated; they do not appear in viewer feeds.
- Overlap warnings are advisory and only consider enabled schedules. `RepeatsAnnually` is true when both events are annual. Dates describe an example intersection; no content overlap analysis is performed.
- `Diagnostics` reports each selection as `Available`, `Missing`, or `Unsupported`; `ArtworkStatus` is `Missing` when its source no longer exists.
- Validation returns 400 with `{ "Errors": ["..."] }`; an outdated revision returns 409. Reload and reconcile edits before retrying. Successful saves increment `Revision` and return updated configuration/warnings/diagnostics.

Preview uses saved definitions and honors enabled flags. Admins may preview as another user, but viewer endpoints cannot impersonate users. Overlap warnings and missing-selection diagnostics are never exposed in viewer responses.
