#!/usr/bin/env python3
"""Add .disc media and demo events to the local events-jellyfin container.

Preserves other event definitions and selections. Uses the container's FFmpeg
for original typographic test artwork. No external metadata providers required.
"""
from pathlib import Path
import json
import subprocess
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
MEDIA = ROOT / 'data/media/placeholders'
BASE = 'http://localhost:8097'
TOKEN = None

MOVIES = [
    ('Home Alone', 1990, 'PG', 'Christmas'),
    ('Elf', 2003, 'PG', 'Christmas'),
    ('The Polar Express', 2004, 'G', 'Christmas'),
    ('Klaus', 2019, 'PG', 'Christmas'),
    ('The Muppet Christmas Carol', 1992, 'G', 'Christmas'),
    ('The Grinch', 2018, 'PG', 'Christmas'),
    ('Arthur Christmas', 2011, 'PG', 'Christmas'),
    ('It\'s a Wonderful Life', 1946, 'PG', 'Christmas'),
    ('Hocus Pocus', 1993, 'PG', 'Halloween'),
    ('The Nightmare Before Christmas', 1993, 'PG', 'Halloween'),
    ('Coraline', 2009, 'PG', 'Halloween'),
    ('The Addams Family', 1991, 'PG-13', 'Halloween'),
    ('Halloween', 1978, 'R', 'Halloween'),
    ('Harry Potter and the Philosopher\'s Stone', 2001, 'PG', 'Halloween'),
    ('Harry Potter and the Prisoner of Azkaban', 2004, 'PG', 'Halloween'),
    ('Beetlejuice', 1988, 'PG', 'Halloween'),
]
# Fictional episodes make their test purpose clear and avoid external episode matching.
EPISODES = [
    (1, 'The Christmas Party', 'Christmas'),
    (2, 'Snow Day', 'Christmas'),
    (3, 'Christmas Eve', 'Christmas'),
    (4, 'The Halloween Heist', 'Halloween'),
    (5, 'The Haunted House', 'Halloween'),
    (6, 'Trick or Treat', 'Halloween'),
]
SEASONS = {'Christmas': ('173f38', 'd5b56d'), 'Halloween': ('33203e', 'ed9c50')}


def request(path, data=None, method=None):
    headers = {'Authorization': 'MediaBrowser Client="Events placeholder seed", Device="CLI", DeviceId="events-placeholder-seed", Version="0.1.0"'}
    if TOKEN:
        headers['Authorization'] += f', Token="{TOKEN}"'
    if data is not None:
        headers['Content-Type'] = 'application/json'
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE + path, headers=headers, data=None if data is None else json.dumps(data).encode(), method=method), timeout=30) as response:
            body = response.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'{method or "GET"} {path}: HTTP {error.code}: {error.read()[:400]!r}') from error


def nfo(path, kind, fields):
    root = ET.Element(kind)
    for name, value in fields.items():
        ET.SubElement(root, name).text = str(value)
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def poster(path, title, season, subtitle):
    if path.exists() and path.stat().st_size > 100:
        return
    bg, accent = SEASONS[season]
    title_text = '\n'.join(textwrap.wrap(title, width=18, break_long_words=False))
    subprocess.run(['docker', 'exec', '-i', 'events-jellyfin', 'sh', '-c', 'cat > /tmp/events-placeholder-title.txt'], input=title_text.encode(), check=True)
    filters = ','.join([
        f'drawbox=x=24:y=24:w=352:h=552:color=0x{accent}:t=2',
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{season.upper()}':fontsize=16:fontcolor=0x{accent}:x=42:y=54",
        'drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:textfile=/tmp/events-placeholder-title.txt:fontsize=29:line_spacing=9:fontcolor=white:x=42:y=(h-text_h)/2-10',
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{subtitle}':fontsize=15:fontcolor=0x{accent}:x=42:y=508",
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='PLACEHOLDER / NO VIDEO':fontsize=12:fontcolor=white:x=42:y=544",
    ])
    with path.open('wb') as output:
        subprocess.run(['docker', 'exec', 'events-jellyfin', '/usr/lib/jellyfin-ffmpeg/ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', f'color=c=0x{bg}:s=400x600', '-vf', filters, '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'mjpeg', '-'], stdout=output, check=True)


TOKEN = request('/Users/AuthenticateByName', {'Username': 'admin', 'Pw': 'admin'})['AccessToken']
(ROOT / 'data/admin-token').write_text(TOKEN)

for title, year, rating, season in MOVIES:
    folder = MEDIA / 'movies' / f'{title} ({year})'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f'{title} ({year}).disc').touch()
    nfo(folder / 'movie.nfo', 'movie', {'title': title, 'year': year, 'mpaa': rating, 'genre': season, 'tag': 'Events test placeholder', 'plot': f'{season} discovery placeholder for testing the Events plugin. This item has metadata and artwork but no playable video.'})
    poster(folder / 'poster.jpg', title, season, f'MOVIE / {year}')

show = MEDIA / 'tv/Seasonal Stories (2026)'
season_dir = show / 'Season 01'
season_dir.mkdir(parents=True, exist_ok=True)
nfo(show / 'tvshow.nfo', 'tvshow', {'title': 'Seasonal Stories', 'year': 2026, 'mpaa': 'G', 'plot': 'Fictional seasonal episode placeholders for Events plugin testing.'})
poster(show / 'poster.jpg', 'Seasonal Stories', 'Christmas', 'TEST SERIES / 2026')
for number, title, season in EPISODES:
    stem = season_dir / f'Seasonal Stories - S01E{number:02d} - {title}'
    stem.with_suffix('.disc').touch()
    nfo(stem.with_suffix('.nfo'), 'episodedetails', {'title': title, 'showtitle': 'Seasonal Stories', 'season': 1, 'episode': number, 'mpaa': 'G', 'genre': season, 'plot': f'Fictional {season.lower()} episode placeholder. No playable video; intended for testing discovery.'})
    poster(stem.with_suffix('.jpg'), title, season, f'TV EPISODE / S01E{number:02d}')

folders = request('/Library/VirtualFolders')
for name, kind, path in [('Placeholder Movies', 'movies', '/media/placeholders/movies'), ('Placeholder TV', 'tvshows', '/media/placeholders/tv')]:
    if not any(folder['Name'] == name for folder in folders):
        options = {'PathInfos': [{'Path': path}], 'EnableInternetProviders': False, 'EnableAutomaticSeriesGrouping': False, 'TypeOptions': [{'Type': item_type, 'MetadataFetchers': [], 'ImageFetchers': []} for item_type in ['Movie', 'Series', 'Season', 'Episode']]}
        request('/Library/VirtualFolders?' + urllib.parse.urlencode({'name': name, 'collectionType': kind, 'refreshLibrary': 'false'}), {'LibraryOptions': options}, method='POST')
request('/Library/Refresh', method='POST')
for _ in range(120):
    items = request('/Items?Recursive=true&IncludeItemTypes=Movie,Episode&Fields=Path')['Items']
    placeholders = [item for item in items if item.get('Path', '').startswith('/media/placeholders/')]
    scan = [task for task in request('/ScheduledTasks') if task['Key'] == 'RefreshLibrary']
    if len(placeholders) == len(MOVIES) + len(EPISODES) and all(task['State'] == 'Idle' for task in scan):
        break
    time.sleep(1)
else:
    raise RuntimeError(f'Scan incomplete: found {len(placeholders)} of 22 placeholders.')

by_name = {item['Name']: item for item in placeholders}
assert all(item.get('IsPlaceHolder') for item in placeholders), 'Jellyfin did not recognize .disc files as placeholders.'
season_items = {
    season: [by_name[title] for title, _, _, tag in MOVIES if tag == season] + [by_name[title] for _, title, tag in EPISODES if tag == season]
    for season in SEASONS
}
config = request('/Events/Configuration')
events = config['Events']
for title, start, end in [('Christmas', '12-01', '12-31'), ('Halloween', '10-18', '10-31')]:
    definition = next((event for event in events if event['Title'] == title), None)
    if definition is None:
        definition = {'Id': uuid.uuid5(uuid.NAMESPACE_URL, 'jellyfin-events-test/' + title).hex, 'Title': title, 'Description': '', 'Enabled': True, 'ScheduleType': 'Annual', 'StartDate': start, 'EndDate': end, 'Items': []}
        events.append(definition)
    existing = {selection['ItemId'] for selection in definition['Items']}
    definition['Items'].extend({'ItemId': item['Id'], 'Label': item['Name']} for item in season_items[title] if item['Id'] not in existing)
    if definition.get('Description') in ['', 'Development verification fixture']:
        definition['Description'] = f'{title} movies and seasonal TV episodes, including metadata-only test placeholders.'
    definition['ArtworkItemId'] = season_items[title][0]['Id']

demo_id = uuid.uuid5(uuid.NAMESPACE_URL, 'jellyfin-events-test/placeholder-spotlight').hex
if not any(event['Id'].replace('-', '') == demo_id for event in events):
    chosen = [by_name[title] for title in ['Home Alone', 'Elf', 'The Polar Express', 'Hocus Pocus', "Harry Potter and the Philosopher's Stone", 'The Christmas Party', 'The Halloween Heist']]
    events.append({'Id': demo_id, 'Title': 'Placeholder spotlight', 'Description': 'Always-active demo event for testing live discovery. Disable this event when checking seasonal date boundaries. All items are non-playable placeholders.', 'Enabled': True, 'ScheduleType': 'Annual', 'StartDate': '01-01', 'EndDate': '12-31', 'ArtworkItemId': chosen[0]['Id'], 'Items': [{'ItemId': item['Id'], 'Label': item['Name']} for item in chosen]})
request('/Events/Configuration', {'Revision': config['Revision'], 'Events': events}, method='PUT')

# Exercise the real plugin and image endpoints, not just the Jellyfin library list.
feed = request('/Events/Active')
demo = next((event for event in feed['Events'] if event['Id'] == demo_id), None)
if demo:
    demo_items = request('/Events/' + demo_id + '/Items')['Items']
    assert len(demo_items) == 7 and all(item.get('IsPlaceHolder') for item in demo_items)
    assert all(item.get('ImageTags', {}).get('Primary') for item in demo_items)
    image_id = demo_items[0]['Id']
    with urllib.request.urlopen(urllib.request.Request(BASE + '/Items/' + image_id + '/Images/Primary?maxWidth=200', headers={'Authorization': f'MediaBrowser Token="{TOKEN}"'})) as response:
        assert response.headers['Content-Type'].startswith('image/') and len(response.read()) > 100
print(f'Added {len(MOVIES)} movie and {len(EPISODES)} episode placeholders with posters.')
print('Christmas and Halloween events populated; Placeholder spotlight uses a year-round schedule.')
print('Open http://localhost:5173 and sign in with admin/admin. Refresh an existing session.')
