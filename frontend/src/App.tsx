import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { DashboardPage } from './pages/DashboardPage.tsx'
import { SettingsPage } from './pages/SettingsPage.tsx'
import { ModelsPage } from './pages/ModelsPage.tsx'
import { BacktestingPage } from './pages/BacktestingPage.tsx'
import { AlertsPage } from './pages/AlertsPage.tsx'
import { LoginPage } from './pages/LoginPage.tsx'
import { SignupPage } from './pages/SignupPage.tsx'
import { RequireAuth } from './components/auth/RequireAuth.tsx'
import { isAuthenticated } from './lib/auth'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route
        path="/auth"
        element={<Navigate to={isAuthenticated() ? '/dashboard' : '/login'} replace />}
      />

      <Route
        path="*"
        element={
          <RequireAuth>
            <AppShell>
              <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/models" element={<ModelsPage />} />
                <Route path="/backtesting" element={<BacktestingPage />} />
                <Route path="/alerts" element={<AlertsPage />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </AppShell>
          </RequireAuth>
        }
      />
    </Routes>
  )
}
