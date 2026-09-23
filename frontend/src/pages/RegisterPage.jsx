import { useState } from 'react'
import { api } from '../services/api'

function RegisterPage({ navigate, onAuthenticated }) {
  const [form, setForm] = useState({ username: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const updateField = (event) => {
    setForm({ ...form, [event.target.name]: event.target.value })
  }

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    if (!form.username.trim() || !form.email.trim() || !form.password) {
      setError('Enter a username, email, and password.')
      return
    }
    if (form.password.length < 8) {
      setError('Your password must be at least 8 characters.')
      return
    }

    setIsSubmitting(true)
    try {
      const result = await api.post('/api/auth/register', {
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
      })
      onAuthenticated(result.user)
      navigate('/dashboard')
    } catch (requestError) {
      setError(requestError.message || 'Unable to create your account. Try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="auth-page" aria-labelledby="register-title">
      <p className="eyebrow">Start shortening</p>
      <h1 id="register-title">Make your first short link.</h1>
      <p className="form-note">Create an account to manage your links and their analytics.</p>
      <form className="auth-form" onSubmit={submit}>
        <label>
          Username
          <input name="username" value={form.username} onChange={updateField} autoComplete="username" />
        </label>
        <label>
          Email
          <input name="email" type="email" value={form.email} onChange={updateField} autoComplete="email" />
        </label>
        <label>
          Password
          <input name="password" type="password" value={form.password} onChange={updateField} autoComplete="new-password" />
        </label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="primary-button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Creating account...' : 'Create account'}
        </button>
      </form>
      <p className="switch-prompt">Already have an account? <button type="button" className="text-button" onClick={() => navigate('/login')}>Log in</button></p>
    </section>
  )
}

export default RegisterPage
