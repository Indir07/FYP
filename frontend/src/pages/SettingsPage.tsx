import './page.css'

export function SettingsPage() {
  return (
    <div className="cv-page">
      <div className="cv-pageHeader">
        <div>
          <div className="cv-h1">Configure System Parameters</div>
          <div className="cv-sub">
            UC-01. Configure trading symbols, risk exposure, fusion weights, and sentiment veto
            thresholds. (UI wired to backend soon.)
          </div>
        </div>
        <div className="cv-row">
          <button className="cv-btn">Reset</button>
          <button className="cv-btn cv-btnPrimary">Save</button>
        </div>
      </div>

      <div className="cv-grid" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
        <div className="cv-card">
          <div className="cv-cardTitle">Trading</div>
          <div style={{ marginTop: 12, display: 'grid', gap: 12 }}>
            <label>
              <div className="cv-muted">Training universe</div>
              <select className="cv-input" defaultValue="top10_famous_growing">
                <option value="top10_famous_growing">Top-10 famous + growing</option>
                <option value="recommended">Recommended (cheap + growing)</option>
                <option value="custom">Custom symbols</option>
              </select>
            </label>
            <label>
              <div className="cv-muted">Symbols (comma-separated)</div>
              <input className="cv-input" defaultValue="BTCUSDT, ETHUSDT" />
            </label>
            <label>
              <div className="cv-muted">Timeframe</div>
              <select className="cv-input" defaultValue="1m">
                <option value="1m">1m</option>
                <option value="5m">5m</option>
                <option value="15m">15m</option>
                <option value="1h">1h</option>
              </select>
            </label>
          </div>
        </div>

        <div className="cv-card">
          <div className="cv-cardTitle">Risk Manager</div>
          <div style={{ marginTop: 12, display: 'grid', gap: 12 }}>
            <label>
              <div className="cv-muted">Max daily exposure (USDT)</div>
              <input className="cv-input" defaultValue="1000" />
            </label>
            <label>
              <div className="cv-muted">Stop-loss (%)</div>
              <input className="cv-input" defaultValue="1.2" />
            </label>
            <label>
              <div className="cv-muted">Kill switch</div>
              <button className="cv-btn" style={{ width: '100%' }}>
                Stop all trading
              </button>
            </label>
          </div>
        </div>

        <div className="cv-card">
          <div className="cv-cardTitle">Hybrid Fusion</div>
          <div className="cv-muted" style={{ marginTop: 10 }}>
            Combine rule signals + ML confidence into a final decision.
          </div>
          <div style={{ marginTop: 12, display: 'grid', gap: 12 }}>
            <label>
              <div className="cv-muted">Rules weight</div>
              <input className="cv-input" defaultValue="0.45" />
            </label>
            <label>
              <div className="cv-muted">ML weight</div>
              <input className="cv-input" defaultValue="0.55" />
            </label>
          </div>
        </div>

        <div className="cv-card">
          <div className="cv-cardTitle">Sentiment Risk Veto</div>
          <div className="cv-muted" style={{ marginTop: 10 }}>
            Downgrade or block execution under elevated sentiment/volatility risk.
          </div>
          <div style={{ marginTop: 12, display: 'grid', gap: 12 }}>
            <label>
              <div className="cv-muted">Veto threshold (-1..1)</div>
              <input className="cv-input" defaultValue="-0.35" />
            </label>
            <label>
              <div className="cv-muted">Cooldown (minutes)</div>
              <input className="cv-input" defaultValue="15" />
            </label>
          </div>
        </div>
      </div>
    </div>
  )
}

