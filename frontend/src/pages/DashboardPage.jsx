function DashboardPage({ user, onLogout }) {
  return (
    <section className="dashboard-page" aria-labelledby="dashboard-title">
      <p className="eyebrow">Private workspace</p>
      <h1 id="dashboard-title">Your dashboard is ready.</h1>
      <p className="intro">You are signed in as {user?.username || 'your account'}. URL management will arrive in the next stage.</p>
      <button className="secondary-button" type="button" onClick={onLogout}>Log out</button>
    </section>
  )
}

export default DashboardPage
