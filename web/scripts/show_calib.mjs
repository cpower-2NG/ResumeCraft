// Print the LAYOUT_METRICS-relevant numbers from a calib.json measurement.
import { readFileSync } from 'node:fs'

const rows = JSON.parse(readFileSync(process.argv[2] || '../output/tmp/calib.json', 'utf-8'))
const round = v => (typeof v === 'number' ? Math.round(v * 10) / 10 : v)
console.log('probe     cpl   pcpl  meta  pmeta base  hdr   hdrF  budget title   side')
for (const r of rows) {
  const s = r.side
    ? `chars=${r.side.charsPerLine} meta=${r.side.metaChars} base=${r.side.base} hdr=${r.side.header} head=${r.side.head} line=${r.side.line}`
    : '—'
  console.log(
    r.template.padEnd(10),
    String(round(r.charsPerLine)).padEnd(5),
    String(round(r.pairCharsPerLine)).padEnd(5),
    String(round(r.metaChars)).padEnd(5),
    String(round(r.pairMetaChars)).padEnd(5),
    String(r.base).padEnd(5),
    String(round(r.header)).padEnd(5),
    String(r.headerFirst).padEnd(5),
    String(r.budget).padEnd(6),
    String(r.titleRow).padEnd(7),
    s,
  )
}
