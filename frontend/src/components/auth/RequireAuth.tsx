import type { ReactElement } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { isAuthenticated } from '../../lib/auth'

export function RequireAuth({ children }: { children: ReactElement }) {
  const location = useLocation()
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return children
}

