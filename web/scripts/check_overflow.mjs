// 溢出安全检查：渲染每个导出 HTML，验证每页主栏/侧栏内容没有超出 A4 纸面
//（.page overflow:hidden 会静默裁字，这里把 scrollHeight 与 clientHeight 对比）。
import { chromium } from 'playwright'
import { readdirSync } from 'node:fs'
import { join } from 'node:path'

const dir = process.argv[2] || 'C:/Users/29673/Documents/Codex/projects/ResumeCraft/output/tmp/v2-previews'
const files = readdirSync(dir).filter(f => f.endsWith('.html'))
const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const page = await browser.newPage({ viewport: { width: 900, height: 1300 } })
let failures = 0
for (const file of files) {
  await page.goto('file:///' + join(dir, file).replace(/\\/g, '/'))
  await page.waitForTimeout(120)
  const report = await page.evaluate(() => {
    const out = []
    for (const pageEl of document.querySelectorAll('.page')) {
      const mains = [...pageEl.querySelectorAll('.main, .sidebar')]
      for (const main of mains) {
        const over = main.scrollHeight - main.clientHeight
        out.push({ page: pageEl.getAttribute('data-page') || [...document.querySelectorAll('.page')].indexOf(pageEl) + 1, cls: main.className, over: Math.round(over) })
      }
    }
    return out
  })
  const bad = report.filter(r => r.over > 1)
  if (bad.length) failures += 1
  console.log(file.padEnd(28), bad.length ? `OVERFLOW ${JSON.stringify(bad)}` : `ok (${report.map(r => r.over).join(',')})`)
}
await browser.close()
process.exitCode = failures ? 1 : 0
