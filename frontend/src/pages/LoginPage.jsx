import { useState } from 'react'
import { api } from '../services/api'

function LoginPage({ navigate, onAuthenticated }) {
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const updateField = (event) => {
    setForm({ ...form, [event.target.name]: event.target.value })
  }

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    if (!form.username.trim() || !form.password) {
      setError('Enter your username and password.')
      return
    }

    setIsSubmitting(true)
    try {
      const result = await api.post('/api/auth/login', {
        username: form.username.trim(),
        password: form.password,
      })
      onAuthenticated(result.user)
      navigate('/dashboard')
    } catch (requestError) {
      setError(requestError.message || 'Unable to log in. Try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="auth-page" aria-labelledby="login-title">
      <p className="eyebrow">Welcome back</p>
      <h1 id="login-title">Log in to Shortform.</h1>
      <p className="form-note">Use the username and password from your Flask account.</p>
      <form className="auth-form" onSubmit={submit}>
        <label>
          Username
          <input name="username" value={form.username} onChange={updateField} autoComplete="username" />
        </label>
        <label>
          Password
          <input name="password" type="password" value={form.password} onChange={updateField} autoComplete="current-password" />
        </label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="primary-button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Logging in...' : 'Log in'}
        </button>
      </form>
      <p className="switch-prompt">New here? <button type="button" className="text-button" onClick={() => navigate('/register')}>Create an account</button></p>
    </section>
  )
}

export default LoginPage
