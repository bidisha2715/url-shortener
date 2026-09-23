function AppShell({ children, user, onNavigate, onLogout }) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="brand-mark" aria-hidden="true">↗</span>
        <span className="brand-name">Shortform</span>
        <span className="environment-label">Frontend foundation</span>
        <nav className="app-nav" aria-label="Primary navigation">
          {user ? (
            <>
              <button type="button" onClick={() => onNavigate('/dashboard')}>Dashboard</button>
              <button type="button" onClick={onLogout}>Log out</button>
            </>
          ) : (
            <>
              <button type="button" onClick={() => onNavigate('/login')}>Log in</button>
              <button type="button" onClick={() => onNavigate('/register')}>Register</button>
            </>
          )}
        </nav>
      </header>
      <main>{children}</main>
    </div>
  )
}

export default AppShell
