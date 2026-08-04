import { useEffect, useState } from 'react'

import {
  analyzeLogFile,
  clearSession,
  fetchAuthConfig,
  getUsername,
  validateSession,
} from './api/auth'
import AnalyzeButton from './components/AnalyzeButton'
import FileUpload from './components/FileUpload'
import LoadingSpinner from './components/LoadingSpinner'
import LoginPage from './components/LoginPage'
import ResultDisplay from './components/ResultDisplay'
import './App.css'

export default function App() {
  const [authReady, setAuthReady] = useState(false)
  const [loginRequired, setLoginRequired] = useState(true)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [username, setUsername] = useState(getUsername())

  const [selectedFile, setSelectedFile] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function bootstrapAuth() {
      try {
        const config = await fetchAuthConfig()
        setLoginRequired(config.login_required)

        if (!config.login_required) {
          setIsAuthenticated(true)
          return
        }

        const valid = await validateSession()
        setIsAuthenticated(valid)
        if (valid) {
          setUsername(getUsername())
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to initialize authentication')
      } finally {
        setAuthReady(true)
      }
    }

    bootstrapAuth()
  }, [])

  async function handleAnalyze() {
    if (!selectedFile) {
      setError('Please select a log file first.')
      return
    }

    try {
      setIsLoading(true)
      setError(null)
      setResult(null)

      const data = await analyzeLogFile(selectedFile)
      setResult(data)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Analysis failed'
      setError(message)

      if (message.includes('sign in again')) {
        setIsAuthenticated(false)
        setUsername(null)
      }
    } finally {
      setIsLoading(false)
    }
  }

  function handleFileSelect(file) {
    setSelectedFile(file)
    setError(null)
    setResult(null)
  }

  function handleLoginSuccess() {
    setIsAuthenticated(true)
    setUsername(getUsername())
    setError(null)
  }

  function handleLogout() {
    clearSession()
    setIsAuthenticated(false)
    setUsername(null)
    setSelectedFile(null)
    setResult(null)
    setError(null)
  }

  if (!authReady) {
    return (
      <div className="app">
        <LoadingSpinner message="Loading dashboard…" />
      </div>
    )
  }

  if (loginRequired && !isAuthenticated) {
    return <LoginPage onSuccess={handleLoginSuccess} />
  }

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__header-row">
          <div>
            <p className="app__eyebrow">LogSentinel</p>
            <h1>Security Log Analysis Dashboard</h1>
            <p className="app__subtitle">
              Upload access logs, detect suspicious patterns, and get AI-powered recommendations.
            </p>
          </div>

          {loginRequired && (
            <div className="session-bar">
              <span>Signed in as {username}</span>
              <button type="button" className="logout-button" onClick={handleLogout}>
                Sign out
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="app__main">
        <section className="panel">
          <FileUpload selectedFile={selectedFile} onFileSelect={handleFileSelect} />
          <AnalyzeButton
            onAnalyze={handleAnalyze}
            disabled={!selectedFile}
            isLoading={isLoading}
          />
        </section>

        {error && (
          <div className="alert alert--error" role="alert">
            {error}
          </div>
        )}

        {isLoading && <LoadingSpinner />}

        {!isLoading && <ResultDisplay result={result} />}
      </main>
    </div>
  )
}
