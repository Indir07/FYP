import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import './AuthPage.css'

async function fetchWithTimeout(input: RequestInfo | URL, init: RequestInit, timeoutMs = 12000) {
  const ctrl = new AbortController()
  const t = window.setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    return await fetch(input, { ...init, signal: ctrl.signal })
  } finally {
    window.clearTimeout(t)
  }
}

export function ResetPasswordPage() {
  const navigate = useNavigate()
  const [search] = useSearchParams()
  const token = search.get('token') ?? ''
  const hasToken = useMemo(() => token.length > 0, [token])

  const [emailOrUsername, setEmailOrUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)

  async function onRequestLink(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setInfo(null)
    setLoading(true)
    try {
      const res = await fetchWithTimeout('http://localhost:8000/api/auth/password/forgot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email_or_username: emailOrUsername.trim() }),
      })
      const j = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(j?.detail ?? 'Failed to send reset link')
      setInfo(j?.message ?? 'Password reset link sent.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send reset link')
    } finally {
      setLoading(false)
    }
  }

  async function onResetPassword(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setInfo(null)
    if (newPassword !== confirmPassword) {
      setError('Password and confirm password must match.')
      return
    }
    setLoading(true)
    try {
      const res = await fetchWithTimeout('http://localhost:8000/api/auth/password/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token,
          new_password: newPassword,
          confirm_password: confirmPassword,
        }),
      })
      const j = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(j?.detail ?? 'Failed to reset password')
      setInfo(j?.message ?? 'Password reset successful.')
      window.setTimeout(() => navigate('/login'), 900)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="cv-authWrap">
      <div className="cv-authCard">
        <div className="cv-authTitle">Reset Password</div>
        <div className="cv-authSub">
          {hasToken
            ? 'Set a new password for your CryptoVolt account.'
            : 'Enter your registered email or username to receive a reset link.'}
        </div>

        <form className="cv-authForm" onSubmit={hasToken ? onResetPassword : onRequestLink}>
          {!hasToken ? (
            <>
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
            </>
          ) : (
            <>
              <label className="cv-authLabel">
                New Password<span className="cv-authRequired">*</span>
              </label>
              <input
                className="cv-authInput"
                type="password"
                placeholder="Minimum 8 characters"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
              />

              <label className="cv-authLabel">
                Confirm Password<span className="cv-authRequired">*</span>
              </label>
              <input
                className="cv-authInput"
                type="password"
                placeholder="Re-enter password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={8}
              />
            </>
          )}

          {info ? <div className="cv-authHint">{info}</div> : null}
          {error ? <div className="cv-authError">{error}</div> : null}
          <button className="cv-authBtn" type="submit" disabled={loading}>
            {loading
              ? hasToken
                ? 'Resetting...'
                : 'Sending link...'
              : hasToken
                ? 'Reset Password'
                : 'Send Reset Link'}
          </button>
        </form>

        <div className="cv-authFooter">
          Back to <Link className="cv-authLink" to="/login">Login</Link>
        </div>
      </div>
    </div>
  )
}

