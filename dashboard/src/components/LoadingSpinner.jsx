export default function LoadingSpinner({ message = 'Running security analysis…' }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <div className="loading__spinner" aria-hidden="true" />
      <p>{message}</p>
      <p className="loading__hint">Parsing logs, indexing patterns, and querying Azure OpenAI.</p>
    </div>
  )
}
