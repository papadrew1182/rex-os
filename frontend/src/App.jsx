import { useState, useEffect } from 'react'

function App() {
  const [health, setHealth] = useState(null)

  useEffect(() => {
    fetch('/api/health')
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(setHealth)
      .catch(() => setHealth({ status: 'unreachable' }))
  }, [])

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: '2rem', maxWidth: 600 }}>
      <h1>Rex OS</h1>
      <p style={{ color: '#666' }}>Construction management platform — clean slate.</p>
      <hr />
      <h3>API Health</h3>
      {health ? (
        <pre style={{ background: '#f4f4f4', padding: '1rem', borderRadius: 6 }}>
          {JSON.stringify(health, null, 2)}
        </pre>
      ) : (
        <p>Checking...</p>
      )}
    </div>
  )
}

export default App
