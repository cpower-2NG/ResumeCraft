// Screenshot one PNG per A4 page of every export HTML in a directory.
// Usage: node scripts/shoot_pages.mjs <dir> [outDir] [nameFilter]
// A4 is 210x297mm; the .page element is sized in mm, so screenshot per element
// keeps each page at its true aspect ratio for visual review.
import { chromium } from 'playwright'
import { readdirSync, mkdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const dir = resolve(process.argv[2] || '../output/tmp')
const outDir = resolve(process.argv[3] || join(dir, 'shots'))
const filter = process.argv[4] || ''
mkdirSync(outDir, { recursive: true })

const files = readdirSync(dir).filter(f => f.endsWith('.html') && f.includes(filter)).sort()
const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const page = await browser.newPage({ viewport: { width: 1000, height: 1200 }, deviceScaleFactor: 1.1 })

for (const file of files) {
  await page.setContent(readFileSync(join(dir, file), 'utf-8'), { waitUntil: 'load' })
  const count = await page.locator('.page').count()
  for (let i = 0; i < count; i++) {
    const name = `${file.replace(/\.html$/, '')}-p${i + 1}.png`
    await page.locator('.page').nth(i).screenshot({ path: join(outDir, name) })
  }
  console.log('shot', file, count)
}
await browser.close()
