import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import './AuthPage.css'
import { setAuth } from '../lib/auth'

export function LoginPage() {
  const navigate = useNavigate()
  const [emailOrUsername, setEmailOrUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await fetch('http://localhost:8000/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email_or_username: emailOrUsername.trim(),
          password,
        }),
      })
      if (!res.ok) {
        const j = await res.json().catch(() => null)
        throw new Error(j?.detail ?? 'Login failed')
      }
      const j = await res.json()
      setAuth(j.token, j.user)
      navigate('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="cv-authWrap">
      <div className="cv-authCard">
        <div className="cv-authTitle">Login</div>
        <div className="cv-authSub">Access your CryptoVolt operator account.</div>

        <form className="cv-authForm" onSubmit={onSubmit}>
          <label className="cv-authLabel">
            Email or Username<span className="cv-authRequired">*</span>
          </label>
          <input
            className="cv-authInput"
            type="text"
            placeholder="name@example.com or trader01"
            value={emailOrUsername}
            onChange={(e) => setEmailOrUsername(e.target.value)}
            required
          />

          <label className="cv-authLabel">
            Password<span className="cv-authRequired">*</span>
          </label>
          <input
            className="cv-authInput"
            type="password"
            placeholder="Minimum 8 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />

          {error ? <div className="cv-authError">{error}</div> : null}
          <button className="cv-authBtn" type="submit" disabled={loading}>
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <div className="cv-authFooter">
          New user? <Link className="cv-authLink" to="/signup">Create account</Link>
        </div>
      </div>
    </div>
  )
}

