export interface User {
  Id: string
  Name: string
  Policy?: { IsAdministrator?: boolean }
}

export interface EventSummary {
  Id: string
  Title: string
  Description: string
  ScheduleType: 'Annual' | 'OneTime'
  StartDate: string
  EndDate: string
  ArtworkItemId?: string
  ItemCount: number
}

export interface Feed {
  ServerTimeZone: string
  Date: string
  Events: EventSummary[]
}

export interface Item {
  Id: string
  Name: string
  Type: string
  ProductionYear?: number
  SeriesName?: string
  ParentIndexNumber?: number
  IndexNumber?: number
  ImageTags?: { Primary?: string }
  IsPlaceHolder?: boolean
  Overview?: string
  UserData?: { Played?: boolean }
}

export interface EventItems {
  Event: EventSummary
  Items: Item[]
  TotalRecordCount: number
  StartIndex: number
}

export interface Trace {
  path: string
  status: number | string
  duration: number
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const identity = 'MediaBrowser Client="Events Test App", Device="Browser", DeviceId="events-test-app", Version="0.1.0"'

export class JellyfinClient {
  token = ''
  readonly base: string
  private readonly onTrace: (trace: Trace) => void

  constructor(base: string, onTrace: (trace: Trace) => void) {
    this.base = base
    this.onTrace = onTrace
  }

  async json<T>(path: string, options: RequestInit = {}): Promise<T> {
    const start = performance.now()
    let status: number | string = 'Network error'
    try {
      const response = await fetch(this.base + path, {
        ...options,
        headers: {
          Authorization: identity + (this.token ? `, Token="${this.token}"` : ''),
          Accept: 'application/json',
          ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        },
      })
      status = response.status
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        const detail = body?.Errors?.join('\n') || body?.title
        throw new ApiError(response.status, detail || `Jellyfin returned ${response.status}.`)
      }
      if (response.status === 204) return undefined as T
      const type = response.headers.get('Content-Type') || ''
      if (!type.includes('json')) throw new Error('Expected Jellyfin JSON. Check the server URL or Vite proxy target.')
      return await response.json() as T
    } finally {
      if (!options.signal?.aborted) this.onTrace({ path, status, duration: Math.round(performance.now() - start) })
    }
  }

  async login(username: string, password: string): Promise<User> {
    const result = await this.json<{ AccessToken: string; User: User }>('/Users/AuthenticateByName', {
      method: 'POST', body: JSON.stringify({ Username: username, Pw: password }),
    })
    this.token = result.AccessToken
    return result.User
  }

  async image(itemId: string, signal: AbortSignal): Promise<Blob | null> {
    const response = await fetch(`${this.base}/Items/${encodeURIComponent(itemId)}/Images/Primary?maxWidth=480`, {
      headers: { Authorization: identity + `, Token="${this.token}"` }, signal,
    })
    return response.ok ? response.blob() : null
  }
}
