import { useEffect } from 'react'
import { useAuth } from '../auth/AuthContext'

function ProtectedRoute({ children, navigate }) {
  const { user, isLoading } = useAuth()

  useEffect(() => {
    if (!isLoading && !user) navigate('/login')
  }, [isLoading, user, navigate])

  if (isLoading) {
    return <p className="route-message">Checking your session...</p>
  }

  if (!user) {
    return null
  }

  return children
}

export default ProtectedRoute