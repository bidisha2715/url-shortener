import { useEffect, useMemo, useState } from 'react'
import { ApiError, api } from '../services/api'

function formatDate(value) {
  if (!value) return 'No clicks yet'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

function EmptyState({ children }) {
  return <p className="analytics-empty">{children}</p>
}

function MetricCard({ label, value }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  )
}

function Timeline({ rows }) {
  const maximum = Math.max(...rows.map((row) => row.clicks), 1)
  if (!rows.length) return <EmptyState>No clicks recorded over time yet.</EmptyState>

  return (
    <div className="timeline" aria-label="Clicks over time">
      {rows.map((row) => (
        <div className="timeline-column" key={row.date}>
          <span className="timeline-value">{row.clicks}</span>
          <div className="timeline-track">
            <div className="timeline-bar" style={{ height: `${Math.max((row.clicks / maximum) * 100, 6)}%` }} />
          </div>
          <time dateTime={row.date}>{new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(new Date(row.date))}</time>
        </div>
      ))}
    </div>
  )
}

function Breakdown({ rows, labelKey }) {
  if (!rows.length) return <EmptyState>No data available yet.</EmptyState>
  const maximum = Math.max(...rows.map((row) => row.clicks), 1)

  return (
    <div className="breakdown-list">
      {rows.map((row) => (
        <div className="breakdown-row" key={row[labelKey]}>
          <div className="breakdown-label">
            <span title={row[labelKey]}>{row[labelKey]}</span>
            <strong>{row.clicks}</strong>
          </div>
          <div className="breakdown-track"><div className="breakdown-bar" style={{ width: `${(row.clicks / maximum) * 100}%` }} /></div>
        </div>
      ))}
    </div>
  )
}

function TopUrls({ rows }) {
  if (!rows.length) return <EmptyState>No URLs available yet.</EmptyState>
  return (
    <div className="top-url-list">
      {rows.map((row) => (
        <div className="top-url-row" key={row.short_code}>
          <div>
            <strong>{row.short_code}</strong>
            <span title={row.original_url}>{row.original_url}</span>
          </div>
          <b>{row.total_clicks} click{row.total_clicks === 1 ? '' : 's'}</b>
        </div>
      ))}
    </div>
  )
}

function AnalyticsPlaceholderPage({ navigate }) {
  const urlId = window.location.pathname.split('/').pop()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(true)

  const loadAnalytics = async () => {
    setIsLoading(true)
    setError('')
    try {
      const [url, overview, timeseries, devices, referrers, countries, topUrls] = await Promise.all([
        api.get(`/api/urls/${urlId}`),
        api.get(`/api/urls/${urlId}/analytics/overview`),
        api.get(`/api/urls/${urlId}/analytics/timeseries`),
        api.get(`/api/urls/${urlId}/analytics/devices`),
        api.get(`/api/urls/${urlId}/analytics/referrers`),
        api.get(`/api/urls/${urlId}/analytics/countries`),
        api.get('/api/analytics/urls/top'),
      ])
      setData({ url, overview, timeseries, devices, referrers, countries, topUrls })
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        navigate('/login')
      } else if (requestError instanceof ApiError && requestError.status === 403) {
        setError('You do not have permission to view this URL analytics.')
      } else {
        setError(requestError.message || 'Could not load analytics. Please try again.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadAnalytics()
  }, [urlId])

  const deviceSummary = useMemo(() => data?.overview?.most_common_device_type || 'No clicks yet', [data])
  if (isLoading) return <p className="route-message">Loading analytics...</p>
  if (error) {
    return (
      <section className="analytics-page" aria-labelledby="analytics-error-title">
        <p className="eyebrow">Analytics</p>
        <h1 id="analytics-error-title">Analytics unavailable.</h1>
        <p className="form-error" role="alert">{error}</p>
        <div className="analytics-actions"><button className="secondary-button" type="button" onClick={() => navigate('/dashboard')}>Back to dashboard</button><button className="primary-button" type="button" onClick={loadAnalytics}>Try again</button></div>
      </section>
    )
  }

  return (
    <section className="analytics-page" aria-labelledby="analytics-title">
      <button className="back-link" type="button" onClick={() => navigate('/dashboard')}>← Back to dashboard</button>
      <div className="analytics-heading">
        <div>
          <p className="eyebrow">Link analytics</p>
          <h1 id="analytics-title">{data.url.short_code}</h1>
          <a className="analytics-original-url" href={data.url.original_url} target="_blank" rel="noreferrer">{data.url.original_url}</a>
        </div>
        <a className="short-link analytics-short-url" href={data.url.short_url} target="_blank" rel="noreferrer">{data.url.short_url}</a>
      </div>

      <div className="metric-grid">
        <MetricCard label="Total clicks" value={data.overview.total_clicks} />
        <MetricCard label="First click" value={formatDate(data.overview.first_click)} />
        <MetricCard label="Latest click" value={formatDate(data.overview.latest_click)} />
        <MetricCard label="Common device" value={deviceSummary} />
        <MetricCard label="Common referrer" value={data.overview.most_common_referrer || 'No referrer yet'} />
      </div>

      <div className="analytics-grid">
        <article className="analytics-panel timeline-panel"><div className="panel-heading"><h2>Clicks over time</h2><span>Daily</span></div><Timeline rows={data.timeseries} /></article>
        <article className="analytics-panel"><div className="panel-heading"><h2>Devices</h2><span>Clicks</span></div><Breakdown rows={data.devices} labelKey="device_type" /></article>
        <article className="analytics-panel"><div className="panel-heading"><h2>Referrers</h2><span>Clicks</span></div><Breakdown rows={data.referrers} labelKey="referrer" /></article>
        <article className="analytics-panel"><div className="panel-heading"><h2>Countries</h2><span>Clicks</span></div>{data.countries.length ? <Breakdown rows={data.countries} labelKey="country" /> : <EmptyState>No geographic data available. A real geolocation provider is required.</EmptyState>}</article>
        <article className="analytics-panel top-urls-panel"><div className="panel-heading"><h2>Top URLs</h2><span>Your links</span></div><TopUrls rows={data.topUrls} /></article>
      </div>
      <p className="analytics-note">CTR is not shown because the current data model records clicks but does not define impressions.</p>
    </section>
  )
}

export default AnalyticsPlaceholderPage
