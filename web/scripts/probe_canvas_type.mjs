// Measure the computed typography of the SPA canvas markup so the preview's
// hierarchy can be compared with the export stylesheet instead of eyeballed.
// Usage: node scripts/probe_canvas_type.mjs [probe.html]
import { chromium } from 'playwright'
import { resolve } from 'node:path'

const file = process.argv[2] || resolve('scripts/fixtures/canvas-probe.html')
const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const page = await browser.newPage({ viewport: { width: 1200, height: 1200 }, deviceScaleFactor: 2 })
await page.goto(`file:///${file.replace(/\\/g, '/')}`, { waitUntil: 'load' })

const rows = await page.evaluate(() => {
  const probe = (label, sel) => {
    const el = document.querySelector(sel)
    if (!el) return { label, sel, missing: true }
    const c = getComputedStyle(el)
    return { label, sel, size: c.fontSize, weight: c.fontWeight, color: c.color }
  }
  return [
    probe('纸张基准', '.resume-paper'),
    probe('栏目标题(主栏)', '.resume-main .template-section-title b'),
    probe('栏目标题(侧栏)', '.sidebar-section .template-section-title b'),
    probe('条目标题(主栏)', '.resume-main .block-head>b'),
    probe('条目标题(侧栏)', '.sidebar-section .block-head>b'),
    probe('正文', '.resume-main .block-copy'),
    probe('字段行', '.resume-main .block-meta'),
    probe('字段标签', '.resume-main .block-meta span b'),
    probe('时间', '.resume-main .entry-period'),
  ]
})
const px = (v) => (v ? `${v} (${(parseFloat(v) * 72 / 96).toFixed(2)}pt)` : v)
for (const r of rows) {
  console.log(r.missing ? `${r.label}\t缺失` : `${r.label}\t${r.sel}\t${px(r.size)}\tweight=${r.weight}`)
}
await browser.close()
