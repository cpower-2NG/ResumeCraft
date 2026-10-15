// Measure the canvas geometry of a resume opened in the running app, to check
// whether the awards table fills the page width like the export does.
//
// Usage: node scripts/review_probe.mjs [baseUrl] [resumeId]
import { chromium } from 'playwright'

const base = process.argv[2] || 'http://127.0.0.1:5173'
const wantedId = process.argv[3] ? Number(process.argv[3]) : null
const apiBase = process.env.API_BASE || 'http://127.0.0.1:8000'

const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } })
const resumes = await (await page.request.get(`${apiBase}/api/resumes`)).json()
const target = wantedId ? resumes.find(r => r.id === wantedId) : resumes[0]

await page.goto(base, { waitUntil: 'domcontentloaded' })
await page.waitForSelector('.module-card')
await page.locator('.module-card', { hasText: '简历工作台' }).click()
await page.getByRole('heading', { name: '正式简历' }).waitFor()
await page.waitForSelector('.resume-row')
await page.locator('.resume-row', { hasText: target.display_name }).first().click()
await page.waitForSelector('.resume-paper')
await page.waitForTimeout(900)

const info = await page.evaluate(() => {
  const paper = document.querySelector('.resume-paper')
  const table = document.querySelector('.awards-table')
  const head = document.querySelector('.template-section-title b')
  const rect = el => { const r = el.getBoundingClientRect(); return { x: Math.round(r.x), w: Math.round(r.width), h: Math.round(r.height) } }
  const chain = []
  let node = table
  while (node && node !== document.body) {
    const cs = getComputedStyle(node)
    chain.push({ tag: node.tagName.toLowerCase(), cls: node.className, display: cs.display, cols: cs.gridTemplateColumns, width: Math.round(node.getBoundingClientRect().width) })
    node = node.parentElement
  }
  const th = table ? Array.from(table.querySelectorAll('th')).map(t => ({ text: t.textContent, w: Math.round(t.getBoundingClientRect().width), h: Math.round(t.getBoundingClientRect().height) })) : []
  return {
    template: paper.dataset.template,
    paper: rect(paper),
    table: table ? rect(table) : null,
    tableWidthStyle: table ? getComputedStyle(table).width : null,
    th,
    chain,
  }
})
console.log(JSON.stringify(info, null, 2))

// 放大截取"成果"这一栏，便于直观看到表格被压扁的样子。
const awardsSection = page.locator('.resume-section', { hasText: '成果' }).first()
if (await awardsSection.count()) {
  await awardsSection.screenshot({ path: '../output/review/editor-awards-canvas-zoom.png' })
  console.log('saved editor-awards-canvas-zoom.png')
}
await browser.close()
