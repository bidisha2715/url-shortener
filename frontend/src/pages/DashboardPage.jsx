import { useEffect, useState } from 'react'
import UrlForm from '../components/UrlForm'
import UrlList from '../components/UrlList'
import { ApiError, api } from '../services/api'

function DashboardPage({ user, onLogout, navigate }) {
  const [urls, setUrls] = useState([])
  const [clickCounts, setClickCounts] = useState({})
  const [isLoading, setIsLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [updatingId, setUpdatingId] = useState(null)
  const [deletingId, setDeletingId] = useState(null)
  const [pageError, setPageError] = useState('')
  const [formError, setFormError] = useState('')
  const [itemErrors, setItemErrors] = useState({})
  const [createFormKey, setCreateFormKey] = useState(0)

  const handleUnauthorized = (error) => {
    if (error instanceof ApiError && error.status === 401) {
      onLogout()
      navigate('/login')
      return true
    }
    return false
  }

  const loadClickCounts = async (urlRows) => {
    try {
      const summary = await api.get('/api/analytics/summary')
      const counts = {}
      for (const item of summary) {
        counts[item.id] = item.total_clicks
      }
      setClickCounts(counts)
    } catch (error) {
      if (handleUnauthorized(error)) throw error
      // Fallback to per-URL requests if summary is unavailable
      const results = await Promise.all(urlRows.map(async (url) => {
        try {
          const overview = await api.get(`/api/urls/${url.id}/analytics/overview`)
          return [url.id, overview.total_clicks]
        } catch (err) {
          if (handleUnauthorized(err)) throw err
          return [url.id, undefined]
        }
      }))
      setClickCounts(Object.fromEntries(results.filter(([, count]) => count !== undefined)))
    }
  }

  const loadUrls = async () => {
    setIsLoading(true)
    setPageError('')
    try {
      const rows = await api.get('/api/urls')
      setUrls(rows)
      await loadClickCounts(rows)
    } catch (error) {
      if (!handleUnauthorized(error)) setPageError(error.message || 'Could not load your URLs.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadUrls()
  }, [])

  const createUrl = async (data) => {
    setIsCreating(true)
    setFormError('')
    try {
      const created = await api.post('/api/urls', data)
      setUrls((current) => [created, ...current])
      setCreateFormKey((current) => current + 1)
      try {
        const overview = await api.get(`/api/urls/${created.id}/analytics/overview`)
        setClickCounts((current) => ({ ...current, [created.id]: overview.total_clicks }))
      } catch (error) {
        if (handleUnauthorized(error)) return
      }
    } catch (error) {
      if (!handleUnauthorized(error)) setFormError(error.message || 'Could not create the short URL.')
    } finally {
      setIsCreating(false)
    }
  }

  const updateUrl = async (urlId, data, finishEditing) => {
    setUpdatingId(urlId)
    setItemErrors((current) => ({ ...current, [urlId]: '' }))
    try {
      const updated = await api.put(`/api/urls/${urlId}`, data)
      setUrls((current) => current.map((url) => (url.id === urlId ? updated : url)))
      finishEditing()
    } catch (error) {
      if (!handleUnauthorized(error)) setItemErrors((current) => ({ ...current, [urlId]: error.message || 'Could not update this URL.' }))
    } finally {
      setUpdatingId(null)
    }
  }

  const deleteUrl = async (urlId) => {
    const target = urls.find((url) => url.id === urlId)
    if (!target || !window.confirm(`Delete ${target.short_code}? This cannot be undone.`)) return

    setDeletingId(urlId)
    setItemErrors((current) => ({ ...current, [urlId]: '' }))
    try {
      await api.delete(`/api/urls/${urlId}`)
      setUrls((current) => current.filter((url) => url.id !== urlId))
      setClickCounts((current) => {
        const next = { ...current }
        delete next[urlId]
        return next
      })
    } catch (error) {
      if (!handleUnauthorized(error)) setItemErrors((current) => ({ ...current, [urlId]: error.message || 'Could not delete this URL.' }))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <section className="dashboard-page dashboard-content" aria-labelledby="dashboard-title">
      <div className="dashboard-heading">
        <div>
          <p className="eyebrow">Private workspace</p>
          <h1 id="dashboard-title">Your short URLs.</h1>
          <p className="intro">Create, edit, and keep track of the links you own.</p>
        </div>
        <p className="signed-in-label">Signed in as {user?.username || 'your account'}</p>
      </div>

      <UrlForm key={createFormKey} isSubmitting={isCreating} error={formError} onSubmit={createUrl} />

      <div className="url-section-heading">
        <h2>Your links</h2>
        {!isLoading && <span>{urls.length} link{urls.length === 1 ? '' : 's'}</span>}
      </div>
      {isLoading && <p className="route-message">Loading your URLs...</p>}
      {pageError && <p className="form-error" role="alert">{pageError}</p>}
      {!isLoading && !pageError && (
        <UrlList
          urls={urls}
          clickCounts={clickCounts}
          updatingId={updatingId}
          deletingId={deletingId}
          errors={itemErrors}
          onUpdate={updateUrl}
          onDelete={deleteUrl}
          onAnalytics={(urlId) => navigate(`/analytics/${urlId}`)}
        />
      )}
    </section>
  )
}

export default DashboardPage
