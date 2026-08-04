const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const TOKEN_KEY = 'logsentinel_access_token'
const USERNAME_KEY = 'logsentinel_username'

export function getAccessToken() {
  return sessionStorage.getItem(TOKEN_KEY)
}

export function getUsername() {
  return sessionStorage.getItem(USERNAME_KEY)
}

export function saveSession({ accessToken, username }) {
  sessionStorage.setItem(TOKEN_KEY, accessToken)
  sessionStorage.setItem(USERNAME_KEY, username)
}

export function clearSession() {
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(USERNAME_KEY)
}

export function getAuthHeaders() {
  const token = getAccessToken()
  if (!token) {
    return {}
  }

  return {
    Authorization: `Bearer ${token}`,
  }
}

async function parseError(response, fallback) {
  let message = fallback
  try {
    const errorBody = await response.json()
    if (typeof errorBody.detail === 'string') {
      message = errorBody.detail
    }
  } catch {
    // keep fallback
  }
  return message
}

export async function fetchAuthConfig() {
  const response = await fetch(`${API_BASE}/auth/config`)
  if (!response.ok) {
    throw new Error('Unable to load authentication settings')
  }
  return response.json()
}

export async function login(username, password) {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ username, password }),
  })

  if (!response.ok) {
    throw new Error(await parseError(response, 'Sign in failed'))
  }

  const data = await response.json()
  saveSession({ accessToken: data.access_token, username: data.username })
  return data
}

export async function validateSession() {
  const token = getAccessToken()
  if (!token) {
    return false
  }

  const response = await fetch(`${API_BASE}/auth/session`, {
    headers: getAuthHeaders(),
  })

  if (!response.ok) {
    clearSession()
    return false
  }

  return true
}

export async function analyzeLogFile(file) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
  })

  if (response.status === 401) {
    clearSession()
    throw new Error('Your session expired. Please sign in again.')
  }

  if (!response.ok) {
    throw new Error(await parseError(response, `Analysis failed (${response.status})`))
  }

  return response.json()
}
