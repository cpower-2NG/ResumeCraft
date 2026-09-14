// Dump the real DOM structure of every page of one export HTML with element
// heights and clipped overflow, so estimate-vs-render drift in the pagination
// model can be located exactly. Complements measure_pages.mjs, which only
// reports per-page fill/overflow totals.
// Usage: node scripts/dump_page.mjs <export.html>
import { chromium } from 'playwright'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const file = resolve(process.argv[2])
const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const page = await browser.newPage({ viewport: { width: 1400, height: 1200 } })
await page.setContent(readFileSync(file, 'utf-8'), { waitUntil: 'load' })

const dump = await page.evaluate(() => {
  const out = []
  document.querySelectorAll('.page').forEach((p, i) => {
    const pr = p.getBoundingClientRect()
    const rows = []
    const head = p.querySelector('.line-head,.grid-head,.page-banner,.sidebar')
    if (head) rows.push(`${head.className.split(' ')[0]} h=${Math.round(head.getBoundingClientRect().height)}`)
    const walk = (parent, depth) => {
      for (const el of parent.children) {
        const cls = el.className && typeof el.className === 'string' ? el.className.split(' ')[0] : el.tagName
        if (['section', 'pair', 'block', 'block-meta', 'entry-row'].includes(cls) || el.tagName === 'H2' || el.tagName === 'H3' || el.tagName === 'P') {
          const r = el.getBoundingClientRect()
          const label = el.tagName === 'H2' || el.tagName === 'H3' ? `${el.tagName}:${el.textContent.slice(0, 14)}` : cls
          const txt = el.tagName === 'P' ? ` chars=${el.textContent.length}` : ''
          rows.push(`${'  '.repeat(depth)}${label} top=${Math.round(r.top - pr.top)} h=${Math.round(r.height)}${txt}`)
        }
        if (!['P', 'H2', 'H3', 'BLOCK-META'].includes(el.tagName)) walk(el, depth + 1)
      }
    }
    if (p.querySelector('.main')) walk(p.querySelector('.main'), 0)
    const main = p.querySelector('.main')
    out.push({
      page: i + 1,
      pageH: Math.round(pr.height),
      mainClient: main.clientHeight,
      mainScroll: main.scrollHeight,
      overflow: main.scrollHeight - main.clientHeight,
      rows,
    })
  })
  return out
})
await browser.close()
for (const p of dump) {
  console.log(`\n=== page ${p.page} pageH=${p.pageH} mainClient=${p.mainClient} mainScroll=${p.mainScroll} overflow=${p.overflow}`)
  console.log(p.rows.join('\n'))
}
