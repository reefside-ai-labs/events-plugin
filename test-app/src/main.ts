import './style.css'
import { ApiError, JellyfinClient } from './api'
import type { EventItems, Feed, Item, Trace, User } from './api'

const app = document.querySelector<HTMLDivElement>('#app')!
app.innerHTML = `
  <header class="masthead"><div><span class="brand-mark" aria-hidden="true">J</span><strong>Jellyfin <span>Events</span></strong><span class="badge">Test client</span></div><button id="sign-out" hidden>Sign out</button></header>
  <main>
    <section id="login-panel" class="login-panel">
      <p class="eyebrow">Scheduled discovery</p><h1>The right stories,<br>at the right time.</h1>
      <p class="intro">Connect to Jellyfin to explore your curated events.</p>
      <form id="login-form">
        <label>Server URL<input id="server" value="/jellyfin" required autocomplete="url" spellcheck="false"></label>
        <p class="hint">/jellyfin connects to the local Docker server on port 8097.</p>
        <label>Username<input id="username" required autocomplete="username" placeholder="Username"></label>
        <label>Password<input id="password" type="password" required autocomplete="current-password" placeholder="Password"></label>
        <button class="primary" id="connect" type="submit">Connect to Jellyfin</button>
      </form>
      <p class="hint">Local fixture accounts: admin / admin, child / child, limited / limited.</p>
    </section>
    <section id="discovery" hidden>
      <div class="page-heading"><div><p class="eyebrow">Discover</p><h1>What’s in season</h1><p id="connection" class="muted"></p></div><button id="refresh">Refresh</button></div>
      <form id="preview-controls" class="toolbar" hidden>
        <label>Mode<select id="mode"><option value="live">Live events</option><option value="preview">Preview a date</option></select></label>
        <label id="date-label" hidden>Date<input id="preview-date" type="date" disabled></label>
        <label id="user-label" hidden>View as<select id="preview-user" disabled><option value="">Me</option></select></label>
        <button class="primary" type="submit">Apply</button>
      </form>
      <div class="feed-context"><span id="feed-context"></span><span id="updated"></span></div>
      <div id="events" aria-live="polite"></div>
      <details class="debug"><summary>API inspector</summary><p class="hint">Recent requests and the latest feed response. Credentials are omitted.</p><div id="requests"></div><pre id="feed-json"></pre></details>
    </section>
    <p id="status" role="status" aria-live="polite"></p>
  </main>
  <dialog id="item-dialog"><div class="dialog-heading"><h2 id="item-title"></h2><button id="close-dialog" aria-label="Close item details">Close</button></div><p id="item-description"></p><a id="item-link" class="button primary" target="_blank" rel="noopener noreferrer">Open in Jellyfin</a><details><summary>Item DTO</summary><pre id="item-json"></pre></details></dialog>
`

function el<T extends HTMLElement = HTMLElement>(id: string): T {
  return document.getElementById(id) as T
}

let client: JellyfinClient | null = null
let currentUser: User | null = null
let serverName = ''
let feedController = new AbortController()
let feedVersion = 0
let imageUrls: string[] = []
let traces: Trace[] = []
let currentFeed: Feed | null = null
// Applied mode is separate from draft controls, so background refresh cannot apply unsaved changes.
let mode: 'live' | 'preview' = 'live'
let previewDate = ''
let previewUser = ''
let previewUserName = 'Me'

function status(message = '', isError = false) {
  el('status').textContent = message
  el('status').classList.toggle('error', isError)
}

function trace(entry: Trace) {
  traces = [entry, ...traces].slice(0, 12)
  el('requests').replaceChildren(...traces.map((entry) => {
    const row = document.createElement('div')
    row.className = 'request'
    row.textContent = `${entry.status} · ${entry.path} · ${entry.duration} ms`
    return row
  }))
}

function clearFeed() {
  feedController.abort()
  feedController = new AbortController()
  feedVersion++
  imageUrls.forEach(URL.revokeObjectURL)
  imageUrls = []
  el('events').replaceChildren()
  el('feed-json').textContent = ''
  el('feed-context').textContent = ''
  el('updated').textContent = ''
  currentFeed = null
}

function disconnected() {
  clearFeed()
  client = null
  currentUser = null
  mode = 'live'
  previewUser = ''
  traces = []
  el('requests').replaceChildren()
  el('discovery').hidden = true
  el('login-panel').hidden = false
  el('sign-out').hidden = true
  el('preview-controls').hidden = true
  el<HTMLDialogElement>('item-dialog').close()
  el('item-json').textContent = ''
  el('item-link').removeAttribute('href')
}

function failure(error: unknown) {
  if (error instanceof DOMException && error.name === 'AbortError') return
  if (error instanceof ApiError && error.status === 401) {
    disconnected()
    status('Your session expired. Sign in again.', true)
    return
  }
  const message = error instanceof ApiError && error.status === 404
    ? 'The Events plugin endpoint is unavailable, or this event is no longer active. Check the plugin installation and refresh.'
    : error instanceof Error ? error.message : 'Could not reach Jellyfin.'
  status(message, true)
}

function previewQuery() {
  const query = new URLSearchParams({ date: previewDate })
  if (previewUser) query.set('userId', previewUser)
  return query
}

function itemPath(id: string, startIndex = 0) {
  const query = mode === 'preview' ? previewQuery() : new URLSearchParams()
  query.set('startIndex', String(startIndex))
  query.set('limit', '24')
  return `/Events/${mode === 'preview' ? 'Preview/' : ''}${encodeURIComponent(id)}/Items?${query}`
}

async function artwork(target: HTMLElement, itemId: string) {
  const activeClient = client
  const signal = feedController.signal
  if (!activeClient) return
  try {
    const blob = await activeClient.image(itemId, signal)
    if (!blob || signal.aborted || !target.isConnected) return
    const url = URL.createObjectURL(blob)
    imageUrls.push(url)
    const image = new Image()
    image.alt = ''
    image.src = url
    image.loading = 'lazy'
    target.prepend(image)
  } catch {
    // A missing/inaccessible image uses the existing placeholder.
  }
}

function describe(item: Item) {
  if (item.Type === 'Episode') return `${item.SeriesName || 'TV episode'} · S${String(item.ParentIndexNumber ?? 0).padStart(2, '0')}E${String(item.IndexNumber ?? 0).padStart(2, '0')}`
  return ['Movie', item.ProductionYear].filter(Boolean).join(' · ')
}

function card(item: Item) {
  const button = document.createElement('button')
  button.className = 'media-card'
  button.setAttribute('aria-label', `${item.Name} — ${describe(item)}`)
  const poster = document.createElement('div')
  poster.className = 'poster'
  const placeholder = document.createElement('span')
  placeholder.className = 'placeholder'
  placeholder.textContent = item.Type === 'Episode' ? 'TV' : 'FILM'
  poster.append(placeholder)
  const title = document.createElement('strong')
  title.textContent = item.Name
  const meta = document.createElement('span')
  meta.className = 'card-meta'
  meta.textContent = describe(item) + (item.IsPlaceHolder ? ' · Placeholder' : '') + (item.UserData?.Played ? ' · Watched' : '')
  button.append(poster, title, meta)
  button.addEventListener('click', () => {
    el('item-title').textContent = item.Name
    el('item-description').textContent = item.Overview || describe(item)
    el('item-json').textContent = JSON.stringify(item, null, 2)
    const webBase = client?.base === '/jellyfin' ? (import.meta.env.VITE_JELLYFIN_WEB_URL || 'http://localhost:8097') : client?.base
    el<HTMLAnchorElement>('item-link').href = `${webBase}/web/#/details?id=${encodeURIComponent(item.Id)}`
    el<HTMLDialogElement>('item-dialog').showModal()
  })
  if (item.ImageTags?.Primary) queueMicrotask(() => { void artwork(poster, item.Id) })
  return button
}

function eventRow(group: EventItems, version: number) {
  const section = document.createElement('section')
  section.className = 'event-row'
  const header = document.createElement('div')
  header.className = 'event-heading'
  const copy = document.createElement('div')
  const kicker = document.createElement('p')
  kicker.className = 'eyebrow'
  kicker.textContent = `${group.Event.ScheduleType === 'Annual' ? 'Every year' : 'One-time event'} · ${group.Event.StartDate} — ${group.Event.EndDate}`
  const title = document.createElement('h2')
  title.textContent = group.Event.Title
  const description = document.createElement('p')
  description.className = 'muted'
  description.textContent = group.Event.Description
  copy.append(kicker, title, description)
  header.append(copy)
  if (group.Event.ArtworkItemId) {
    const thumbnail = document.createElement('div')
    thumbnail.className = 'event-artwork'
    header.prepend(thumbnail)
    queueMicrotask(() => { void artwork(thumbnail, group.Event.ArtworkItemId!) })
  }
  const count = document.createElement('span')
  count.className = 'item-count'
  count.textContent = `${group.TotalRecordCount} ${group.TotalRecordCount === 1 ? 'item' : 'items'}`
  header.append(count)
  const grid = document.createElement('div')
  grid.className = 'media-grid'
  grid.append(...group.Items.map(card))
  const more = document.createElement('button')
  more.textContent = 'Load more'
  let loaded = group.Items.length
  more.hidden = loaded >= group.TotalRecordCount
  more.addEventListener('click', async () => {
    if (!client || version !== feedVersion) return
    more.disabled = true
    try {
      const next = await client.json<EventItems>(itemPath(group.Event.Id, loaded), { signal: feedController.signal })
      if (version !== feedVersion) return
      grid.append(...next.Items.map(card))
      loaded += next.Items.length
      more.hidden = loaded >= next.TotalRecordCount || next.Items.length === 0
    } catch (error) { failure(error) }
    finally { more.disabled = false }
  })
  section.append(header, grid, more)
  return section
}

async function refresh() {
  if (!client || !currentUser) return
  clearFeed()
  const version = feedVersion
  const activeClient = client
  const signal = feedController.signal
  status('Loading events…')
  el<HTMLButtonElement>('refresh').disabled = true
  try {
    const path = mode === 'live' ? '/Events/Active' : `/Events/Preview?${previewQuery()}`
    const feed = await activeClient.json<Feed>(path, { signal })
    if (signal.aborted) return
    currentFeed = feed
    const groups = await Promise.all(feed.Events.map(event => activeClient.json<EventItems>(itemPath(event.Id), { signal })))
    if (signal.aborted) return
    el('feed-context').textContent = `${mode === 'live' ? 'Live' : `Preview as ${previewUserName}`} · ${feed.Date} · ${feed.ServerTimeZone}`
    el('updated').textContent = `Updated ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
    el('feed-json').textContent = JSON.stringify(feed, null, 2)
    if (groups.length) el('events').append(...groups.map(group => eventRow(group, version)))
    else {
      const empty = document.createElement('div')
      empty.className = 'empty'
      const heading = document.createElement('h2')
      heading.textContent = 'Nothing in season today'
      const note = document.createElement('p')
      note.textContent = mode === 'preview' ? 'No enabled events have accessible content for this date and user.' : 'No active events have content you can access.' + (currentUser?.Policy?.IsAdministrator ? ' Preview another date above to test seasonal events.' : '')
      empty.append(heading, note)
      el('events').append(empty)
    }
    status()
  } catch (error) { if (!signal.aborted) failure(error) }
  finally { if (version === feedVersion) el<HTMLButtonElement>('refresh').disabled = false }
}

el<HTMLFormElement>('login-form').addEventListener('submit', async (event) => {
  event.preventDefault()
  el<HTMLButtonElement>('connect').disabled = true
  status('Connecting…')
  traces = []
  try {
    const base = el<HTMLInputElement>('server').value.trim().replace(/\/+$/, '')
    if (base !== '/jellyfin') {
      const url = new URL(base)
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error('Use an HTTP(S) server URL, including its base path if needed.')
    }
    client = new JellyfinClient(base, trace)
    currentUser = await client.login(el<HTMLInputElement>('username').value.trim(), el<HTMLInputElement>('password').value)
    el<HTMLInputElement>('password').value = ''
    const info = await client.json<{ ServerName: string; Version: string }>('/System/Info/Public')
    serverName = `${info.ServerName} · Jellyfin ${info.Version}`
    el('connection').textContent = `${currentUser.Name} · ${serverName}`
    el('login-panel').hidden = true
    el('discovery').hidden = false
    el('sign-out').hidden = false
    const isAdmin = !!currentUser.Policy?.IsAdministrator
    el('preview-controls').hidden = !isAdmin
    el<HTMLSelectElement>('mode').value = 'live'
    syncPreviewControls()
    el<HTMLSelectElement>('preview-user').replaceChildren(new Option('Me', ''))
    if (isAdmin) {
      const users = await client.json<User[]>('/Users')
      el<HTMLSelectElement>('preview-user').append(...users.filter(user => user.Id !== currentUser!.Id).map(user => new Option(user.Name, user.Id)))
    }
    await refresh()
    el<HTMLInputElement>('preview-date').value = currentFeed?.Date || new Date().toISOString().slice(0, 10)
  } catch (error) {
    if (error instanceof ApiError && error.status === 401 && !currentUser) {
      disconnected()
      status('Username or password not accepted.', true)
    } else failure(error)
  }
  finally { el<HTMLButtonElement>('connect').disabled = false }
})

function syncPreviewControls() {
  const isPreview = el<HTMLSelectElement>('mode').value === 'preview'
  el('date-label').hidden = !isPreview
  el('user-label').hidden = !isPreview
  el<HTMLInputElement>('preview-date').disabled = !isPreview
  el<HTMLInputElement>('preview-date').required = isPreview
  el<HTMLSelectElement>('preview-user').disabled = !isPreview
}
el('mode').addEventListener('change', syncPreviewControls)
el<HTMLFormElement>('preview-controls').addEventListener('submit', (event) => {
  event.preventDefault()
  mode = el<HTMLSelectElement>('mode').value === 'preview' ? 'preview' : 'live'
  previewDate = el<HTMLInputElement>('preview-date').value
  previewUser = el<HTMLSelectElement>('preview-user').value
  previewUserName = el<HTMLSelectElement>('preview-user').selectedOptions[0]?.textContent || 'Me'
  void refresh()
})
el('refresh').addEventListener('click', () => { void refresh() })
el('sign-out').addEventListener('click', () => {
  const oldClient = client
  disconnected()
  status('Signed out.')
  void oldClient?.json('/Sessions/Logout', { method: 'POST' }).catch(() => {}).finally(() => { if (oldClient) oldClient.token = '' })
})
el('close-dialog').addEventListener('click', () => el<HTMLDialogElement>('item-dialog').close())
window.addEventListener('focus', () => { if (client) void refresh() })
setInterval(() => { if (client && document.visibilityState === 'visible') void refresh() }, 120_000)
