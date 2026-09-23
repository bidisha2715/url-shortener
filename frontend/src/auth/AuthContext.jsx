import { createContext, useContext, useEffect, useState } from 'react'
import { ApiError, api } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    api.get('/api/urls')
      .then(() => setUser({ authenticated: true }))
      .catch((error) => {
        if (!(error instanceof ApiError && error.status === 401)) {
          console.error('Could not restore the Flask session', error)
        }
        setUser(null)
      })
      .finally(() => setIsLoading(false))
  }, [])

  const signIn = (authenticatedUser) => setUser(authenticatedUser)

  const signOut = async () => {
    try {
      await api.post('/api/auth/logout')
    } finally {
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}