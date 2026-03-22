import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import './page.css'
import { apiUrl } from '../lib/apiBase'

type RecommendedCoin = {
  symbol: string
  last_price: number
  price_change_percent_24h: number
  quote_volume_24h: number
  score: number
}

type RecommendedResponse = {
  as_of: string
  quote_asset: string
  criteria: Record<string, unknown>
  coins: RecommendedCoin[]
}

async function fetchRecommended(): Promise<RecommendedResponse> {
  const fallback: RecommendedResponse = {
    as_of: new Date().toISOString(),
    quote_asset: 'USDT',
    criteria: {},
    coins: [
      { symbol: 'BTCUSDT', last_price: 0, price_change_percent_24h: 0, quote_volume_24h: 0, score: 0 },
      { symbol: 'ETHUSDT', last_price: 0, price_change_percent_24h: 0, quote_volume_24h: 0, score: 0 },
      { symbol: 'BNBUSDT', last_price: 0, price_change_percent_24h: 0, quote_volume_24h: 0, score: 0 },
      { symbol: 'SOLUSDT', last_price: 0, price_change_percent_24h: 0, quote_volume_24h: 0, score: 0 },
      { symbol: 'XRPUSDT', last_price: 0, price_change_percent_24h: 0, quote_volume_24h: 0, score: 0 },
      { symbol: 'DOGEUSDT', last_price: 0, price_change_percent_24h: 0, quote_volume_24h: 0, score: 0 },
      { symbol: 'ADAUSDT', last_price: 0, price_change_percent_24h: 0, quote_volume_24h: 0, score: 0 },
      { symbol: 'TRXUSDT', last_price: 0, price_change_percent_24h: 0, quote_volume_24h: 0, score: 0 },
      { symbol: 'AVAXUSDT', last_price: 0, price_change_percent_24h: 0, quote_volume_24h: 0, score: 0 },
      { symbol: 'LINKUSDT', last_price: 0, price_change_percent_24h: 0, quote_volume_24h: 0, score: 0 },
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

async function startTrainXgbRecommended(): Promise<{ job_id: string }> {
  const res = await fetch(apiUrl('/api/ml/train/xgb'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      universe: 'top10_famous_growing',
      limit: 10,
      interval: '1m',
      limit_per_symbol: 120_000,
      tune: true,
      tune_trials: 40,
      optimize_metric: 'roc_auc',
      // Reddit + VADER per symbol/time window; requires REDDIT_* in backend .env
      sentiment_post_limit: 150,
      balance_classes: true,
      balance_per_class: 600_000,
    }),
  })
  if (!res.ok) throw new Error('Failed to start training')
  return res.json()
}

type JobStatus = {
  job_id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  started_at?: string | null
  ended_at?: string | null
  error?: string | null
  model_id?: string | null
  metrics?: Record<string, unknown> | null
}

type ModelEntry = {
  id: string
  kind: string
  created_at: string
  symbols: string[]
  interval: string
  metrics: Record<string, unknown>
  active: boolean
}

async function fetchModels(): Promise<{ models: ModelEntry[] }> {
  const res = await fetch(apiUrl('/api/ml/models'))
  if (!res.ok) throw new Error('Failed to fetch models')
  return res.json()
}

async function fetchJob(jobId: string): Promise<JobStatus> {
  const res = await fetch(apiUrl(`/api/ml/jobs/${jobId}`))
  if (!res.ok) throw new Error('Failed to fetch job')
  return res.json()
}

function fmtNum(v: unknown, digits = 4): string {
  if (typeof v === 'number' && Number.isFinite(v)) return v.toFixed(digits)
  return '—'
}

function fmtPct01(v: unknown): string {
  if (typeof v === 'number' && Number.isFinite(v)) return `${(v * 100).toFixed(2)}%`
  return '—'
}

function MetricsSection({
  title,
  rows,
}: {
  title: string
  rows: { label: string; value: string }[]
}) {
  if (!rows.length) return null
  return (
    <div className="cv-metricsSection">
      <div className="cv-metricsSectionTitle">{title}</div>
      {rows.map((r) => (
        <div key={r.label} className="cv-metricRow">
          <span className="cv-muted">{r.label}</span>
          <span>{r.value}</span>
        </div>
      ))}
    </div>
  )
}

function buildMetricSections(m: Record<string, unknown>) {
  const classification = [
    { label: 'AUC (ROC)', value: fmtNum(m.auc, 4) },
    { label: 'Accuracy', value: fmtPct01(m.accuracy) },
    { label: 'Precision', value: fmtNum(m.precision, 4) },
    { label: 'Recall', value: fmtNum(m.recall, 4) },
    { label: 'F1 score', value: fmtNum(m.f1, 4) },
    { label: 'Decision threshold', value: fmtNum(m.threshold, 4) },
  ]
  const validation = [
    { label: 'Val accuracy (threshold search)', value: fmtPct01(m.val_accuracy) },
    { label: 'Val F1 (threshold search)', value: fmtNum(m.val_f1, 4) },
    { label: 'Val profit (simulated)', value: fmtNum(m.val_profit, 6) },
    { label: 'Val Sharpe (simulated)', value: fmtNum(m.val_sharpe, 4) },
  ]
  const trading = [
    { label: 'Simulated trades (test)', value: fmtNum(m.trades, 0) },
    { label: 'Gross PnL (test, fraction)', value: fmtNum(m.gross_pnl, 6) },
    { label: 'Win rate (test)', value: fmtPct01(m.win_rate) },
    { label: 'Avg trade return', value: fmtNum(m.avg_trade_return, 6) },
    { label: 'Max drawdown-like (test)', value: fmtNum(m.max_drawdown_like, 4) },
  ]
  const walkForward = [
    { label: 'WF avg PnL (folds)', value: fmtNum(m.wf_avg_pnl, 6) },
    { label: 'WF avg win rate', value: fmtPct01(m.wf_avg_win_rate) },
  ]
  const dataset = [
    { label: 'Training rows (n_samples)', value: m.n_samples != null ? String(m.n_samples) : '—' },
    {
      label: 'Rows before balance',
      value: m.rows_before_balance != null ? String(m.rows_before_balance) : '—',
    },
    {
      label: 'Rows after balance',
      value: m.rows_after_balance != null ? String(m.rows_after_balance) : '—',
    },
    {
      label: 'Balance per class',
      value: m.balance_per_class != null ? String(m.balance_per_class) : '—',
    },
    { label: 'Symbols', value: m.n_symbols != null ? String(m.n_symbols) : '—' },
    { label: 'Positive rate (test)', value: fmtPct01(m.pos_rate_test) },
    { label: 'Majority baseline accuracy', value: fmtPct01(m.majority_accuracy) },
    { label: 'Label method', value: typeof m.label_method === 'string' ? m.label_method : '—' },
    { label: 'Label cost (bps)', value: fmtNum(m.label_cost_bps, 2) },
    { label: 'Selected model', value: typeof m.selected === 'string' ? m.selected : '—' },
    { label: 'Dataset CSV', value: typeof m.dataset_path === 'string' ? m.dataset_path : '—' },
  ]
  return { classification, validation, trading, walkForward, dataset }
}

export function ModelsPage() {
  const q = useQuery({ queryKey: ['coins', 'recommended'], queryFn: fetchRecommended })
  const modelsQ = useQuery({ queryKey: ['ml', 'models'], queryFn: fetchModels, refetchInterval: 5000 })
  const [jobId, setJobId] = useState<string | null>(null)
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null)
  const [showFullMetricsJson, setShowFullMetricsJson] = useState(false)
  const jobQ = useQuery({
    queryKey: ['ml', 'job', jobId],
    queryFn: () => fetchJob(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: 2000,
  })

  const jobSummary = useMemo(() => {
    if (!jobQ.data) return null
    const m = jobQ.data.metrics as Record<string, unknown> | undefined
    const auc = typeof m?.auc === 'number' ? m.auc.toFixed(3) : undefined
    const selected = typeof m?.selected === 'string' ? m.selected : undefined
    return { auc, selected }
  }, [jobQ.data])

  const displayModel = useMemo(() => {
    const list = modelsQ.data?.models ?? []
    if (!list.length) return null
    if (selectedModelId) return list.find((x) => x.id === selectedModelId) ?? list[0]
    return list.find((x) => x.active) ?? list[0]
  }, [modelsQ.data, selectedModelId])

  const selectedMetricSections = useMemo(() => {
    if (!displayModel?.metrics) return null
    return buildMetricSections(displayModel.metrics as Record<string, unknown>)
  }, [displayModel])

  const jobMetricSections = useMemo(() => {
    const m = jobQ.data?.metrics as Record<string, unknown> | undefined
    if (!m || typeof m !== 'object') return null
    return buildMetricSections(m)
  }, [jobQ.data?.metrics])

  return (
    <div className="cv-page">
      <div className="cv-pageHeader">
        <div>
          <div className="cv-h1">Manage Model Training & Version Selection</div>
          <div className="cv-sub">
            UC-06. Train models on top-10 famous, liquid, and growth-focused coins and activate a version.
          </div>
        </div>
      </div>

      <div className="cv-card">
        <div className="cv-cardTitle">Actions</div>
        <div className="cv-muted" style={{ marginTop: 6, lineHeight: 1.45 }}>
          Training uses a <strong>fixed payload</strong> in code (universe, intervals, tuning trials). Requires
          backend + optional <code>REDDIT_*</code> for sentiment features. Activation picks which model backtesting
          and trading load.
        </div>
        <div className="cv-row" style={{ marginTop: 12, alignItems: 'flex-start' }}>
          <div className="cv-field" style={{ flex: '1 1 220px' }}>
            <span className="cv-label">Start training job</span>
            <span className="cv-hint">
              Queues XGB training + hyperparameter search. Watch status below. Can take a long time and heavy CPU.
            </span>
            <button
              type="button"
              className="cv-btn"
              style={{ marginTop: 6 }}
              title="POST /api/ml/train/xgb with recommended universe"
              onClick={async () => {
                try {
                  const r = await startTrainXgbRecommended()
                  setJobId(r.job_id)
                } catch (e) {
                  alert('Failed to start training (is backend running?)')
                }
              }}
            >
              Train + auto-tune (recommended)
            </button>
          </div>
          <div className="cv-field" style={{ flex: '1 1 220px' }}>
            <span className="cv-label">Set active model</span>
            <span className="cv-hint">
              Click a row in the registry first. Active model is used for decisions and backtests for matching
              symbols.
            </span>
            <button
              type="button"
              className="cv-btn cv-btnPrimary"
              style={{ marginTop: 6 }}
              title="POST /api/ml/models/activate"
              onClick={async () => {
                if (!selectedModelId) {
                  alert('Select a model first.')
                  return
                }
                const res = await fetch(apiUrl('/api/ml/models/activate'), {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ model_id: selectedModelId }),
                })
                if (!res.ok) throw new Error('Failed to activate model')
              }}
            >
              Activate selected model
            </button>
          </div>
        </div>
      </div>

      {jobQ.data ? (
        <div className="cv-card">
          <div className="cv-cardTitle">Training job</div>
          {jobQ.data.status === 'succeeded' ? (
            <div className="cv-muted" style={{ marginTop: 6 }}>
              Evaluation summary for this run (same schema as <strong>Model evaluation</strong> below).
            </div>
          ) : null}
          <div className="cv-muted" style={{ marginTop: 10 }}>
            Job <code>{jobQ.data.job_id}</code> • Status:{' '}
            <span className="cv-tag cv-tagOk">{jobQ.data.status}</span>
            {jobSummary?.auc ? ` • AUC ${jobSummary.auc}` : ''}
            {jobSummary?.selected ? ` • Selected: ${jobSummary.selected}` : ''}
            {jobQ.data.model_id ? ` • Model: ${jobQ.data.model_id}` : ''}
          </div>
          {jobQ.data.error ? <div className="cv-muted">Error: {jobQ.data.error}</div> : null}
          {jobQ.data.status === 'succeeded' && jobMetricSections ? (
            <div className="cv-metricsGrid" style={{ marginTop: 14 }}>
              <MetricsSection title="Classification (hold-out test)" rows={jobMetricSections.classification} />
              <MetricsSection title="Validation (threshold search)" rows={jobMetricSections.validation} />
              <MetricsSection title="Simulated trading (test split)" rows={jobMetricSections.trading} />
              <MetricsSection title="Walk-forward estimate" rows={jobMetricSections.walkForward} />
              <MetricsSection title="Dataset & labels" rows={jobMetricSections.dataset} />
            </div>
          ) : null}
        </div>
      ) : null}

      {displayModel && selectedMetricSections ? (
        <div className="cv-card">
          <div className="cv-cardTitle">Model evaluation</div>
          <div className="cv-muted" style={{ marginTop: 6, lineHeight: 1.45 }}>
            Hold-out classification, validation threshold search, simulated test PnL, walk-forward estimate, and
            dataset/label info. Compare versions by clicking a row in the registry below.
          </div>
          <div className="cv-muted" style={{ marginTop: 8 }}>
            Showing <code>{displayModel.id}</code>
            {displayModel.active ? (
              <>
                {' '}
                <span className="cv-tag cv-tagOk">Active</span>
              </>
            ) : null}{' '}
            • interval {displayModel.interval} • symbols: {(displayModel.symbols ?? []).join(', ') || '—'}
          </div>
          <div className="cv-metricsGrid">
            <MetricsSection title="Classification (hold-out test)" rows={selectedMetricSections.classification} />
            <MetricsSection title="Validation (threshold search)" rows={selectedMetricSections.validation} />
            <MetricsSection title="Simulated trading (test split)" rows={selectedMetricSections.trading} />
            <MetricsSection title="Walk-forward estimate" rows={selectedMetricSections.walkForward} />
            <MetricsSection title="Dataset & labels" rows={selectedMetricSections.dataset} />
          </div>
          <button
            type="button"
            className="cv-btn"
            style={{ marginTop: 12 }}
            onClick={() => setShowFullMetricsJson((v) => !v)}
          >
            {showFullMetricsJson ? 'Hide' : 'Show'} full metrics JSON
          </button>
          {showFullMetricsJson ? (
            <pre className="cv-preJson">{JSON.stringify(displayModel.metrics, null, 2)}</pre>
          ) : null}
        </div>
      ) : !modelsQ.isLoading && !modelsQ.isError ? (
        <div className="cv-card">
          <div className="cv-cardTitle">Model evaluation</div>
          <div className="cv-muted" style={{ marginTop: 10 }}>
            No trained models in the registry yet. Run training above, then evaluation tables will appear here. Same
            data is returned by <code>GET /api/ml/models</code> (each model&apos;s <code>metrics</code> object). See
            TESTING_GUIDE.txt section <strong>5b) Model evaluation</strong>.
          </div>
        </div>
      ) : null}

      <div className="cv-card">
        <div className="cv-cardTitle">Recommended training universe (top-10 famous + growing)</div>
        <div className="cv-muted" style={{ marginTop: 10 }}>
          Curated symbols with high Binance liquidity and strong public/news coverage.
        </div>
        <div style={{ marginTop: 12, overflowX: 'auto' }}>
          {q.isLoading ? (
            <div className="cv-muted">Loading…</div>
          ) : q.isError ? (
            <div className="cv-muted">
              Backend not running yet. Start it and refresh this page.
            </div>
          ) : (
            <table className="cv-table">
              <thead>
                <tr>
                  <th align="left">Symbol</th>
                  <th align="left">Price</th>
                  <th align="left">24h %</th>
                  <th align="left">Quote vol</th>
                </tr>
              </thead>
              <tbody>
                {(q.data?.coins ?? []).map((c) => (
                  <tr key={c.symbol}>
                    <td>{c.symbol}</td>
                    <td>{c.last_price}</td>
                    <td>{c.price_change_percent_24h.toFixed(2)}%</td>
                    <td>{Math.round(c.quote_volume_24h).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="cv-card">
        <div className="cv-cardTitle">Model registry</div>
        <div style={{ marginTop: 12, overflowX: 'auto' }}>
          <table className="cv-table">
            <thead>
              <tr>
                <th align="left">ID</th>
                <th align="left">Kind</th>
                <th align="left">Metrics</th>
                <th align="left">Status</th>
              </tr>
            </thead>
            <tbody>
              {modelsQ.isLoading ? (
                <tr>
                  <td colSpan={4} className="cv-muted">
                    Loading…
                  </td>
                </tr>
              ) : modelsQ.isError ? (
                <tr>
                  <td colSpan={4} className="cv-muted">
                    Backend not running yet.
                  </td>
                </tr>
              ) : (
                (modelsQ.data?.models ?? []).map((m) => (
                  <tr
                    key={m.id}
                    onClick={() => setSelectedModelId(m.id)}
                    style={{
                      cursor: 'pointer',
                      outline:
                        displayModel?.id === m.id ? '1px solid rgba(73, 163, 255, 0.55)' : undefined,
                      background:
                        displayModel?.id === m.id ? 'rgba(73, 163, 255, 0.08)' : undefined,
                    }}
                    title="Click to select and view metrics above"
                  >
                    <td>{m.id}</td>
                    <td>{m.kind}</td>
                    <td>
                      AUC {Number(m.metrics.auc ?? 0).toFixed(3)} • P{' '}
                      {Number(m.metrics.precision ?? 0).toFixed(3)} • R{' '}
                      {Number(m.metrics.recall ?? 0).toFixed(3)} • F1{' '}
                      {Number(m.metrics.f1 ?? 0).toFixed(3)} • Thr{' '}
                      {Number(m.metrics.threshold ?? 0.5).toFixed(2)} • Selected{' '}
                      {String(m.metrics.selected ?? 'n/a')}
                    </td>
                    <td>
                      {m.active ? (
                        <span className="cv-tag cv-tagOk">Active</span>
                      ) : (
                        <span className="cv-tag">Inactive</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

