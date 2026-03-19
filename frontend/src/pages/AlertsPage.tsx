import { useQuery } from '@tanstack/react-query'
import './page.css'

export function AlertsPage() {
  const alertsQ = useQuery({
    queryKey: ['alerts', 'recent'],
    queryFn: async () => {
      const res = await fetch('http://localhost:8000/api/alerts/recent?limit=50')
      if (!res.ok) throw new Error('Failed to fetch alerts')
      return res.json() as Promise<{ alerts: Array<{ ts: string; type: string; message: string }> }>
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
            UC-04. Alerts are delivered via Discord + stored for audit and reproducibility.
          </div>
        </div>
        <div className="cv-row">
          <button
            className="cv-btn"
            onClick={async () => {
              await fetch('http://localhost:8000/api/alerts/test', {
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
            Test Discord webhook
          </button>
        </div>
      </div>

      <div className="cv-card">
        <div className="cv-cardTitle">Recent alerts</div>
        <div style={{ marginTop: 12, overflowX: 'auto' }}>
          <table className="cv-table">
            <thead>
              <tr>
                <th align="left">Time</th>
                <th align="left">Type</th>
                <th align="left">Message</th>
              </tr>
            </thead>
            <tbody>
              {alertsQ.isLoading ? (
                <tr>
                  <td colSpan={3} className="cv-muted">
                    Loading…
                  </td>
                </tr>
              ) : alertsQ.isError ? (
                <tr>
                  <td colSpan={3} className="cv-muted">
                    Backend not running?
                  </td>
                </tr>
              ) : alerts.length === 0 ? (
                <tr>
                  <td colSpan={3} className="cv-muted">
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

