import AppShell from './components/AppShell'
import ProtectedRoute from './components/ProtectedRoute'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { useEffect, useState } from 'react'
import DashboardPage from './pages/DashboardPage'
import AnalyticsPlaceholderPage from './pages/AnalyticsPlaceholderPage'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import './App.css'

function RoutedApp() {
  const { user, signIn, signOut } = useAuth()
  const [path, setPath] = useState(window.location.pathname)
  useEffect(() => {
    const handlePopState = () => setPath(window.location.pathname)
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])
  const navigate = (nextPath) => {
    window.history.pushState({}, '', nextPath)
    setPath(nextPath)
  }

  const page = path === '/login'
    ? <LoginPage navigate={navigate} onAuthenticated={signIn} />
    : path === '/register'
      ? <RegisterPage navigate={navigate} onAuthenticated={signIn} />
      : path === '/dashboard'
        ? <ProtectedRoute navigate={navigate}><DashboardPage user={user} onLogout={() => signOut().then(() => navigate('/login'))} /></ProtectedRoute>
        : path.startsWith('/analytics/')
          ? <ProtectedRoute navigate={navigate}><AnalyticsPlaceholderPage navigate={navigate} /></ProtectedRoute>
        : <HomePage />

  return (
    <AppShell user={user} onNavigate={navigate} onLogout={() => signOut().then(() => navigate('/login'))}>
      {page}
    </AppShell>
  )
}

function App() {
  return <AuthProvider><RoutedApp /></AuthProvider>
}

export default App
