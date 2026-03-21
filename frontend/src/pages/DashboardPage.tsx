import { useEffect, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import './page.css'

type Candle = {
  ts: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

type Decision = {
  action: string
  confidence: number
  vetoed: boolean
  reason: string
  model_id?: string | null
}

type Sentiment = {
  compound_avg: number
  label: string
}

type RecommendedCoin = {
  symbol: string
}

type RecommendedResponse = {
  coins: RecommendedCoin[]
}

async function fetchRecommendedCoins(): Promise<string[]> {
  const fallback = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT']
  try {
    const res = await fetch('http://localhost:8000/api/coins/recommended?limit=10&max_price=2')
    if (!res.ok) return fallback
    const j = (await res.json()) as RecommendedResponse
    const syms = j.coins.map((c) => c.symbol).filter(Boolean)
    return syms.length > 0 ? syms : fallback
  } catch {
    return fallback
  }
}

async function fetchKlines(symbol: string): Promise<Candle[]> {
  const res = await fetch(
    `http://localhost:8000/api/market/klines?symbol=${symbol}&interval=1m&limit=200`,
  )
  if (!res.ok) throw new Error('Failed to load klines')
  const json = await res.json()
  return json.rows
}

async function fetchSentiment(symbol: string): Promise<Sentiment> {
  const body = {
    symbol,
    texts: [
      `${symbol} shows strong buy interest on Binance.`,
      `${symbol} volatility elevated but sentiment mixed.`,
    ],
  }
  const res = await fetch('http://localhost:8000/api/sentiment/score', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error('Failed to load sentiment')
  const j = await res.json()
  return { compound_avg: j.compound_avg, label: j.label }
}

async function fetchDecision(symbol: string, sentimentIndex: number): Promise<Decision> {
  const res = await fetch('http://localhost:8000/api/trading/decision', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      symbol,
      interval: '1m',
      limit: 200,
      sentiment_index: sentimentIndex,
    }),
  })
  if (!res.ok) throw new Error('Failed to load decision')
  const j = await res.json()
  return {
    action: j.action,
    confidence: j.confidence,
    vetoed: j.vetoed,
    reason: j.reason,
    model_id: j.model_id,
  }
}

export function DashboardPage() {
  const [symbols, setSymbols] = useState<string[]>([])
  const [symbol, setSymbol] = useState<string | null>(null)
  const [candles, setCandles] = useState<Candle[]>([])
  const [sentiment, setSentiment] = useState<Sentiment | null>(null)
  const [decision, setDecision] = useState<Decision | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [automationOn, setAutomationOn] = useState(false)

  async function getAutomationState(): Promise<boolean> {
    const res = await fetch('http://localhost:8000/api/trading/automation', { method: 'GET' })
    if (!res.ok) throw new Error('Failed to load automation state')
    const j = await res.json()
    return Boolean(j.automation)
  }

  async function startAutomation(sym: string): Promise<void> {
    const qty = sym === 'WAXPUSDT' ? 0.2 : 1
    const res = await fetch('http://localhost:8000/api/trading/automation/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: sym,
        interval: '1m',
        limit: 200,
        qty,
        rules_weight: 0.45,
        ml_weight: 0.55,
        veto_threshold: -0.35,
        tick_seconds: 30,
        sentiment_lookback_minutes: 60,
        // Safer defaults tuned via backtesting.
        stop_loss_bps: 250,
        take_profit_bps: 400,
        trailing_stop_bps: 0,
        use_proba_thresholds: true,
        buy_proba_threshold: 0.2,
        sell_proba_threshold: 0.45,
      }),
    })
    if (!res.ok) throw new Error('Failed to start automation')
    setAutomationOn(true)
  }

  async function stopAutomation(): Promise<void> {
    const res = await fetch('http://localhost:8000/api/trading/automation/stop', { method: 'POST' })
    if (!res.ok) throw new Error('Failed to stop automation')
    setAutomationOn(false)
  }

  async function refreshAll(sym: string) {
    try {
      setLoading(true)
      setError(null)
      const [kl, sent] = await Promise.all([fetchKlines(sym), fetchSentiment(sym)])
      setCandles(kl)
      setSentiment(sent)
      const dec = await fetchDecision(sym, sent.compound_avg)
      setDecision(dec)
    } catch (e) {
      console.error(e)
      setError('Failed to load live data. Is backend running on :8000?')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // Load top-10 cheapest growing coins once and default to the first.
    ;(async () => {
      try {
        const syms = await fetchRecommendedCoins()
        setSymbols(syms)
        if (!symbol && syms.length > 0) {
          setSymbol(syms[0])
          await refreshAll(syms[0])
        }
      } catch (e) {
        console.error(e)
        setError('Failed to load recommended cheap coins.')
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    void (async () => {
      try {
        const on = await getAutomationState()
        setAutomationOn(on)
      } catch {
        // ignore
      }
    })()
  }, [])

  useEffect(() => {
    if (symbol) {
      void refreshAll(symbol)
    }
  }, [symbol])

  useEffect(() => {
    if (!symbol) return
    if (!automationOn) return

    let cancelled = false
    const tickMs = 30000

    const automationTick = async () => {
      if (cancelled) return
      try {
        setError(null)
        setLoading(true)
        const kl = await fetchKlines(symbol)
        setCandles(kl)

        const sent = await fetchSentiment(symbol)
        setSentiment(sent)

        const dec = await fetchDecision(symbol, sent.compound_avg)
        setDecision(dec)

        // Trade execution happens in the backend automation loop now.
      } catch (e) {
        console.error(e)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    // Run immediately, then on interval.
    void automationTick()
    const t = window.setInterval(() => {
      void automationTick()
    }, tickMs)

    return () => {
      cancelled = true
      window.clearInterval(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [automationOn, symbol])

  const latest = useMemo(() => (candles.length ? candles[candles.length - 1] : null), [candles])

  return (
    <div className="cv-page">
      <div className="cv-pageHeader">
        <div>
          <div className="cv-h1">Live Market & Sentiment Dashboard</div>
          <div className="cv-sub">
            Powered by backend APIs (`/market`, `/sentiment`, `/trading`). Paper trading only.
          </div>
        </div>
        <div className="cv-row">
          <select
            className="cv-input"
            value={symbol ?? ''}
            onChange={(e) => setSymbol(e.target.value)}
          >
            {symbols.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <button
            className="cv-btn"
            onClick={() => symbol && void refreshAll(symbol)}
            disabled={loading || !symbol}
          >
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
          {!automationOn ? (
            <button
              className="cv-btn cv-btnPrimary"
              onClick={() => symbol && void startAutomation(symbol)}
              disabled={!symbol}
            >
              Start automation
            </button>
          ) : (
            <button className="cv-btn" onClick={() => void stopAutomation()}>
              Stop automation
            </button>
          )}
        </div>
      </div>

      {error ? (
        <div className="cv-card">
          <div className="cv-cardTitle">Error</div>
          <div className="cv-muted" style={{ marginTop: 8 }}>
            {error}
          </div>
        </div>
      ) : null}

      <div className="cv-grid">
        <div className="cv-card">
          <div className="cv-cardTitle">Symbol</div>
          <div className="cv-kpi">{symbol}</div>
          <div className="cv-muted">1m candles • live from `/market/klines`</div>
        </div>
        <div className="cv-card">
          <div className="cv-cardTitle">Last price</div>
          <div className="cv-kpi">{latest ? `$${latest.close.toFixed(2)}` : '—'}</div>
          <div className="cv-muted">Last close from klines</div>
        </div>
        <div className="cv-card">
          <div className="cv-cardTitle">Sentiment index</div>
          <div className="cv-kpi">
            {sentiment ? sentiment.compound_avg.toFixed(3) : '—'}{' '}
            <span className="cv-kpiSub">({sentiment ? sentiment.label : 'loading'})</span>
          </div>
          <div className="cv-muted">From `/sentiment/score`</div>
        </div>
        <div className="cv-card">
          <div className="cv-cardTitle">Decision</div>
          <div className="cv-kpi">
            {decision ? decision.action : '—'}{' '}
            <span className="cv-kpiSub">
              {decision ? `(${decision.confidence.toFixed(2)})` : ''}
            </span>
          </div>
          <div className="cv-muted">
            {decision
              ? decision.vetoed
                ? `VETOED (${decision.reason})`
                : `Reason: ${decision.reason}`
              : 'Hybrid rules + ML + sentiment veto'}
          </div>
        </div>
      </div>

      <div className="cv-split">
        <div className="cv-card cv-cardTall">
          <div className="cv-cardTitle">Price (live)</div>
          <div style={{ height: 320, marginTop: 12 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={candles} margin={{ left: 6, right: 10, top: 10, bottom: 0 }}>
                <defs>
                  <linearGradient id="gPrice" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#49a3ff" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#49a3ff" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                <XAxis
                  dataKey="ts"
                  tick={{ fill: 'rgba(232,236,255,0.6)', fontSize: 12 }}
                  minTickGap={24}
                />
                <YAxis
                  tick={{ fill: 'rgba(232,236,255,0.6)', fontSize: 12 }}
                  width={56}
                  domain={['auto', 'auto']}
                />
                <Tooltip
                  contentStyle={{
                    background: 'rgba(11,16,32,0.92)',
                    border: '1px solid rgba(255,255,255,0.12)',
                    borderRadius: 12,
                    color: '#e8ecff',
                  }}
                />
                <Area type="monotone" dataKey="close" stroke="#49a3ff" fill="url(#gPrice)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="cv-card cv-cardTall">
          <div className="cv-cardTitle">Volume</div>
          <div style={{ height: 320, marginTop: 12 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={candles} margin={{ left: 6, right: 10, top: 10, bottom: 0 }}>
                <defs>
                  <linearGradient id="gVol" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#a25dff" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#a25dff" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                <XAxis
                  dataKey="ts"
                  tick={{ fill: 'rgba(232,236,255,0.6)', fontSize: 12 }}
                  minTickGap={24}
                />
                <YAxis
                  tick={{ fill: 'rgba(232,236,255,0.6)', fontSize: 12 }}
                  width={56}
                  domain={['auto', 'auto']}
                />
                <Tooltip
                  contentStyle={{
                    background: 'rgba(11,16,32,0.92)',
                    border: '1px solid rgba(255,255,255,0.12)',
                    borderRadius: 12,
                    color: '#e8ecff',
                  }}
                />
                <Area type="monotone" dataKey="volume" stroke="#a25dff" fill="url(#gVol)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}

