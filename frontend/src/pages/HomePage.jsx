function HomePage() {
  return (
    <section className="placeholder-page" aria-labelledby="page-title">
      <p className="eyebrow">Stage 4 / foundation</p>
      <h1 id="page-title">The React workspace is ready.</h1>
      <p className="intro">
        This client is connected to the Flask API layer through Vite&apos;s local
        development proxy. URL management and analytics views will be added next.
      </p>
      <div className="status-row">
        <span className="status-dot" aria-hidden="true" />
        <span>React + Vite running</span>
      </div>
    </section>
  )
}

export default HomePage
