import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { Activity, AlertTriangle, Bot, Settings, TestTube } from 'lucide-react'
import './appShell.css'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: Activity },
  { to: '/settings', label: 'Settings', icon: Settings },
  { to: '/models', label: 'Models', icon: Bot },
  { to: '/backtesting', label: 'Backtesting', icon: TestTube },
  { to: '/alerts', label: 'Alerts', icon: AlertTriangle },
] as const

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="cv-shell">
      <aside className="cv-sidebar">
        <div className="cv-brand">
          <div className="cv-brandMark" aria-hidden="true">
            CV
          </div>
          <div>
            <div className="cv-brandName">CryptoVolt</div>
            <div className="cv-brandSub">AI trading (paper mode)</div>
          </div>
        </div>

        <nav className="cv-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                ['cv-navItem', isActive ? 'is-active' : ''].join(' ')
              }
            >
              <item.icon size={18} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="cv-sidebarFooter">
          <div className="cv-pill">
            <span className="cv-pillDot" />
            Backend: connecting…
          </div>
        </div>
      </aside>

      <main className="cv-main">
        <div className="cv-topbar">
          <div className="cv-topbarTitle">Operator UI</div>
          <div className="cv-topbarMeta">
            <span className="cv-badge">TLS</span>
            <span className="cv-badge">Audit logs</span>
            <span className="cv-badge">Kill switch</span>
          </div>
        </div>
        <div className="cv-content">{children}</div>
      </main>
    </div>
  )
}

