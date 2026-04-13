// Build-time constants injected by vite.config.js via `define`.
// These are string literals at runtime — importing this module is cheap
// and safe in any context (no side effects).
//
// Usage: read GIT_SHA / BUILD_TIME anywhere in the app. Also exposed on
// `window.__REX_VERSION__` from main.jsx so support / ops can read the
// running build from a browser console without needing devtools source
// maps.

/* global __REX_GIT_SHA__, __REX_BUILD_TIME__ */

export const GIT_SHA =
  typeof __REX_GIT_SHA__ !== 'undefined' ? __REX_GIT_SHA__ : 'dev'

export const BUILD_TIME =
  typeof __REX_BUILD_TIME__ !== 'undefined' ? __REX_BUILD_TIME__ : ''

export const VERSION_INFO = Object.freeze({
  service: 'rex-os-frontend',
  commit: GIT_SHA,
  build_time: BUILD_TIME,
})
