// Explain an estimator-vs-render mismatch: for every main-column paragraph, print
// its character count, line-box count and content width, so chars-per-line can be
// compared between the calibration probe and the sample that overflowed.
// Usage: node scripts/check_chars_per_line.mjs <export.html> [export.html ...]
import { chromium } from 'playwright'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const page = await browser.newPage({ viewport: { width: 1200, height: 1400 } })
for (const file of process.argv.slice(2)) {
  await page.setContent(readFileSync(resolve(file), 'utf-8'), { waitUntil: 'load' })
  const rows = await page.evaluate(() => {
    const lineCount = el => { const r = document.createRange(); r.selectNodeContents(el); return r.getClientRects().length }
    return [...document.querySelectorAll('.main .block p, .sidebar .block p')].map(el => {
      const box = el.getBoundingClientRect()
      return {
        inPair: Boolean(el.closest('.pair')),
        inSidebar: Boolean(el.closest('.sidebar')),
        chars: el.textContent.length,
        lines: lineCount(el),
        width: Math.round(box.width),
        size: getComputedStyle(el).fontSize,
        cpl: lineCount(el) ? Math.round(el.textContent.length / lineCount(el) * 10) / 10 : 0,
      }
    }).filter(r => r.chars > 100)
  })
  console.log(`--- ${file}`)
  for (const r of rows) console.log(JSON.stringify(r))
}
await browser.close()
