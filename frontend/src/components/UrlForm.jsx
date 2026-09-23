import { useState } from 'react'

function UrlForm({ initialUrl, isSubmitting, error, onSubmit, onCancel }) {
  const [originalUrl, setOriginalUrl] = useState(initialUrl?.original_url || '')
  const [customAlias, setCustomAlias] = useState(initialUrl?.custom_alias || '')

  const submit = (event) => {
    event.preventDefault()
    if (!originalUrl.trim()) return
    onSubmit({
      original_url: originalUrl.trim(),
      ...(customAlias.trim() ? { custom_alias: customAlias.trim() } : {}),
    })
  }

  return (
    <form className="url-form" onSubmit={submit}>
      <div className="form-heading">
        <div>
          <p className="eyebrow">{initialUrl ? 'Edit link' : 'New link'}</p>
          <h2>{initialUrl ? 'Update a destination' : 'Shorten something useful'}</h2>
        </div>
        {initialUrl && <button className="text-button" type="button" onClick={onCancel}>Cancel</button>}
      </div>
      <label>
        Original URL
        <input
          type="url"
          value={originalUrl}
          onChange={(event) => setOriginalUrl(event.target.value)}
          placeholder="https://example.com/article"
          required
        />
      </label>
      <label>
        Custom alias <span className="optional-label">optional</span>
        <input
          value={customAlias}
          onChange={(event) => setCustomAlias(event.target.value)}
          placeholder="my-article"
          minLength="3"
          maxLength="50"
        />
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="primary-button" type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Saving...' : initialUrl ? 'Save changes' : 'Create short URL'}
      </button>
    </form>
  )
}

export default UrlForm
