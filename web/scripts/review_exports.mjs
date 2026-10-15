// Render every generated export sample (output/tmp/real-*.html) at full size so
// each template's true paper appearance can be reviewed from an image.
//
// Usage: node scripts/review_exports.mjs
import { chromium } from 'playwright'
import { readdirSync, mkdirSync } from 'node:fs'
import { resolve, basename } from 'node:path'

const tmpDir = resolve(process.cwd(), '..', 'output', 'tmp')
const outDir = resolve(process.cwd(), '..', 'output', 'review')
mkdirSync(outDir, { recursive: true })
const files = readdirSync(tmpDir).filter(f => /^real-.*\.html$/.test(f)).sort()

const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const ctx = await browser.newContext({ viewport: { width: 900, height: 1300 }, deviceScaleFactor: 2 })
const page = await ctx.newPage()
for (const f of files) {
  const url = 'file:///' + resolve(tmpDir, f).replace(/\\/g, '/')
  await page.goto(url, { waitUntil: 'load' })
  await page.waitForTimeout(350)
  const name = basename(f, '.html')
  await page.screenshot({ path: resolve(outDir, `tpl-${name}.png`), fullPage: true })
  console.log('saved tpl-' + name)
}
await browser.close()
