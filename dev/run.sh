#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(dirname "$here")"
compose=(docker compose -f "$here/docker-compose.yml")
"${compose[@]}" pull
python3 "$here/make-fixtures.py"
# The plugin is installed before startup, then reloaded if the container exists.
dotnet build "$repo/Jellyfin.Plugin.Events" -c Release --nologo
mkdir -p "$here/data/config/plugins/Events_0.1.0.0" "$here/data/media" "$repo/artifacts"
cp "$repo/Jellyfin.Plugin.Events/bin/Release/net10.0/Jellyfin.Plugin.Events.dll" "$here/data/config/plugins/Events_0.1.0.0/"
cp "$repo/Jellyfin.Plugin.Events/bin/Release/net10.0/Jellyfin.Plugin.Events.dll" "$repo/artifacts/"
"${compose[@]}" up -d
"${compose[@]}" restart
python3 "$here/verify.py"

# Populate a browsable placeholder library and an explicitly named live demo event.
python3 "$here/seed-placeholders.py"
