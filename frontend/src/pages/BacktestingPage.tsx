import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import './page.css'
import { apiUrl } from '../lib/apiBase'

type RecommendedCoin = { symbol: string }

type RecommendedResponse = {
  coins: RecommendedCoin[]
}

async function fetchRecommended(): Promise<RecommendedResponse> {
  const fallback: RecommendedResponse = {
    coins: [
      { symbol: 'BTCUSDT' },
      { symbol: 'ETHUSDT' },
      { symbol: 'BNBUSDT' },
      { symbol: 'SOLUSDT' },
      { symbol: 'XRPUSDT' },
      { symbol: 'DOGEUSDT' },
      { symbol: 'ADAUSDT' },
      { symbol: 'TRXUSDT' },
      { symbol: 'AVAXUSDT' },
      { symbol: 'LINKUSDT' },
    ],
  }
  try {
    const res = await fetch(apiUrl('/api/coins/recommended?strategy=top10_famous_growing&limit=10'))
    if (!res.ok) return fallback
    const data = (await res.json()) as RecommendedResponse
    return data.coins?.length ? data : fallback
  } catch {
    return fallback
  }
}

type BacktestMetrics = {
  sharpe: number
  max_drawdown: number
  final_return: number
  cagr_like?: number | null
  cagr_annualized?: boolean
  total_return_pct?: number
  period_years?: number
  cagr_note?: string
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
  // Default ~7 days of 1m bars — enough for meaningful CAGR (backend requires ≥7d for annualized CAGR).
  const [limit, setLimit] = useState(10080)
  const [sentimentMode, setSentimentMode] = useState<'neutral' | 'reddit'>('neutral')
  const [tradeFractionCash, setTradeFractionCash] = useState(0.1)
  const [stopLossBps, setStopLossBps] = useState(120)
  const [takeProfitBps, setTakeProfitBps] = useState(220)
  const [trailingStopBps, setTrailingStopBps] = useState(0)
  const [useProbaThresholds, setUseProbaThresholds] = useState(true)
  const [buyProbaThreshold, setBuyProbaThreshold] = useState(0.15)
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
    } else if (tradeFractionCash > 0.2) {
      setTradeFractionCash(0.1)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol])

  async function runBacktest() {
    try {
      if (!symbol) throw new Error('No symbol selected')
      setRunning(true)
      setError(null)
      const res = await fetch(apiUrl('/api/backtest/run'), {
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
            UC-05. Replay the hybrid strategy on historical candles. Fee is fixed at 4 bps in this run (see
            code). Use <strong>≥7 days</strong> of 1m data for meaningful annualized CAGR.
          </div>
        </div>
      </div>

      <div className="cv-card">
        <div className="cv-cardTitle">Backtest parameters</div>
        <div className="cv-muted" style={{ marginTop: 6, lineHeight: 1.45 }}>
          Each field below is sent to <code>POST /api/backtest/run</code>. Adjust one group at a time (data →
          size → risk → model thresholds) when tuning.
        </div>

        <div className="cv-formGrid">
          <div className="cv-sectionTitle">Market & data</div>

          <div className="cv-field">
            <label className="cv-label" htmlFor="bt-symbol">
              Trading pair (symbol)
            </label>
            <span className="cv-hint">Must match a symbol you have a trained XGB model for (Models page).</span>
            <select
              id="bt-symbol"
              className="cv-input"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
            >
              {recommended.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="cv-field">
            <label className="cv-label" htmlFor="bt-interval">
              Candle interval (timeframe)
            </label>
            <span className="cv-hint">Bar size for klines and features. Shorter = more bars for the same wall-clock span.</span>
            <select
              id="bt-interval"
              className="cv-input"
              value={interval}
              onChange={(e) => setInterval(e.target.value as '1m' | '5m' | '15m' | '1h')}
            >
              <option value="1m">1 minute (1m)</option>
              <option value="5m">5 minutes (5m)</option>
              <option value="15m">15 minutes (15m)</option>
              <option value="1h">1 hour (1h)</option>
            </select>
          </div>

          <div className="cv-field">
            <label className="cv-label" htmlFor="bt-limit">
              Number of candles (limit)
            </label>
            <span className="cv-hint">
              How many recent bars to load (50–50,000). Example: 1m → 10,080 ≈ 7 days. Longer = stabler stats;
              CAGR (annualized) only shown when the window is long enough.
            </span>
            <input
              id="bt-limit"
              className="cv-input"
              type="number"
              min={50}
              max={50000}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              placeholder="e.g. 10080"
            />
          </div>

          <div className="cv-field">
            <label className="cv-label" htmlFor="bt-sentiment">
              Sentiment source
            </label>
            <span className="cv-hint">
              <strong>Neutral</strong>: no Reddit features (stable). <strong>Reddit</strong>: requires{' '}
              <code>REDDIT_*</code> in backend .env.
            </span>
            <select
              id="bt-sentiment"
              className="cv-input"
              value={sentimentMode}
              onChange={(e) => setSentimentMode(e.target.value as 'neutral' | 'reddit')}
            >
              <option value="neutral">Neutral (0 sentiment — good for comparisons)</option>
              <option value="reddit">Reddit (live sentiment if configured)</option>
            </select>
          </div>

          <div className="cv-sectionTitle">Position sizing & fees</div>

          <div className="cv-field">
            <label className="cv-label" htmlFor="bt-fraction">
              Trade fraction of cash (0–1)
            </label>
            <span className="cv-hint">
              Fraction of <em>available cash</em> used per BUY. Typical: <strong>0.05–0.15</strong>. Higher =
              larger positions and risk.
            </span>
            <input
              id="bt-fraction"
              className="cv-input"
              type="number"
              min={0.01}
              max={1}
              step={0.01}
              value={tradeFractionCash}
              onChange={(e) => setTradeFractionCash(Number(e.target.value))}
              placeholder="0.1"
            />
          </div>

          <div className="cv-field">
            <span className="cv-label">Trading fee (fixed in this run)</span>
            <span className="cv-hint">
              Sent to API as <code>fee_bps: 4</code> (4 basis points = 0.04% per side). Change in code if you
              need another tier.
            </span>
            <input className="cv-input" value="4 bps (0.04%)" readOnly disabled />
          </div>

          <div className="cv-sectionTitle">Risk exits (basis points, bps)</div>

          <div className="cv-field">
            <label className="cv-label" htmlFor="bt-sl">
              Stop-loss (bps)
            </label>
            <span className="cv-hint">
              1 bps = 0.01%. Sell if price drops this far <em>below entry</em>. Typical: <strong>80–200</strong>.{' '}
              <strong>0</strong> = disabled.
            </span>
            <input
              id="bt-sl"
              className="cv-input"
              type="number"
              min={0}
              max={50000}
              value={stopLossBps}
              onChange={(e) => setStopLossBps(Number(e.target.value))}
              placeholder="120"
            />
          </div>

          <div className="cv-field">
            <label className="cv-label" htmlFor="bt-tp">
              Take-profit (bps)
            </label>
            <span className="cv-hint">
              Sell when price is this far <em>above entry</em>. Typical: <strong>150–400</strong>.{' '}
              <strong>0</strong> = disabled.
            </span>
            <input
              id="bt-tp"
              className="cv-input"
              type="number"
              min={0}
              max={50000}
              value={takeProfitBps}
              onChange={(e) => setTakeProfitBps(Number(e.target.value))}
              placeholder="220"
            />
          </div>

          <div className="cv-field">
            <label className="cv-label" htmlFor="bt-trail">
              Trailing stop (bps)
            </label>
            <span className="cv-hint">
              Trails below the highest price since entry. Typical: <strong>0</strong> (off) or{' '}
              <strong>50–150</strong> when enabled.
            </span>
            <input
              id="bt-trail"
              className="cv-input"
              type="number"
              min={0}
              max={50000}
              value={trailingStopBps}
              onChange={(e) => setTrailingStopBps(Number(e.target.value))}
              placeholder="0"
            />
          </div>

          <div className="cv-sectionTitle">Model decision (XGB probability)</div>

          <div className="cv-field" style={{ gridColumn: '1 / -1' }}>
            <label className="cv-label" htmlFor="bt-use-proba">
              <input
                id="bt-use-proba"
                type="checkbox"
                checked={useProbaThresholds}
                onChange={(e) => setUseProbaThresholds(e.target.checked)}
              />{' '}
              Use probability thresholds (vs fused score)
            </label>
            <span className="cv-hint">
              When <strong>on</strong>: BUY/SELL use raw <code>P(up)</code> from the model. When <strong>off</strong>:
              backend uses fused rule+ML score thresholds (see API defaults).
            </span>
          </div>

          <div className="cv-field">
            <label className="cv-label" htmlFor="bt-buy-p">
              Buy probability threshold (0–1)
            </label>
            <span className="cv-hint">
              Open long when <code>P(up) ≥</code> this. <strong>Lower</strong> = more trades (often too many).
              Try <strong>0.52–0.60</strong> for fewer, higher-conviction entries.
            </span>
            <input
              id="bt-buy-p"
              className="cv-input"
              type="number"
              min={0}
              max={1}
              step={0.01}
              value={buyProbaThreshold}
              onChange={(e) => setBuyProbaThreshold(Number(e.target.value))}
              placeholder="0.55"
            />
          </div>

          <div className="cv-field">
            <label className="cv-label" htmlFor="bt-sell-p">
              Sell probability threshold (0–1)
            </label>
            <span className="cv-hint">
              Close long when <code>P(up) ≤</code> this. Should usually be <strong>below</strong> the buy
              threshold. Try <strong>0.40–0.48</strong>.
            </span>
            <input
              id="bt-sell-p"
              className="cv-input"
              type="number"
              min={0}
              max={1}
              step={0.01}
              value={sellProbaThreshold}
              onChange={(e) => setSellProbaThreshold(Number(e.target.value))}
              placeholder="0.45"
            />
          </div>
        </div>

        <div className="cv-row" style={{ marginTop: 18 }}>
          <button className="cv-btn cv-btnPrimary" onClick={() => void runBacktest()} disabled={running}>
            {running ? 'Running…' : 'Run backtest'}
          </button>
          <span className="cv-muted">Runs the simulation with the values above and updates metrics below.</span>
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

      <div className="cv-grid" style={{ gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}>
        <div className="cv-card">
          <div className="cv-cardTitle">Period return</div>
          <div className="cv-kpi">
            {metrics && typeof metrics.total_return_pct === 'number'
              ? `${metrics.total_return_pct.toFixed(2)}%`
              : '—'}
          </div>
          <div className="cv-muted">Total P&amp;L % over the backtest window (always shown)</div>
        </div>
        <div className="cv-card">
          <div className="cv-cardTitle">Sharpe (approx.)</div>
          <div className="cv-kpi">{metrics ? metrics.sharpe.toFixed(3) : '—'}</div>
          <div className="cv-muted">Daily / hourly when possible; clipped to reduce 1m noise</div>
        </div>
        <div className="cv-card">
          <div className="cv-cardTitle">Max drawdown</div>
          <div className="cv-kpi">{metrics ? maxDdPct : '—'}</div>
          <div className="cv-muted">Peak-to-trough drawdown</div>
        </div>
        <div className="cv-card">
          <div className="cv-cardTitle">CAGR (annualized)</div>
          <div className="cv-kpi">
            {metrics?.cagr_annualized && metrics.cagr_like != null
              ? `${(metrics.cagr_like * 100).toFixed(2)}%`
              : '—'}
          </div>
          <div className="cv-muted">
            {metrics?.cagr_note
              ? metrics.cagr_note
              : 'Shown only when the sample is at least ~7 days (geometric annualization is misleading on very short intraday runs).'}
          </div>
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

