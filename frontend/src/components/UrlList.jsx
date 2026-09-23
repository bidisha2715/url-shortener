import UrlCard from './UrlCard'

function UrlList({ urls, clickCounts, updatingId, deletingId, errors, onUpdate, onDelete, onAnalytics }) {
  if (urls.length === 0) {
    return <p className="empty-state">No short URLs yet. Create your first one above.</p>
  }

  return (
    <div className="url-list">
      {urls.map((url) => (
        <UrlCard
          key={url.id}
          url={url}
          clickCount={clickCounts[url.id]}
          isUpdating={updatingId === url.id}
          isDeleting={deletingId === url.id}
          error={errors[url.id]}
          onUpdate={onUpdate}
          onDelete={onDelete}
          onAnalytics={onAnalytics}
        />
      ))}
    </div>
  )
}

export default UrlList
