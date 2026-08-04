export default function AnalyzeButton({ onAnalyze, disabled, isLoading }) {
  return (
    <button
      type="button"
      className="analyze-button"
      onClick={onAnalyze}
      disabled={disabled || isLoading}
    >
      {isLoading ? 'Analyzing…' : 'Analyze logs'}
    </button>
  )
}
