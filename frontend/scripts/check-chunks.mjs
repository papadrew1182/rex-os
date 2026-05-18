import { readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

const distAssetsDir = new URL('../dist/assets/', import.meta.url)
const thresholdKb = Number(process.env.REX_MAX_CHUNK_KB || 150)

const jsFiles = readdirSync(distAssetsDir)
  .filter((name) => name.endsWith('.js'))
  .map((name) => {
    const fullPath = join(distAssetsDir.pathname, name)
    const bytes = statSync(fullPath).size
    return {
      name,
      bytes,
      kb: bytes / 1024,
    }
  })
  .sort((a, b) => b.bytes - a.bytes)

if (jsFiles.length === 0) {
  console.error('No built JS assets found in frontend/dist/assets. Run `npm run build` first.')
  process.exit(1)
}

const oversized = jsFiles.filter((f) => f.kb > thresholdKb)

console.log(`Chunk budget check (max ${thresholdKb} kB)`)
for (const file of jsFiles.slice(0, 8)) {
  console.log(` - ${file.name}: ${file.kb.toFixed(2)} kB`)
}

if (oversized.length > 0) {
  console.error('\nChunk budget exceeded:')
  for (const file of oversized) {
    console.error(` - ${file.name}: ${file.kb.toFixed(2)} kB > ${thresholdKb} kB`)
  }
  process.exit(1)
}

console.log('\nChunk budget check passed.')
