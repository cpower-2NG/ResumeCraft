// Zoom into the 成果 (awards) block of the timeline template's card on the
// library page, to show what the squeezed table looks like to a user.
// Usage: node scripts/review_probe_library.mjs [baseUrl]
import { chromium } from 'playwright'
import { resolve } from 'node:path'

const base = process.argv[2] || 'http://127.0.0.1:5173'
const outDir = resolve(process.cwd(), '..', 'output', 'review')

const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 }, deviceScaleFactor: 3 })
await page.goto(base, { waitUntil: 'domcontentloaded' })
await page.waitForSelector('.module-card')
await page.locator('.module-card', { hasText: '简历工作台' }).click()
await page.getByRole('heading', { name: '正式简历' }).waitFor()
await page.getByRole('button', { name: '模板库' }).click()
await page.waitForSelector('.template-library-card')
await page.waitForTimeout(900)

const card = page.locator('.template-library-card', { hasText: '晨光时间轴模板' }).first()
const info = await card.evaluate(el => {
  const t = el.querySelector('.awards-table')
  const paper = el.querySelector('.resume-paper')
  if (!t) return { hasTable: false }
  const th = t.querySelector('th')
  return {
    paperWidth: Math.round(paper.getBoundingClientRect().width),
    tableWidth: Math.round(t.getBoundingClientRect().width),
    headerHeight: Math.round(th.getBoundingClientRect().height),
  }
})
console.log('timeline card awards table:', JSON.stringify(info))

const section = card.locator('.resume-section', { hasText: '成果' }).first()
await section.screenshot({ path: resolve(outDir, 'card-timeline-awards-zoom.png') })
console.log('saved card-timeline-awards-zoom')
await browser.close()
