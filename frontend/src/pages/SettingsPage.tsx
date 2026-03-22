import './page.css'

export function SettingsPage() {
  return (
    <div className="cv-page">
      <div className="cv-pageHeader">
        <div>
          <div className="cv-h1">Configure System Parameters</div>
          <div className="cv-sub">
            UC-01. Planned operator controls for symbols, risk, fusion weights, and sentiment veto. These are{' '}
            <strong>UI placeholders</strong> — persist to the backend in a future iteration; trading still uses
            API defaults unless you change code or env.
          </div>
        </div>
        <div className="cv-row">
          <button type="button" className="cv-btn" title="Not wired yet — resets form only in a future build">
            Reset
          </button>
          <button type="button" className="cv-btn cv-btnPrimary" title="Not wired yet — no API call">
            Save
          </button>
        </div>
      </div>

      <div className="cv-grid" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
        <div className="cv-card">
          <div className="cv-cardTitle">Trading universe</div>
          <div className="cv-formStack">
            <div className="cv-field">
              <label className="cv-label" htmlFor="st-universe">
                Training / watchlist universe
              </label>
              <span className="cv-hint">
                Which coin list the trainer and UI should prefer. <strong>Top-10 famous + growing</strong> matches
                the Models page &quot;recommended&quot; universe.
              </span>
              <select id="st-universe" className="cv-input" defaultValue="top10_famous_growing">
                <option value="top10_famous_growing">Top-10 famous + growing</option>
                <option value="recommended">Recommended (cheap + growing)</option>
                <option value="custom">Custom symbols</option>
              </select>
            </div>
            <div className="cv-field">
              <label className="cv-label" htmlFor="st-symbols">
                Symbols (comma-separated)
              </label>
              <span className="cv-hint">
                Binance-style pairs, e.g. <code>BTCUSDT, ETHUSDT</code>. No spaces after commas. Used when
                training or scanning is set to custom.
              </span>
              <input
                id="st-symbols"
                className="cv-input"
                defaultValue="BTCUSDT, ETHUSDT"
                placeholder="BTCUSDT, ETHUSDT, SOLUSDT"
              />
            </div>
            <div className="cv-field">
              <label className="cv-label" htmlFor="st-tf">
                Default timeframe
              </label>
              <span className="cv-hint">
                Candle resolution for features and training. Must match what your models were trained on (often{' '}
                <strong>1m</strong>).
              </span>
              <select id="st-tf" className="cv-input" defaultValue="1m">
                <option value="1m">1 minute</option>
                <option value="5m">5 minutes</option>
                <option value="15m">15 minutes</option>
                <option value="1h">1 hour</option>
              </select>
            </div>
          </div>
        </div>

        <div className="cv-card">
          <div className="cv-cardTitle">Risk manager</div>
          <div className="cv-formStack">
            <div className="cv-field">
              <label className="cv-label" htmlFor="st-exposure">
                Max daily exposure (USDT)
              </label>
              <span className="cv-hint">
                Intended cap on notional risk per day (paper/live). Set a level you can afford to lose in tests;
                typical starter: <strong>100–1000</strong> USDT.
              </span>
              <input
                id="st-exposure"
                className="cv-input"
                defaultValue="1000"
                placeholder="1000"
                inputMode="decimal"
              />
            </div>
            <div className="cv-field">
              <label className="cv-label" htmlFor="st-sl-pct">
                Stop-loss (% of position)
              </label>
              <span className="cv-hint">
                Percentage drawdown from entry before a hard exit (conceptual; wire to engine later). Example:{' '}
                <strong>1.2</strong> = 1.2%.
              </span>
              <input
                id="st-sl-pct"
                className="cv-input"
                defaultValue="1.2"
                placeholder="1.2"
              />
            </div>
            <div className="cv-field">
              <span className="cv-label">Emergency stop</span>
              <span className="cv-hint">
                Stops automation / paper broker (when connected). Use only if you need to halt all activity
                immediately.
              </span>
              <button type="button" className="cv-btn" style={{ width: '100%' }} title="Not wired to backend yet">
                Stop all trading (kill switch)
              </button>
            </div>
          </div>
        </div>

        <div className="cv-card">
          <div className="cv-cardTitle">Hybrid fusion</div>
          <div className="cv-muted" style={{ marginTop: 6, lineHeight: 1.45 }}>
            Rule-based score and ML score are blended in the backend. Weights should sum to <strong>1.0</strong> for
            a balanced interpretation.
          </div>
          <div className="cv-formStack">
            <div className="cv-field">
              <label className="cv-label" htmlFor="st-w-rules">
                Rules weight (0–1)
              </label>
              <span className="cv-hint">
                Weight on technical / rule signal. Default in API is often <strong>0.45</strong>. Raise if you trust
                indicators more than the model.
              </span>
              <input id="st-w-rules" className="cv-input" defaultValue="0.45" placeholder="0.45" />
            </div>
            <div className="cv-field">
              <label className="cv-label" htmlFor="st-w-ml">
                ML weight (0–1)
              </label>
              <span className="cv-hint">
                Weight on XGBoost probability-derived score. Default <strong>0.55</strong>. Should pair with rules so
                total ≈ 1.
              </span>
              <input id="st-w-ml" className="cv-input" defaultValue="0.55" placeholder="0.55" />
            </div>
          </div>
        </div>

        <div className="cv-card">
          <div className="cv-cardTitle">Sentiment risk veto</div>
          <div className="cv-muted" style={{ marginTop: 6, lineHeight: 1.45 }}>
            When compound sentiment falls below this threshold, the system can block or downgrade trades (see
            trading decision API).
          </div>
          <div className="cv-formStack">
            <div className="cv-field">
              <label className="cv-label" htmlFor="st-veto">
                Veto threshold (−1 … +1)
              </label>
              <span className="cv-hint">
                VADER-style compound score. More negative = stricter (more vetoes). Typical: <strong>−0.35</strong>.{' '}
                Closer to <strong>0</strong> = fewer vetoes.
              </span>
              <input id="st-veto" className="cv-input" defaultValue="-0.35" placeholder="-0.35" />
            </div>
            <div className="cv-field">
              <label className="cv-label" htmlFor="st-cooldown">
                Cooldown (minutes)
              </label>
              <span className="cv-hint">
                Minimum time between veto-related actions or alerts (placeholder). Example: <strong>15</strong>{' '}
                minutes.
              </span>
              <input id="st-cooldown" className="cv-input" defaultValue="15" placeholder="15" min={1} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
