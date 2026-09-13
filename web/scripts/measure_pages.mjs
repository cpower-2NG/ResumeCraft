// Measure per-page CONTENT height (leaf nodes only) and clipped overflow of
// export HTML files. Usage: node measure_pages.mjs <dir>
// - overflow: main/sidebar scrollHeight - clientHeight (clipped content px)
// - fill%: lowest leaf bottom (section/block/head nodes) vs page height
import { chromium } from 'playwright'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const dir = process.argv[2] || '../output/tmp'
const files = readdirSync(dir).filter(f => f.endsWith('.html')).sort()

const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const page = await browser.newPage({ viewport: { width: 1200, height: 1400 } })

const results = {}
for (const file of files) {
  const html = readFileSync(join(dir, file), 'utf-8')
  await page.setContent(html, { waitUntil: 'load' })
  const metrics = await page.evaluate(() => {
    const LEAF = '.section,.block,.t-body,.grid-head,.line-head,.page-banner,h1,.side-copy'
    return Array.from(document.querySelectorAll('.page')).map(p => {
      const pr = p.getBoundingClientRect()
      const pageTop = pr.top
      let bottom = 0
      p.querySelectorAll(LEAF).forEach(el => {
        const r = el.getBoundingClientRect()
        if (r.height > 0) bottom = Math.max(bottom, r.bottom - pageTop)
      })
      let overflow = 0
      p.querySelectorAll('.main,.sidebar').forEach(el => {
        overflow = Math.max(overflow, el.scrollHeight - el.clientHeight)
      })
      return {
        pageH: Math.round(pr.height),
        fillPct: Math.round((bottom / pr.height) * 100),
        overflowPx: overflow > 1 ? Math.round(overflow) : 0,
      }
    })
  })
  results[file.replace('.html', '')] = metrics
}
await browser.close()
console.log(JSON.stringify(results, null, 1))
