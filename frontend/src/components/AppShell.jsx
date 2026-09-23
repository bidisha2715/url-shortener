function AppShell({ children }) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="brand-mark" aria-hidden="true">↗</span>
        <span className="brand-name">Shortform</span>
        <span className="environment-label">Frontend foundation</span>
      </header>
      <main>{children}</main>
    </div>
  )
}

export default AppShell
