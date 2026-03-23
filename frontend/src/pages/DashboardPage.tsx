import { useEffect, useMemo, useRef, useState } from 'react'
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
import { apiUrl } from '../lib/apiBase'

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

const TOP10_COINS = [
  'BTCUSDT',
  'ETHUSDT',
  'BNBUSDT',
  'SOLUSDT',
  'XRPUSDT',
  'DOGEUSDT',
  'ADAUSDT',
  'TRXUSDT',
  'AVAXUSDT',
  'LINKUSDT',
]
const DASHBOARD_SYMBOL_KEY = 'cv_dashboard_selected_symbol'

function useElementSize<T extends HTMLElement>() {
  const ref = useRef<T | null>(null)
  const [size, setSize] = useState({ width: 0, height: 0 })

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const ro = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      const cr = entry.contentRect
      setSize({ width: cr.width, height: cr.height })
    })

    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  return { ref, size }
}

function toTimeLabel(ts: string) {
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ts
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function CandlestickSVG({ candles, width, height }: { candles: Candle[]; width: number; height: number }) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null)
  const svgRef = useRef<SVGSVGElement | null>(null)

  const margin = { left: 56, right: 10, top: 10, bottom: 22 }
  const innerW = Math.max(1, width - margin.left - margin.right)
  const innerH = Math.max(1, height - margin.top - margin.bottom)

  const lows = candles.map((c) => c.low)
  const highs = candles.map((c) => c.high)

  const minY = lows.length ? Math.min(...lows) : 0
  const maxY = highs.length ? Math.max(...highs) : 1
  const pad = (maxY - minY) * 0.05
  const yMin = minY - pad
  const yMax = maxY + pad
  const yRange = Math.max(1e-9, yMax - yMin)

  const xStep = candles.length ? innerW / candles.length : innerW
  const candleW = Math.max(3, Math.min(10, xStep * 0.65))

  const yScale = (v: number) => margin.top + innerH - ((v - yMin) / yRange) * innerH
  const xCenter = (i: number) => margin.left + i * xStep + xStep / 2

  const onMove = (e: any) => {
    if (!svgRef.current) return
    const rect = svgRef.current.getBoundingClientRect()
    const px = e.clientX - rect.left
    const i = Math.floor((px - margin.left) / xStep)
    const clamped = Math.max(0, Math.min(candles.length - 1, i))
    setHoverIdx(Number.isFinite(clamped) ? clamped : null)
  }

  const tooltip =
    hoverIdx != null && candles[hoverIdx] ? (
      (() => {
        const c = candles[hoverIdx]
        const x = xCenter(hoverIdx)
        const y = yScale(Math.max(c.high, c.close))
        const isUp = c.close >= c.open
        const color = isUp ? 'rgba(34,197,94,0.95)' : 'rgba(239,68,68,0.95)'
        return (
          <div
            className="cv-binanceTooltip"
            style={{
              left: x,
              top: y,
              transform: 'translate(-50%, -100%)',
              borderColor: color,
            }}
          >
            <div style={{ fontWeight: 750, fontSize: 12, color: 'rgba(240,245,255,0.95)' }}>
              {toTimeLabel(c.ts)}
            </div>
            <div style={{ fontSize: 12, color: 'rgba(232,236,255,0.78)', marginTop: 4 }}>
              O: {c.open.toFixed(4)}
              <br />
              H: {c.high.toFixed(4)}
              <br />
              L: {c.low.toFixed(4)}
              <br />
              C: {c.close.toFixed(4)}
            </div>
          </div>
        )
      })()
    ) : null

  const ticks = 5
  const yTickVals = Array.from({ length: ticks }, (_, i) => yMin + (yRange * i) / (ticks - 1))

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {tooltip}
      <svg
        ref={svgRef}
        width={width}
        height={height}
        onMouseMove={onMove}
        onMouseLeave={() => setHoverIdx(null)}
        style={{ display: 'block' }}
      >
        {yTickVals.map((v, i) => {
          const y = yScale(v)
          return (
            <g key={i}>
              <line
                x1={margin.left}
                x2={width - margin.right}
                y1={y}
                y2={y}
                stroke="rgba(255,255,255,0.08)"
              />
              <text x={margin.left - 8} y={y + 4} textAnchor="end" fontSize={11} fill="rgba(232,236,255,0.55)">
                {v.toFixed(2)}
              </text>
            </g>
          )
        })}

        {candles.map((c, i) => {
          const cx = xCenter(i)
          const yO = yScale(c.open)
          const yC = yScale(c.close)
          const yH = yScale(c.high)
          const yL = yScale(c.low)
          const isUp = c.close >= c.open
          const col = isUp ? '#22c55e' : '#ef4444'
          const bodyTop = Math.min(yO, yC)
          const bodyH = Math.max(1, Math.abs(yC - yO))

          return (
            <g key={c.ts}>
              <line x1={cx} x2={cx} y1={yH} y2={yL} stroke={col} strokeWidth={1} />
              <rect
                x={cx - candleW / 2}
                y={bodyTop}
                width={candleW}
                height={bodyH}
                fill={col}
                stroke={col}
                strokeWidth={0.5}
                rx={1}
              />
            </g>
          )
        })}
      </svg>
    </div>
  )
}

async function fetchRecommendedCoins(): Promise<string[]> {
  const fallback = TOP10_COINS
  try {
    const res = await fetch(apiUrl('/api/coins/recommended?strategy=top10_famous_growing&limit=10'))
    if (!res.ok) return fallback
    const j = (await res.json()) as RecommendedResponse
    const allowed = new Set(j.coins.map((c) => c.symbol).filter(Boolean))
    const filtered = TOP10_COINS.filter((s) => allowed.has(s))
    return filtered.length > 0 ? filtered : fallback
  } catch {
    return fallback
  }
}

async function fetchKlines(symbol: string): Promise<Candle[]> {
  const res = await fetch(
    apiUrl(`/api/market/klines?symbol=${encodeURIComponent(symbol)}&interval=1m&limit=200`),
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
  const res = await fetch(apiUrl('/api/sentiment/score'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error('Failed to load sentiment')
  const j = await res.json()
  return { compound_avg: j.compound_avg, label: j.label }
}

async function fetchDecision(symbol: string, sentimentIndex: number): Promise<Decision> {
  const res = await fetch(apiUrl('/api/trading/decision'), {
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
  const [coinMenuOpen, setCoinMenuOpen] = useState(false)
  const coinMenuRef = useRef<HTMLDivElement | null>(null)
  const [candles, setCandles] = useState<Candle[]>([])
  const [sentiment, setSentiment] = useState<Sentiment | null>(null)
  const [decision, setDecision] = useState<Decision | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [automationOn, setAutomationOn] = useState(false)

  const { ref: priceChartWrapRef, size: priceChartSize } = useElementSize<HTMLDivElement>()

  async function getAutomationState(): Promise<boolean> {
    const res = await fetch(apiUrl('/api/trading/automation'), { method: 'GET' })
    if (!res.ok) throw new Error('Failed to load automation state')
    const j = await res.json()
    return Boolean(j.automation)
  }

  async function startAutomation(sym: string): Promise<void> {
    const qty = sym === 'WAXPUSDT' ? 0.1 : 0.1
    const res = await fetch(apiUrl('/api/trading/automation/start'), {
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
        stop_loss_bps: 120,
        take_profit_bps: 220,
        trailing_stop_bps: 0,
        use_proba_thresholds: true,
        buy_proba_threshold: 0.15,
        sell_proba_threshold: 0.45,
      }),
    })
    if (!res.ok) throw new Error('Failed to start automation')
    setAutomationOn(true)
  }

  async function stopAutomation(): Promise<void> {
    const res = await fetch(apiUrl('/api/trading/automation/stop'), { method: 'POST' })
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
    // Load curated top-10 famous growing coins once and default to the first.
    ;(async () => {
      try {
        const syms = await fetchRecommendedCoins()
        setSymbols(syms)
        if (!symbol && syms.length > 0) {
          const saved = window.localStorage.getItem(DASHBOARD_SYMBOL_KEY)
          const initial = saved && syms.includes(saved) ? saved : syms[0]
          setSymbol(initial)
          await refreshAll(initial)
        }
      } catch (e) {
        console.error(e)
        setError('Failed to load recommended top-10 coins.')
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
      window.localStorage.setItem(DASHBOARD_SYMBOL_KEY, symbol)
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

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (!coinMenuRef.current) return
      if (!coinMenuRef.current.contains(e.target as Node)) {
        setCoinMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

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
          <div className="cv-coinSelect" ref={coinMenuRef}>
            <button
              type="button"
              className="cv-coinSelectBtn"
              onClick={() => setCoinMenuOpen((v) => !v)}
              aria-label="Select coin"
            >
              <span>{symbol ?? 'Select coin'}</span>
              <span className="cv-coinSelectArrow">{coinMenuOpen ? '▲' : '▼'}</span>
            </button>
            {coinMenuOpen ? (
              <div className="cv-coinSelectMenu">
                {symbols.map((s) => (
                  <button
                    key={s}
                    type="button"
                    className={`cv-coinOption ${s === symbol ? 'cv-coinOptionActive' : ''}`}
                    onClick={() => {
                      setSymbol(s)
                      setCoinMenuOpen(false)
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
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

      <div className="cv-card">
        <div className="cv-cardTitle">How this page works</div>
        <div className="cv-muted" style={{ marginTop: 8, lineHeight: 1.5 }}>
          <strong>Refresh</strong> loads latest 1m candles and sentiment, then asks the backend for a hybrid{' '}
          <strong>BUY / SELL / HOLD</strong> decision. <strong>Start automation</strong> runs paper-trading logic on
          the server with fixed defaults (qty, stops, probability thresholds) — tune those in{' '}
          <strong>Backtesting</strong> first, then adjust <code>backend/app/api/routes/trading.py</code> if you
          need live automation to match. This UI does not expose every automation parameter yet.
        </div>
      </div>

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
          <div ref={priceChartWrapRef} style={{ height: 320, marginTop: 12, position: 'relative' }}>
            {priceChartSize.width > 0 && candles.length ? (
              <CandlestickSVG
                candles={candles}
                width={priceChartSize.width}
                height={priceChartSize.height || 320}
              />
            ) : null}
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

