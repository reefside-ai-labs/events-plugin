#!/usr/bin/env python3
"""Set up and verify ONLY the disposable events-jellyfin development container.

Creates admin/admin, limited/limited, child/child and local fixture events.
Leaves example events installed for manual inspection. Never use against a real server.
"""
import copy
import datetime
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parent
BASE = 'http://localhost:8097'
PLUGIN = '74fd27c8-721c-462b-a5f8-356cc7e01d62'
TOKEN = None
CHECKS = []


def request(path, data=None, method=None, token='admin', expected=200):
    credential = TOKEN if token == 'admin' else token
    headers = {'Authorization': 'MediaBrowser Client="events-verification", Device="CLI", DeviceId="events-verification", Version="1.0"'}
    if credential:
        headers['Authorization'] += f', Token="{credential}"'
    if data is not None:
        headers['Content-Type'] = 'application/json'
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE + path, data=None if data is None else json.dumps(data).encode(), headers=headers, method=method), timeout=30) as response:
            status, body = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, body = error.code, error.read()
    assert status == expected, f'{method or "GET"} {path}: expected {expected}, received {status}: {body[:600]!r}'
    if body and status == 200:
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return body.decode()
    return None


def check(name, condition):
    assert condition, name
    CHECKS.append(name)
    print('PASS ' + name, flush=True)


def wait_ready():
    for _ in range(90):
        try:
            return request('/System/Info/Public', token=None)
        except (OSError, AssertionError):
            time.sleep(1)
    raise AssertionError('Server did not become ready')


def login(name):
    # Public info can respond before startup has finished initializing auth.
    for attempt in range(60):
        try:
            return request('/Users/AuthenticateByName', {'Username': name, 'Pw': name}, token=None)['AccessToken']
        except (OSError, AssertionError):
            if attempt == 59:
                raise
            time.sleep(1)
    raise AssertionError('Authentication did not become ready')


def save(events, expected=200, revision=None):
    if revision is None:
        revision = request('/Events/Configuration')['Revision']
    return request('/Events/Configuration', {'Revision': revision, 'Events': events}, method='PUT', expected=expected)


def preview(date, user=None):
    return request('/Events/Preview?date=' + date + (('&userId=' + user) if user else ''))


def event(title, start, end, items, schedule='Annual', enabled=True, artwork=None):
    return {'Id': uuid.uuid4().hex, 'Title': title, 'Description': 'Development verification fixture', 'Enabled': enabled,
            'ScheduleType': schedule, 'StartDate': start, 'EndDate': end, 'ArtworkItemId': artwork,
            'Items': [{'ItemId': item['Id'], 'Label': item['Name']} for item in items]}


info = wait_ready()
if not info['StartupWizardCompleted']:
    request('/Startup/Configuration', {'UICulture': 'en-US', 'MetadataCountryCode': 'US', 'PreferredMetadataLanguage': 'en'}, expected=204, token=None)
    request('/Startup/User', token=None)
    request('/Startup/User', {'Name': 'admin', 'Password': 'admin'}, expected=204, token=None)
    request('/Startup/Complete', method='POST', expected=204, token=None)
TOKEN = login('admin')
(ROOT / 'data/admin-token').write_text(TOKEN)
plugins = request('/Plugins')
plugin = next(p for p in plugins if p['Id'] == PLUGIN.replace('-', ''))
check('Plugin loaded and active', plugin['Status'] == 'Active')
check('Installed on Jellyfin 12.1.0 latest image', info['Version'] == '12.1.0')

folders = request('/Library/VirtualFolders')
for name, kind, path in [('Movies', 'movies', '/media/movies'), ('TV', 'tvshows', '/media/tv')]:
    if not any(folder['Name'] == name for folder in folders):
        options = {'PathInfos': [{'Path': path}], 'EnableInternetProviders': False, 'EnableAutomaticSeriesGrouping': False,
                   'TypeOptions': [{'Type': item_type, 'MetadataFetchers': [], 'ImageFetchers': []} for item_type in ['Movie', 'Series', 'Season', 'Episode']]}
        request('/Library/VirtualFolders?name=' + name + '&collectionType=' + kind + '&refreshLibrary=false', {'LibraryOptions': options}, method='POST', expected=204)
request('/Library/Refresh', method='POST', expected=204)
for _ in range(90):
    # Additional placeholder libraries may coexist with the three playable fixtures.
    items = [item for item in request('/Items?Recursive=true&IncludeItemTypes=Movie,Episode')['Items']
             if item['Name'] in {'Christmas Movie', 'Harry Potter Example', 'Christmas Episode'}]
    if len(items) >= 3 and all(task['State'] == 'Idle' for task in request('/ScheduledTasks') if task['Key'] == 'RefreshLibrary'):
        break
    time.sleep(1)
else:
    raise AssertionError('Media scan did not finish')
christmas_movie = next(item for item in items if item['Name'] == 'Christmas Movie')
harry = next(item for item in items if item['Name'] == 'Harry Potter Example')
episode = next(item for item in items if item['Type'] == 'Episode')
check('Movie and individual episode fixtures discovered', len(items) == 3)

users = request('/Users')
for name in ['limited', 'child']:
    if not any(user['Name'] == name for user in users):
        request('/Users/New', {'Name': name, 'Password': name})
users = request('/Users')
limited_user = next(user for user in users if user['Name'] == 'limited')
child_user = next(user for user in users if user['Name'] == 'child')
limited_policy = limited_user['Policy']
limited_policy.update(EnableAllFolders=False, EnabledFolders=[])
request('/Users/' + limited_user['Id'] + '/Policy', limited_policy, method='POST', expected=204)
child_policy = child_user['Policy']
child_policy.update(MaxParentalRating=5, EnableAllFolders=True, BlockUnratedItems=['Movie', 'Series'])
request('/Users/' + child_user['Id'] + '/Policy', child_policy, method='POST', expected=204)
limited_token, child_token = login('limited'), login('child')
(ROOT / 'data/limited-token').write_text(limited_token)

missing = {'Id': uuid.uuid4().hex, 'Name': 'Deleted movie (saved label)'}
christmas = event('Christmas', '12-01', '12-31', [christmas_movie, episode, christmas_movie, missing], artwork=christmas_movie['Id'])
halloween = event('Halloween', '10-18', '10-31', [harry, christmas_movie], artwork=harry['Id'])
overlap = event('Winter favorites', '12-15', '01-05', [harry])
disabled = event('Disabled event', '01-01', '12-31', [harry], enabled=False)
once = event('One-time leap-day marathon', '2028-02-29', '2028-03-01', [harry], 'OneTime')
empty = event('Empty event', '01-01', '12-31', [])
events = [christmas, halloween, overlap, disabled, once, empty]
config = save(events)
check('Server timezone follows container location', config['ServerTimeZone'] == 'America/Denver')
check('Duplicate selections removed preserving order', [x['ItemId'] for x in config['Events'][0]['Items']] == [christmas_movie['Id'], episode['Id'], missing['Id']])
check('Overlapping schedules warn without blocking save', any(w['FirstTitle'] == 'Christmas' and w['SecondTitle'] == 'Winter favorites' for w in config['Warnings']) and not any('Disabled event' in (w['FirstTitle'], w['SecondTitle']) for w in config['Warnings']))
check('Missing selections retain repair label', config['Diagnostics'][0]['Items'][-1]['Status'] == 'Missing' and config['Diagnostics'][0]['Items'][-1]['Label'] == missing['Name'])

for date, titles in [('2026-11-30', []), ('2026-12-01', ['Christmas']), ('2026-12-31', ['Christmas', 'Winter favorites']), ('2027-01-01', ['Winter favorites']), ('2027-01-05', ['Winter favorites']), ('2027-01-06', []), ('2028-02-29', ['One-time leap-day marathon']), ('2029-03-01', []), ('2026-10-18', ['Halloween'])]:
    check('Preview date ' + date, [x['Title'] for x in preview(date)['Events']] == titles)

december = request('/Events/Preview/' + christmas['Id'] + '/Items?date=2026-12-15')
check('Movies and episodes returned in curator order; missing skipped', [x['Id'] for x in december['Items']] == [christmas_movie['Id'], episode['Id']])
check('Standard Jellyfin image tags returned', 'Primary' in december['Items'][0].get('ImageTags', {}))
check('Episode DTO includes series and episode metadata', december['Items'][1]['SeriesName'] == 'Example Show' and december['Items'][1]['IndexNumber'] == 1)
page = request('/Events/Preview/' + christmas['Id'] + '/Items?date=2026-12-15&startIndex=1&limit=1')
check('Pagination preserves filtered order and total', len(page['Items']) == 1 and page['Items'][0]['Id'] == episode['Id'] and page['TotalRecordCount'] == 2)
request('/Events/Preview/' + christmas['Id'] + '/Items?date=2026-12-15&limit=0', expected=400)
request('/Events/Preview/' + christmas['Id'] + '/Items?date=2026-07-01', expected=404)
request('/Events/Preview', expected=400)
check('Invalid pagination, missing preview date, and inactive event rejected', True)
check('Library-restricted viewer sees no events', preview('2026-12-15', limited_user['Id'])['Events'] == [])
child = preview('2026-10-20', child_user['Id'])
check('Parental restriction filters membership and artwork', len(child['Events']) == 1 and child['Events'][0]['ItemCount'] == 1 and 'ArtworkItemId' not in child['Events'][0])
child_items = request('/Events/Preview/' + halloween['Id'] + '/Items?date=2026-10-20&userId=' + child_user['Id'])
check('Parental-restricted item cannot be retrieved from event', [x['Id'] for x in child_items['Items']] == [christmas_movie['Id']])

# A temporary all-year event exercises viewer endpoints regardless of today's date.
all_year = event('API verification', '01-01', '12-31', [harry, christmas_movie], artwork=harry['Id'])
save([all_year])
feed = request('/Events/Active')
check('Active endpoint uses server-local current date', feed['Date'] == config['Date'] and feed['Events'][0]['Title'] == 'API verification')
check('Restricted active feed omits empty events', request('/Events/Active', token=limited_token)['Events'] == [])
request('/Events/' + all_year['Id'] + '/Items', token=limited_token, expected=404)
check('Restricted item endpoint returns 404', True)
check('Child active feed respects parental controls', request('/Events/Active', token=child_token)['Events'][0]['ItemCount'] == 1)
request('/Events/Active', token=None, expected=401)
request('/Events/' + all_year['Id'] + '/Items', token=None, expected=401)
for path, method in [('/Events/Configuration', None), ('/Events/Configuration', 'PUT'), ('/Events/Preview?date=2026-12-15', None), ('/Events/Validate', 'POST'), ('/Events/Search?term=Christmas', None)]:
    request(path, data={'Revision': 0, 'Events': []} if method else None, method=method, token=limited_token, expected=403)
check('Anonymous viewers and non-admin management denied', True)
search = request('/Events/Search?term=Christmas')
check('Administrator search finds movie and episode', {x['Type'] for x in search} == {'Movie', 'Episode'})

invalid = copy.deepcopy(events)
invalid[0]['StartDate'] = '02-29'
save(invalid, expected=400)
invalid[0]['StartDate'] = '12-01'
invalid[0]['ScheduleType'] = 'Weekly'
save(invalid, expected=400)
save([events[0], events[0]], expected=400)
save(events, expected=409, revision=-1)
check('Validation and stale-edit conflict enforced', True)
config = save(events)
reordered = copy.deepcopy(events)
reordered[0], reordered[2] = reordered[2], reordered[0]
save(reordered)
check('Event order follows administrator list order', [x['Title'] for x in preview('2026-12-20')['Events']] == ['Winter favorites', 'Christmas'])
config = save(events)
admin_user = next(user for user in users if user['Name'] == 'admin')
request('/Users/' + admin_user['Id'] + '/PlayedItems/' + christmas_movie['Id'], method='POST')
watched = request('/Events/Preview/' + christmas['Id'] + '/Items?date=2026-12-15')
check('Watched media remains eligible', watched['Items'][0]['Id'] == christmas_movie['Id'] and watched['Items'][0]['UserData']['Played'])
revision = config['Revision']
subprocess.run(['docker', 'compose', '-f', str(ROOT / 'docker-compose.yml'), 'restart'], check=True, stdout=subprocess.DEVNULL)
wait_ready()
TOKEN = login('admin')
(ROOT / 'data/admin-token').write_text(TOKEN)
persisted = request('/Events/Configuration')
check('Events and revision persist across server restart', persisted['Revision'] == revision and persisted['Events'] == config['Events'])
check('Plugin still active after restart', next(p for p in request('/Plugins') if p['Id'] == PLUGIN.replace('-', ''))['Status'] == 'Active')
html = request('/web/ConfigurationPage?name=Events')
check('Embedded plugin settings page served', 'events-preview-user' in html and 'events-search-button' in html)

digest = json.loads(subprocess.check_output(['docker', 'image', 'inspect', 'jellyfin/jellyfin:latest']))[0]['RepoDigests'][0]
report = {'VerifiedAtUtc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'Image': 'jellyfin/jellyfin:latest', 'Digest': digest, 'ServerVersion': info['Version'], 'Checks': CHECKS}
(ROOT.parent / 'artifacts/verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'All {len(CHECKS)} integration checks passed. Example events remain installed at {BASE}/web/.')
