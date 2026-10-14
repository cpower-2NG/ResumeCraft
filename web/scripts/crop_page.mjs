// Crop one region of the first page of an export HTML for close inspection.
// Usage: node scripts/crop_page.mjs <export.html> <out.png> <x> <y> <w> <h> [scale]
import { chromium } from 'playwright'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const [file, out, x, y, w, h, scale = '3'] = process.argv.slice(2)
const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const page = await browser.newPage({ viewport: { width: 1200, height: 1400 }, deviceScaleFactor: Number(scale) })
await page.setContent(readFileSync(resolve(file), 'utf-8'), { waitUntil: 'load' })
const box = await page.locator('.page').first().boundingBox()
await page.screenshot({
  path: resolve(out),
  clip: { x: box.x + Number(x), y: box.y + Number(y), width: Number(w), height: Number(h) },
})
await browser.close()
console.log('cropped', out)
