import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import './AuthPage.css'
import { setAuth } from '../lib/auth'

export function SignupPage() {
  const navigate = useNavigate()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const strength =
    password.length >= 12 && /[A-Z]/.test(password) && /[0-9]/.test(password) && /[^A-Za-z0-9]/.test(password)
      ? 'Strong'
      : password.length >= 8
        ? 'Medium'
        : 'Weak'

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (password !== confirmPassword) {
      setError('Password and confirm password must match.')
      return
    }
    setLoading(true)
    try {
      const res = await fetch('http://localhost:8000/api/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: fullName.trim(),
          email: email.trim(),
          username: username.trim(),
          password,
        }),
      })
      if (!res.ok) {
        const j = await res.json().catch(() => null)
        throw new Error(j?.detail ?? 'Signup failed')
      }
      const j = await res.json()
      setAuth(j.token, j.user)
      navigate('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Signup failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="cv-authWrap">
      <div className="cv-authCard">
        <div className="cv-authTitle">Sign Up</div>
        <div className="cv-authSub">Create your account to access trading controls.</div>

        <form className="cv-authForm" onSubmit={onSubmit}>
          <label className="cv-authLabel">
            Full Name<span className="cv-authRequired">*</span>
          </label>
          <input
            className="cv-authInput"
            type="text"
            placeholder="e.g., John Smith"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
          />

          <label className="cv-authLabel">
            Email<span className="cv-authRequired">*</span>
          </label>
          <input
            className="cv-authInput"
            type="email"
            placeholder="name@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <label className="cv-authLabel">
            Username<span className="cv-authRequired">*</span>
          </label>
          <input
            className="cv-authInput"
            type="text"
            placeholder="3-50 chars, e.g., trader01"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            minLength={3}
            maxLength={50}
          />

          <label className="cv-authLabel">
            Password<span className="cv-authRequired">*</span>
          </label>
          <input
            className="cv-authInput"
            type="password"
            placeholder="Min 8 chars, include number and symbol"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
          <div className="cv-authHint">Password strength: {strength}</div>

          <label className="cv-authLabel">
            Confirm Password<span className="cv-authRequired">*</span>
          </label>
          <input
            className="cv-authInput"
            type="password"
            placeholder="Re-enter the same password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            minLength={8}
          />

          {error ? <div className="cv-authError">{error}</div> : null}
          <button className="cv-authBtn" type="submit" disabled={loading}>
            {loading ? 'Creating account...' : 'Create Account'}
          </button>
        </form>

        <div className="cv-authFooter">
          Already have an account? <Link className="cv-authLink" to="/login">Login</Link>
        </div>
      </div>
    </div>
  )
}

