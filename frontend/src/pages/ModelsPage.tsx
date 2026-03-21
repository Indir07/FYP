import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import './page.css'

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
    const res = await fetch('http://localhost:8000/api/coins/recommended?strategy=top10_famous_growing&limit=10')
    if (!res.ok) return fallback
    const data = (await res.json()) as RecommendedResponse
    return data.coins?.length ? data : fallback
  } catch {
    return fallback
  }
}

async function startTrainXgbRecommended(): Promise<{ job_id: string }> {
  const res = await fetch('http://localhost:8000/api/ml/train/xgb', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      universe: 'top10_famous_growing',
      limit: 10,
      interval: '1m',
      limit_per_symbol: 750,
      tune: true,
      tune_trials: 25,
      optimize_metric: 'accuracy',
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
  const res = await fetch('http://localhost:8000/api/ml/models')
  if (!res.ok) throw new Error('Failed to fetch models')
  return res.json()
}

async function fetchJob(jobId: string): Promise<JobStatus> {
  const res = await fetch(`http://localhost:8000/api/ml/jobs/${jobId}`)
  if (!res.ok) throw new Error('Failed to fetch job')
  return res.json()
}

export function ModelsPage() {
  const q = useQuery({ queryKey: ['coins', 'recommended'], queryFn: fetchRecommended })
  const modelsQ = useQuery({ queryKey: ['ml', 'models'], queryFn: fetchModels, refetchInterval: 5000 })
  const [jobId, setJobId] = useState<string | null>(null)
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null)
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

  return (
    <div className="cv-page">
      <div className="cv-pageHeader">
        <div>
          <div className="cv-h1">Manage Model Training & Version Selection</div>
          <div className="cv-sub">
            UC-06. Train models on top-10 famous, liquid, and growth-focused coins and activate a version.
          </div>
        </div>
        <div className="cv-row">
          <button
            className="cv-btn"
            onClick={async () => {
              try {
                const r = await startTrainXgbRecommended()
                setJobId(r.job_id)
              } catch (e) {
                alert('Failed to start training (is backend running?)')
              }
            }}
          >
            Train + Auto-tune (recommended)
          </button>
          <button
            className="cv-btn cv-btnPrimary"
            onClick={async () => {
              if (!selectedModelId) {
                alert('Select a model first.')
                return
              }
              const res = await fetch('http://localhost:8000/api/ml/models/activate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_id: selectedModelId }),
              })
              if (!res.ok) throw new Error('Failed to activate model')
              // modelsQ refetches automatically (refetchInterval=5000).
            }}
          >
            Activate selected
          </button>
        </div>
      </div>

      {jobQ.data ? (
        <div className="cv-card">
          <div className="cv-cardTitle">Training job</div>
          <div className="cv-muted" style={{ marginTop: 10 }}>
            Job <code>{jobQ.data.job_id}</code> • Status:{' '}
            <span className="cv-tag cv-tagOk">{jobQ.data.status}</span>
            {jobSummary?.auc ? ` • AUC ${jobSummary.auc}` : ''}
            {jobSummary?.selected ? ` • Selected: ${jobSummary.selected}` : ''}
            {jobQ.data.model_id ? ` • Model: ${jobQ.data.model_id}` : ''}
          </div>
          {jobQ.data.error ? <div className="cv-muted">Error: {jobQ.data.error}</div> : null}
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
                    style={{ cursor: 'pointer', opacity: selectedModelId && selectedModelId !== m.id ? 0.9 : 1 }}
                    title="Click to select"
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

