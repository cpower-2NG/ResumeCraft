// Measure the awards table in an exported HTML file for comparison with the canvas.
// Usage: node scripts/review_probe_export.mjs <file.html>
import { chromium } from 'playwright'
import { resolve } from 'node:path'

const file = resolve(process.cwd(), process.argv[2])
const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const page = await browser.newPage({ viewport: { width: 900, height: 1300 } })
await page.goto('file:///' + file.replace(/\\/g, '/'), { waitUntil: 'load' })
const info = await page.evaluate(() => {
  const pageEl = document.querySelector('.page')
  const table = document.querySelector('.awards-table')
  if (!table) return { hasTable: false, pageWidth: pageEl ? pageEl.getBoundingClientRect().width : null }
  const r = table.getBoundingClientRect()
  const parent = table.parentElement
  const chain = []
  let node = table
  for (let i = 0; i < 6 && node && node !== document.body; i++) {
    const cs = getComputedStyle(node)
    chain.push({ cls: node.className || node.tagName.toLowerCase(), display: cs.display, cols: cs.gridTemplateColumns, w: Math.round(node.getBoundingClientRect().width) })
    node = node.parentElement
  }
  return {
    hasTable: true,
    pageWidth: Math.round(pageEl.getBoundingClientRect().width),
    tableX: Math.round(r.x),
    tableWidth: Math.round(r.width),
    tableHeight: Math.round(r.height),
    parentTag: parent.tagName.toLowerCase(),
    parentClass: parent.className,
    parentDisplay: getComputedStyle(parent).display,
    chain,
    th: Array.from(table.querySelectorAll('th')).map(t => ({ text: t.textContent, w: Math.round(t.getBoundingClientRect().width), h: Math.round(t.getBoundingClientRect().height) })),
  }
})
console.log(JSON.stringify(info, null, 2))
await browser.close()
