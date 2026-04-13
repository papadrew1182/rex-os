import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import { VERSION_INFO } from './version.js'

// Expose build identity on window so ops/support can read it from any
// browser console without opening DevTools source maps. Intentionally
// read-only.
if (typeof window !== 'undefined') {
  Object.defineProperty(window, '__REX_VERSION__', {
    value: VERSION_INFO,
    writable: false,
    configurable: false,
  })
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
