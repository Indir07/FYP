import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import './AuthPage.css'
import { setAuth } from '../lib/auth'

async function fetchWithTimeout(input: RequestInfo | URL, init: RequestInit, timeoutMs = 12000) {
  const ctrl = new AbortController()
  const t = window.setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    return await fetch(input, { ...init, signal: ctrl.signal })
  } finally {
    window.clearTimeout(t)
  }
}

export function LoginPage() {
  const navigate = useNavigate()
  const [emailOrUsername, setEmailOrUsername] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [challengeId, setChallengeId] = useState<number | null>(null)
  const [phase, setPhase] = useState<'request' | 'verify'>('request')
  const [resendIn, setResendIn] = useState(0)
  const [info, setInfo] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setInfo(null)
    setLoading(true)
    try {
      const res = await fetchWithTimeout('http://localhost:8000/api/auth/login/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email_or_username: emailOrUsername.trim(),
          password,
          device_label: navigator.userAgent.slice(0, 100),
        }),
      })
      if (!res.ok) {
        const j = await res.json().catch(() => null)
        throw new Error(j?.detail ?? 'Login failed')
      }
      const j = await res.json()
      setChallengeId(j.challenge_id)
      setInfo(j?.message ?? 'Verification code sent.')
      setPhase('verify')
      setResendIn(60)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  async function onVerify(e: FormEvent) {
    e.preventDefault()
    if (!challengeId) return
    setError(null)
    setLoading(true)
    try {
      const res = await fetchWithTimeout('http://localhost:8000/api/auth/login/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          challenge_id: challengeId,
          code: code.trim(),
        }),
      })
      if (!res.ok) {
        const j = await res.json().catch(() => null)
        throw new Error(j?.detail ?? 'Verification failed')
      }
      const j = await res.json()
      setAuth(j.token, j.user)
      navigate('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed')
    } finally {
      setLoading(false)
    }
  }

  async function resendCode() {
    if (!challengeId) return
    setError(null)
    setInfo(null)
    try {
      const res = await fetchWithTimeout('http://localhost:8000/api/auth/login/resend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ challenge_id: challengeId }),
      })
      const j = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(j?.detail ?? 'Failed to resend code')
      setInfo(j?.message ?? 'Code resent')
      setResendIn(60)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resend code')
    }
  }

  useEffect(() => {
    if (resendIn <= 0) return
    const t = window.setInterval(() => setResendIn((s) => (s > 0 ? s - 1 : 0)), 1000)
    return () => window.clearInterval(t)
  }, [resendIn])

  return (
    <div className="cv-authWrap">
      <div className="cv-authCard">
        <div className="cv-authTitle">Login</div>
        <div className="cv-authSub">Access your CryptoVolt operator account.</div>

        <form className="cv-authForm" onSubmit={phase === 'request' ? onSubmit : onVerify}>
          {phase === 'request' ? (
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
              <div className="cv-authInlineRow">
                <Link className="cv-authLink" to="/reset-password">Forgot password?</Link>
              </div>
            </>
          ) : (
            <>
              <div className="cv-authHint">Verification code sent to your email.</div>
              <label className="cv-authLabel">
                Login Verification Code<span className="cv-authRequired">*</span>
              </label>
              <input
                className="cv-authInput"
                type="text"
                placeholder="6-digit code, e.g., 123456"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                minLength={6}
                maxLength={6}
              />
              <div className="cv-authInlineRow">
                <button
                  type="button"
                  className="cv-authResendBtn"
                  onClick={() => void resendCode()}
                  disabled={resendIn > 0}
                >
                  {resendIn > 0 ? `Resend in ${resendIn}s` : 'Resend code'}
                </button>
              </div>
            </>
          )}

          {info ? <div className="cv-authHint">{info}</div> : null}
          {error ? <div className="cv-authError">{error}</div> : null}
          <button className="cv-authBtn" type="submit" disabled={loading}>
            {loading ? (phase === 'request' ? 'Sending code...' : 'Verifying...') : phase === 'request' ? 'Send Login Code' : 'Verify & Login'}
          </button>
        </form>

        <div className="cv-authFooter">
          New user? <Link className="cv-authLink" to="/signup">Create account</Link>
        </div>
      </div>
    </div>
  )
}

