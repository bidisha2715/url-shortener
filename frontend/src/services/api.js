const apiRequest = async (path, options = {}) => {
  const response = await fetch(path, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })

  const contentType = response.headers.get('content-type') || ''
  const body = contentType.includes('application/json')
    ? await response.json()
    : await response.text()

  if (!response.ok) {
    const message = typeof body === 'object' && body?.error
      ? body.error
      : `Request failed with status ${response.status}`
    throw new Error(message)
  }

  return body
}

export const api = {
  request: apiRequest,
  get: (path) => apiRequest(path),
  post: (path, data) => apiRequest(path, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
}
