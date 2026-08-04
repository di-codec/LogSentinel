import ReactMarkdown from 'react-markdown'

export default function ResultDisplay({ result }) {
  if (!result) {
    return null
  }

  return (
    <section className="result">
      <div className="result__metrics">
        <div className="metric-card">
          <span className="metric-card__label">Records processed</span>
          <strong className="metric-card__value">{result.records_processed}</strong>
        </div>
        <div className="metric-card">
          <span className="metric-card__label">Similar patterns found</span>
          <strong className="metric-card__value">{result.similar_patterns_found}</strong>
        </div>
      </div>

      <article className="result__analysis markdown">
        <h2>Security analysis</h2>
        <ReactMarkdown>{result.analysis}</ReactMarkdown>
      </article>
    </section>
  )
}
