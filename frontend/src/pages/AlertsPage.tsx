import { useQuery } from '@tanstack/react-query'
import './page.css'
import { apiUrl } from '../lib/apiBase'

export function AlertsPage() {
  const alertsQ = useQuery({
    queryKey: ['alerts', 'recent'],
    queryFn: async () => {
      const res = await fetch(apiUrl('/api/alerts/recent?limit=50'))
      if (!res.ok) throw new Error('Failed to fetch alerts')
      return res.json() as Promise<{
        alerts: Array<{ ts: string; type: string; message: string; discord_sent?: boolean }>
      }>
    },
    refetchInterval: 3000,
  })

  const alerts = alertsQ.data?.alerts ?? []

  return (
    <div className="cv-page">
      <div className="cv-pageHeader">
        <div>
          <div className="cv-h1">Alerts & Notifications</div>
          <div className="cv-sub">
            UC-04. Alerts are stored in the database and optionally sent to Discord when{' '}
            <code>DISCORD_WEBHOOK_URL</code> is set.
          </div>
        </div>
        <div className="cv-row" style={{ alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div className="cv-field" style={{ flex: '1 1 280px', maxWidth: 480 }}>
            <span className="cv-label">Test notification</span>
            <span className="cv-hint">
              Writes a row to the <strong>alerts</strong> table and, if <code>DISCORD_WEBHOOK_URL</code> is set in
              <code>.env</code>, posts a test message to your Discord channel.
            </span>
          </div>
          <button
            type="button"
            className="cv-btn"
            title="POST /api/alerts/test — requires backend running"
            onClick={async () => {
              await fetch(apiUrl('/api/alerts/test'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  title: 'CryptoVolt alert test',
                  message: 'If you see this on Discord, webhook + backend alerts are working.',
                  send_to_discord: true,
                }),
              })
            }}
          >
            Send test alert (DB + Discord)
          </button>
        </div>
      </div>

      <div className="cv-card">
        <div className="cv-cardTitle">Recent alerts</div>
        <div style={{ marginTop: 12, overflowX: 'auto' }}>
          <table className="cv-table">
            <thead>
              <tr>
                <th align="left">Time (UTC)</th>
                <th align="left">Type</th>
                <th align="left">Message</th>
                <th align="left">Discord</th>
              </tr>
            </thead>
            <tbody>
              {alertsQ.isLoading ? (
                <tr>
                  <td colSpan={4} className="cv-muted">
                    Loading…
                  </td>
                </tr>
              ) : alertsQ.isError ? (
                <tr>
                  <td colSpan={4} className="cv-muted">
                    Backend not running?
                  </td>
                </tr>
              ) : alerts.length === 0 ? (
                <tr>
                  <td colSpan={4} className="cv-muted">
                    No alerts yet. Start automation or submit a paper trade.
                  </td>
                </tr>
              ) : (
                alerts.map((a, idx) => (
                  <tr key={`${a.ts}-${idx}`}>
                    <td>{a.ts}</td>
                    <td>
                      <span className="cv-tag">{a.type}</span>
                    </td>
                    <td>{a.message}</td>
                    <td className="cv-muted">
                      {a.discord_sent ? 'sent / attempted' : '—'}
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

