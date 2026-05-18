import { existsSync } from 'node:fs'
import { spawnSync } from 'node:child_process'

const releaseSha =
  process.env.REX_RELEASE ||
  process.env.VERCEL_GIT_COMMIT_SHA ||
  process.env.RAILWAY_GIT_COMMIT_SHA ||
  process.env.GITHUB_SHA ||
  'dev'

const release = `rex-os-frontend@${releaseSha}`
const distDir = new URL('../dist', import.meta.url)

if (!existsSync(distDir)) {
  console.error('Missing frontend/dist. Run `npm run build` before sourcemap upload.')
  process.exit(1)
}

const required = ['SENTRY_AUTH_TOKEN', 'SENTRY_ORG', 'SENTRY_PROJECT']
const missing = required.filter((key) => !process.env[key])
if (missing.length) {
  console.error(
    `Missing Sentry env var(s): ${missing.join(', ')}. ` +
      'Set them before running `npm run sentry:upload-sourcemaps`.'
  )
  process.exit(1)
}

const args = [
  '@sentry/cli',
  'releases',
  'files',
  release,
  'upload-sourcemaps',
  distDir.pathname,
  '--url-prefix',
  '~/assets',
  '--rewrite',
  '--validate',
]

console.log(`Uploading frontend sourcemaps for release ${release}`)
const result = spawnSync('npx', args, { stdio: 'inherit', env: process.env })

if (result.status !== 0) {
  process.exit(result.status ?? 1)
}

console.log('Sourcemap upload completed successfully.')