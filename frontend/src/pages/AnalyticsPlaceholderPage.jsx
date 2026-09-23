function AnalyticsPlaceholderPage({ navigate }) {
  return (
    <section className="dashboard-page" aria-labelledby="analytics-title">
      <p className="eyebrow">Stage 4.4</p>
      <h1 id="analytics-title">Analytics are next.</h1>
      <p className="intro">The analytics API is ready. Charts and detailed reporting will be added in the next frontend stage.</p>
      <button className="secondary-button" type="button" onClick={() => navigate('/dashboard')}>Back to dashboard</button>
    </section>
  )
}

export default AnalyticsPlaceholderPage
