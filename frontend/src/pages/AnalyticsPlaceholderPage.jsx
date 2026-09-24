import { useEffect, useMemo, useState } from 'react'
import { ApiError, api } from '../services/api'

function formatDate(value) {
  if (!value) return 'No activity yet'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

function EmptyState({ children }) {
  return <p className="analytics-empty">{children}</p>
}

function MetricCard({ label, value, subtext }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
      {subtext && <small className="metric-subtext">{subtext}</small>}
    </article>
  )
}

function Timeline({ rows }) {
  if (!rows.length) return <EmptyState>No activity recorded over time yet.</EmptyState>
  const maximum = Math.max(...rows.map((row) => Math.max(row.clicks || 0, row.impressions || 0)), 1)

  return (
    <div className="timeline-container">
      <div className="timeline-legend">
        <span className="legend-item"><span className="legend-swatch clicks-swatch" /> Clicks</span>
        <span className="legend-item"><span className="legend-swatch impressions-swatch" /> Impressions</span>
      </div>
      <div className="timeline" aria-label="Activity over time">
        {rows.map((row) => {
          const clicksHeight = Math.max(((row.clicks || 0) / maximum) * 100, (row.clicks > 0 ? 8 : 0))
          const impressionsHeight = Math.max(((row.impressions || 0) / maximum) * 100, (row.impressions > 0 ? 8 : 0))
          return (
            <div className="timeline-column" key={row.date}>
              <div className="timeline-values">
                <span className="timeline-value" title={`Clicks: ${row.clicks}, Impressions: ${row.impressions}${row.ctr !== null ? `, CTR: ${row.ctr}%` : ''}`}>
                  {row.clicks}c / {row.impressions}i
                </span>
              </div>
              <div className="timeline-track">
                <div
                  className="timeline-bar clicks-bar"
                  style={{ height: `${clicksHeight}%` }}
                  title={`Clicks: ${row.clicks}`}
                />
                <div
                  className="timeline-bar impressions-bar"
                  style={{ height: `${impressionsHeight}%` }}
                  title={`Impressions: ${row.impressions}`}
                />
              </div>
              <time dateTime={row.date}>
                {new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(new Date(row.date))}
              </time>
            </div>
          )
        })}
      </div>
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
          <div className="breakdown-track">
            <div className="breakdown-bar" style={{ width: `${(row.clicks / maximum) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}

function GeographicBreakdown({ rows }) {
  if (!rows.length) return <EmptyState>No geographic activity recorded yet.</EmptyState>
  const maximum = Math.max(...rows.map((row) => Math.max(row.clicks || 0, row.impressions || 0)), 1)

  return (
    <div className="breakdown-list">
      {rows.map((row) => (
        <div className="breakdown-row geo-row" key={row.country}>
          <div className="breakdown-label">
            <span className="country-tag" title={row.country}>
              <strong className="country-code">{row.country}</strong>
              {row.ctr !== null && row.ctr !== undefined && (
                <span className="ctr-pill">{row.ctr}% CTR</span>
              )}
            </span>
            <div className="breakdown-counts">
              <b>{row.clicks} click{row.clicks === 1 ? '' : 's'}</b>
              <span className="sub-count">{row.impressions} imp</span>
            </div>
          </div>
          <div className="breakdown-track">
            <div
              className="breakdown-bar clicks-bar"
              style={{ width: `${((row.clicks || 0) / maximum) * 100}%` }}
              title={`Clicks: ${row.clicks}`}
            />
          </div>
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
          <div className="top-url-metrics">
            <b>{row.total_clicks} click{row.total_clicks === 1 ? '' : 's'}</b>
            <span className="sub-count">{row.total_impressions || 0} imp</span>
            {row.ctr !== null && row.ctr !== undefined ? (
              <span className="top-url-ctr">{row.ctr}% CTR</span>
            ) : (
              <span className="top-url-ctr top-url-ctr-na">No imp</span>
            )}
          </div>
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
        <div className="analytics-actions">
          <button className="secondary-button" type="button" onClick={() => navigate('/dashboard')}>
            Back to dashboard
          </button>
          <button className="primary-button" type="button" onClick={loadAnalytics}>
            Try again
          </button>
        </div>
      </section>
    )
  }

  const ctrDisplay = data.overview.ctr !== null && data.overview.ctr !== undefined
    ? `${data.overview.ctr}%`
    : 'N/A'

  const ctrSubtext = data.overview.total_impressions > 0
    ? `${data.overview.total_clicks} / ${data.overview.total_impressions}`
    : '0 impressions'

  return (
    <section className="analytics-page" aria-labelledby="analytics-title">
      <button className="back-link" type="button" onClick={() => navigate('/dashboard')}>
        ← Back to dashboard
      </button>
      <div className="analytics-heading">
        <div>
          <p className="eyebrow">Link analytics</p>
          <h1 id="analytics-title">{data.url.short_code}</h1>
          <a className="analytics-original-url" href={data.url.original_url} target="_blank" rel="noreferrer">
            {data.url.original_url}
          </a>
        </div>
        <div className="analytics-header-links">
          <a className="short-link analytics-short-url" href={data.url.short_url} target="_blank" rel="noreferrer">
            {data.url.short_url}
          </a>
          <a
            className="preview-link-badge"
            href={data.url.preview_url || `/preview/${data.url.short_code}`}
            target="_blank"
            rel="noreferrer"
            title="Public preview page that records impressions"
          >
            Preview page ↗
          </a>
        </div>
      </div>

      <div className="metric-grid">
        <MetricCard label="Total clicks" value={data.overview.total_clicks} />
        <MetricCard label="Impressions" value={data.overview.total_impressions} />
        <MetricCard label="Click-Through Rate (CTR)" value={ctrDisplay} subtext={ctrSubtext} />
        <MetricCard label="First click" value={formatDate(data.overview.first_click)} />
        <MetricCard label="Latest click" value={formatDate(data.overview.latest_click)} />
        <MetricCard label="Common device" value={deviceSummary} />
        <MetricCard label="Common referrer" value={data.overview.most_common_referrer || 'No referrer yet'} />
      </div>

      <div className="analytics-grid">
        <article className="analytics-panel timeline-panel">
          <div className="panel-heading">
            <h2>Activity over time</h2>
            <span>Daily clicks &amp; impressions</span>
          </div>
          <Timeline rows={data.timeseries} />
        </article>
        <article className="analytics-panel">
          <div className="panel-heading">
            <h2>Devices</h2>
            <span>Clicks</span>
          </div>
          <Breakdown rows={data.devices} labelKey="device_type" />
        </article>
        <article className="analytics-panel">
          <div className="panel-heading">
            <h2>Referrers</h2>
            <span>Clicks</span>
          </div>
          <Breakdown rows={data.referrers} labelKey="referrer" />
        </article>
        <article className="analytics-panel">
          <div className="panel-heading">
            <h2>Geographic distribution</h2>
            <span>Countries</span>
          </div>
          <GeographicBreakdown rows={data.countries} />
        </article>
        <article className="analytics-panel top-urls-panel">
          <div className="panel-heading">
            <h2>Top URLs</h2>
            <span>Your links</span>
          </div>
          <TopUrls rows={data.topUrls} />
        </article>
      </div>
      <p className="analytics-note">
        CTR is computed as (Clicks / Impressions) &times; 100. Impressions are recorded when visitors view the public preview page or trigger an embed pixel; direct redirects record clicks.
      </p>
    </section>
  )
}

export default AnalyticsPlaceholderPage
