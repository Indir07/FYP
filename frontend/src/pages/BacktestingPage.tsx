import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import './page.css'

type RecommendedCoin = { symbol: string }

type RecommendedResponse = {
  coins: RecommendedCoin[]
}

async function fetchRecommended(): Promise<RecommendedResponse> {
  const res = await fetch('http://localhost:8000/api/coins/recommended?limit=10&max_price=0.5')
  if (!res.ok) throw new Error('Failed to fetch recommended coins')
  return res.json()
}

type BacktestMetrics = {
  sharpe: number
  max_drawdown: number
  final_return: number
  cagr_like?: number
}

type BacktestTrade = {
  ts: string
  symbol: string
  side: 'BUY' | 'SELL'
  qty: number
  price: number
  fee: number
  pnl: number
}

type BacktestResponse = {
  symbol: string
  interval: string
  metrics: BacktestMetrics
  trades: BacktestTrade[]
  model_id: string | null
}

export function BacktestingPage() {
  const recQ = useQuery({
    queryKey: ['coins', 'recommended'],
    queryFn: fetchRecommended,
    refetchInterval: false,
  })

  const recommended = recQ.data?.coins.map((c) => c.symbol) ?? []
  const [symbol, setSymbol] = useState('')
  const [interval, setInterval] = useState<'1m' | '5m' | '15m' | '1h'>('1m')
  const [limit, setLimit] = useState(300)
  const [sentimentMode, setSentimentMode] = useState<'neutral' | 'reddit'>('neutral')
  const [tradeFractionCash, setTradeFractionCash] = useState(0.5)
  const [stopLossBps, setStopLossBps] = useState(250)
  const [takeProfitBps, setTakeProfitBps] = useState(400)
  const [trailingStopBps, setTrailingStopBps] = useState(0)
  const [useProbaThresholds, setUseProbaThresholds] = useState(true)
  const [buyProbaThreshold, setBuyProbaThreshold] = useState(0.2)
  const [sellProbaThreshold, setSellProbaThreshold] = useState(0.45)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<BacktestResponse | null>(null)

  useEffect(() => {
    if (!symbol && recommended.length > 0) setSymbol(recommended[0])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recommended.join(',')])

  useEffect(() => {
    // Safer default sizing for high-volatility micro-price pair.
    if (symbol === 'WAXPUSDT') {
      setTradeFractionCash(0.1)
    } else if (tradeFractionCash < 0.5) {
      setTradeFractionCash(0.5)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol])

  async function runBacktest() {
    try {
      if (!symbol) throw new Error('No symbol selected')
      setRunning(true)
      setError(null)
      const res = await fetch('http://localhost:8000/api/backtest/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          interval,
          limit,
          sentiment_mode: sentimentMode,
          trade_fraction_cash: tradeFractionCash,
          fee_bps: 4.0,
          rules_weight: 0.45,
          ml_weight: 0.55,
          veto_threshold: -0.35,
          stop_loss_bps: stopLossBps,
          take_profit_bps: takeProfitBps,
          trailing_stop_bps: trailingStopBps,
          use_proba_thresholds: useProbaThresholds,
          buy_proba_threshold: buyProbaThreshold,
          sell_proba_threshold: sellProbaThreshold,
        }),
      })
      if (!res.ok) throw new Error('Backtest failed')
      const j = (await res.json()) as BacktestResponse
      setResult(j)
    } catch (e) {
      setError('Failed to run backtest. Train a model first.')
    } finally {
      setRunning(false)
    }
  }

  const metrics = result?.metrics
  const maxDdPct = typeof metrics?.max_drawdown === 'number' ? `${(metrics.max_drawdown * 100).toFixed(2)}%` : '—'

  return (
    <div className="cv-page">
      <div className="cv-pageHeader">
        <div>
          <div className="cv-h1">Backtesting & Performance Reports</div>
          <div className="cv-sub">
            UC-05. Run backtests on historical market + archived sentiment and generate Sharpe,
            drawdown, and P/L charts.
          </div>
        </div>
        <div className="cv-row">
          <select className="cv-input" value={symbol} onChange={(e) => setSymbol(e.target.value)}>
            {recommended.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select className="cv-input" value={interval} onChange={(e) => setInterval(e.target.value as any)}>
            <option value="1m">1m</option>
            <option value="5m">5m</option>
            <option value="15m">15m</option>
            <option value="1h">1h</option>
          </select>
          <select
            className="cv-input"
            value={sentimentMode}
            onChange={(e) => setSentimentMode(e.target.value as 'neutral' | 'reddit')}
          >
            <option value="neutral">Sentiment: neutral</option>
            <option value="reddit">Sentiment: reddit</option>
          </select>
          <input
            className="cv-input"
            type="number"
            min={50}
            max={2000}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          />
          <input
            className="cv-input"
            type="number"
            min={0.01}
            max={1}
            step={0.01}
            value={tradeFractionCash}
            onChange={(e) => setTradeFractionCash(Number(e.target.value))}
            title="Trade fraction of cash per trade (position size)."
          />
          <input
            className="cv-input"
            type="number"
            min={0}
            max={50000}
            value={stopLossBps}
            onChange={(e) => setStopLossBps(Number(e.target.value))}
            title="Stop-loss in basis points (bps). 0 disables."
          />
          <input
            className="cv-input"
            type="number"
            min={0}
            max={50000}
            value={takeProfitBps}
            onChange={(e) => setTakeProfitBps(Number(e.target.value))}
            title="Take-profit in basis points (bps). 0 disables."
          />
          <input
            className="cv-input"
            type="number"
            min={0}
            max={50000}
            value={trailingStopBps}
            onChange={(e) => setTrailingStopBps(Number(e.target.value))}
            title="Trailing stop in basis points (bps). 0 disables."
          />
          <label className="cv-muted" style={{ marginLeft: 10 }}>
            <input
              type="checkbox"
              checked={useProbaThresholds}
              onChange={(e) => setUseProbaThresholds(e.target.checked)}
            />{' '}
            Use probability thresholds
          </label>
          <input
            className="cv-input"
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={buyProbaThreshold}
            onChange={(e) => setBuyProbaThreshold(Number(e.target.value))}
            title="BUY threshold on model P(positive). BUY when proba >= this."
          />
          <input
            className="cv-input"
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={sellProbaThreshold}
            onChange={(e) => setSellProbaThreshold(Number(e.target.value))}
            title="SELL threshold on model P(positive). SELL when proba <= this."
          />
          <button className="cv-btn cv-btnPrimary" onClick={() => void runBacktest()} disabled={running}>
            {running ? 'Running…' : 'Run backtest'}
          </button>
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

      <div className="cv-grid" style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))' }}>
        <div className="cv-card">
          <div className="cv-cardTitle">Sharpe</div>
          <div className="cv-kpi">{metrics ? metrics.sharpe.toFixed(3) : '—'}</div>
          <div className="cv-muted">Strategy Sharpe on equity curve</div>
        </div>
        <div className="cv-card">
          <div className="cv-cardTitle">Max drawdown</div>
          <div className="cv-kpi">{metrics ? maxDdPct : '—'}</div>
          <div className="cv-muted">Peak-to-trough drawdown</div>
        </div>
        <div className="cv-card">
          <div className="cv-cardTitle">CAGR</div>
          <div className="cv-kpi">
            {metrics?.cagr_like !== undefined ? `${(metrics.cagr_like * 100).toFixed(2)}%` : '—'}
          </div>
          <div className="cv-muted">Approximate CAGR-like estimate</div>
        </div>
      </div>

      <div className="cv-card">
        <div className="cv-cardTitle">Runs</div>
        <div className="cv-muted" style={{ marginTop: 10 }}>
          Model: {result?.model_id ?? '—'} • Trades: {result?.trades.length ?? 0}
        </div>
        {result ? (
          <div style={{ marginTop: 12, overflowX: 'auto' }}>
            <table className="cv-table">
              <thead>
                <tr>
                  <th align="left">Time</th>
                  <th align="left">Side</th>
                  <th align="left">Qty</th>
                  <th align="left">Price</th>
                  <th align="left">Fee</th>
                  <th align="left">P/L</th>
                </tr>
              </thead>
              <tbody>
                {result.trades.slice(-50).map((t, idx) => (
                  <tr key={`${t.ts}-${idx}`}>
                    <td>{t.ts}</td>
                    <td>{t.side}</td>
                    <td>{t.qty.toFixed(6)}</td>
                    <td>{t.price.toFixed(6)}</td>
                    <td>{t.fee.toFixed(6)}</td>
                    <td>{t.pnl.toFixed(6)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </div>
  )
}

