#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
dotnet build "$repo/Jellyfin.Plugin.Events" -c Release --nologo
mkdir -p "$repo/artifacts"
cp "$repo/Jellyfin.Plugin.Events/bin/Release/net10.0/Jellyfin.Plugin.Events.dll" "$repo/artifacts/"
python3 - "$repo" <<'PY'
from pathlib import Path
import hashlib
import sys
import zipfile
root = Path(sys.argv[1])
archive = root / 'artifacts/Jellyfin.Plugin.Events-0.1.0.0.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as out:
    out.write(root / 'artifacts/Jellyfin.Plugin.Events.dll', 'Jellyfin.Plugin.Events.dll')
    out.write(root / 'LICENSE', 'LICENSE')
(root / 'artifacts/SHA256SUMS').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
print('Packaged ' + str(archive))
PY
