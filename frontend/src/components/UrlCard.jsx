import { useState } from 'react'
import UrlForm from './UrlForm'

function formatDate(value) {
  if (!value) return 'Date unavailable'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value))
}

function UrlCard({ url, clickCount, isUpdating, isDeleting, error, onUpdate, onDelete, onAnalytics }) {
  const [isEditing, setIsEditing] = useState(false)

  if (isEditing) {
    return (
      <article className="url-card edit-card">
        <UrlForm
          initialUrl={url}
          isSubmitting={isUpdating}
          error={error}
          onSubmit={(data) => onUpdate(url.id, data, () => setIsEditing(false))}
          onCancel={() => setIsEditing(false)}
        />
      </article>
    )
  }

  return (
    <article className="url-card">
      <div className="url-card-main">
        <div className="url-card-title-row">
          <a className="short-link" href={url.short_url} target="_blank" rel="noreferrer">{url.short_code}</a>
          {url.custom_alias && <span className="alias-label">custom alias</span>}
        </div>
        <a className="original-link" href={url.original_url} target="_blank" rel="noreferrer">{url.original_url}</a>
        <p className="url-meta">
          Created {formatDate(url.created_at)} <span aria-hidden="true">·</span> {clickCount === undefined ? 'Clicks unavailable' : `${clickCount} click${clickCount === 1 ? '' : 's'}`}
        </p>
      </div>
      <div className="url-card-actions">
        <button className="text-button" type="button" onClick={() => onAnalytics(url.id)}>View Analytics</button>
        <button className="text-button" type="button" onClick={() => setIsEditing(true)}>Edit</button>
        <button className="danger-button" type="button" onClick={() => onDelete(url.id)} disabled={isDeleting}>
          {isDeleting ? 'Deleting...' : 'Delete'}
        </button>
      </div>
    </article>
  )
}

export default UrlCard
