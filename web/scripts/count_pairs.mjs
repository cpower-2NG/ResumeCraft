// Count how the paginator chose to lay out each export: full-width section rows vs
// paired rows (two sections side by side), and which sections got paired.
//
// The pair markup is <div class="pair"><section…><section…></div>, so each pair has
// to be extracted with balanced-tag matching — splitting on the opening tag (the
// first version of this script) swallows every following full-width section into the
// last pair and reports nonsense.
// Usage: node scripts/count_pairs.mjs <dir>
import { readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const dir = resolve(process.argv[2] || '../output/tmp')
const files = readdirSync(dir).filter(f => f.endsWith('.html') && !f.includes('probe')).sort()

// Body of each <div class="pair">…</div>, with nested divs accounted for.
const pairsIn = (html) => {
  const out = []
  for (let at = html.indexOf('<div class="pair">'); at !== -1; at = html.indexOf('<div class="pair">', at + 1)) {
    let depth = 0
    let index = at
    while (index < html.length) {
      const open = html.indexOf('<div', index)
      const close = html.indexOf('</div>', index)
      if (close === -1) break
      if (open !== -1 && open < close) { depth++; index = open + 4; continue }
      depth--; index = close + 6
      if (depth === 0) break
    }
    out.push(html.slice(at, index))
  }
  return out
}
const headingsOf = (chunk) => [...chunk.matchAll(/<h2>([^<]*)<\/h2>/g)].map(m => m[1].replace('（续）', ''))

console.log('file                pages  full  pairs  paired sections')
const totals = { full: 0, pairs: 0 }
for (const file of files) {
  const html = readFileSync(join(dir, file), 'utf-8')
  const pages = html.split('<section class="page').slice(1)
  const pairs = pairsIn(html)
  // Full-width rows = every section heading, minus the ones living inside a pair.
  const allHeadings = pages.reduce((sum, page) => sum + headingsOf(page).length, 0)
  const pairedHeadings = pairs.reduce((sum, pair) => sum + headingsOf(pair).length, 0)
  const full = allHeadings - pairedHeadings
  totals.full += full
  totals.pairs += pairs.length
  console.log(`${file.replace('.html', '').padEnd(20)}${String(pages.length).padEnd(7)}${String(full).padEnd(6)}${String(pairs.length).padEnd(7)}${pairs.map(p => headingsOf(p).join('+')).join('  ')}`)
}
console.log(`\n全宽栏目行 ${totals.full}，并排行 ${totals.pairs}（并排行占 ${Math.round(totals.pairs / (totals.full + totals.pairs) * 100)}%）`)
