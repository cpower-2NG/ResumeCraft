// 将真实简历导出 HTML 截图为 PNG。
import { chromium } from 'playwright'
import { readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const dir = join(dirname(fileURLToPath(import.meta.url)), 'real-resume-previews')
const files = readdirSync(dir).filter(f => f.endsWith('.html'))
const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const page = await browser.newPage({ viewport: { width: 900, height: 1300 }, deviceScaleFactor: 1.5 })

for (const file of files) {
  await page.goto('file:///' + join(dir, file).replace(/\\/g, '/'))
  await page.waitForTimeout(120)
  const out = join(dir, file.replace('.html', '.png'))
  await page.screenshot({ path: out, fullPage: true })
  console.log('shot', out)
}
await browser.close()
