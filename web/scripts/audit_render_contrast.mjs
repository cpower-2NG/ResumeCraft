// Contrast audit of real rendered text in export HTML.
// Usage: node scripts/audit_render_contrast.mjs <dir> [threshold]
// Walks every element with its own text, composites the effective background by
// walking ancestors (skipping transparent ones), and reports WCAG contrast for
// text below the threshold — so palette mistakes show up as measured facts on
// the rendered page, not as guesses from token names.
import { chromium } from 'playwright'
import { readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const dir = resolve(process.argv[2] || '../output/tmp')
const threshold = Number(process.argv[3] || 4.5)
const files = readdirSync(dir).filter(f => f.endsWith('.html') && !f.includes('probe')).sort()

const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const page = await browser.newPage({ viewport: { width: 1200, height: 1400 } })

const probe = (threshold) => {
  const lin = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4 }
  const lum = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
  const parse = s => {
    const m = s.match(/rgba?\(([^)]+)\)/)
    if (!m) return null
    const p = m[1].split(',').map(Number)
    return { rgb: p.slice(0, 3), a: p.length > 3 ? p[3] : 1 }
  }
  const over = (fg, bg, a) => fg.map((c, i) => c * a + bg[i] * (1 - a))
  const bgOf = el => {
    let node = el, acc = null
    while (node && node !== document.documentElement.parentNode) {
      const c = parse(getComputedStyle(node).backgroundColor)
      if (c && c.a > 0) {
        acc = acc ? over(acc, c.rgb, acc.a ?? 1) : c.rgb
        if (c.a >= 0.999) return acc
        acc = acc
      }
      node = node.parentElement
    }
    return acc || [255, 255, 255]
  }
  const ratio = (a, b) => {
    const la = lum(a), lb = lum(b), hi = Math.max(la, lb), lo = Math.min(la, lb)
    return (hi + 0.05) / (lo + 0.05)
  }
  const path = el => {
    const parts = []
    let n = el
    while (n && n.tagName !== 'BODY') {
      parts.unshift(n.className && typeof n.className === 'string' && n.className.trim()
        ? n.className.trim().split(/\s+/)[0]
        : n.tagName.toLowerCase())
      n = n.parentElement
    }
    return parts.join('>')
  }
  const out = []
  document.querySelectorAll('.page *').forEach(el => {
    const own = Array.from(el.childNodes).filter(n => n.nodeType === 3 && n.textContent.trim()).map(n => n.textContent.trim()).join(' ')
    if (!own) return
    const cs = getComputedStyle(el)
    const fg = parse(cs.color)
    if (!fg) return
    const bg = bgOf(el)
    const colour = fg.a < 1 ? over(fg.rgb, bg, fg.a) : fg.rgb
    const r = ratio(colour, bg)
    if (r < threshold) out.push({ path: path(el), text: own.slice(0, 24), size: cs.fontSize, fg: `rgb(${colour.map(Math.round)})`, bg: `rgb(${bg.map(Math.round)})`, ratio: Math.round(r * 100) / 100 })
  })
  return out
}

const worst = []
let total = 0
for (const file of files) {
  await page.setContent(readFileSync(join(dir, file), 'utf-8'), { waitUntil: 'load' })
  const rows = await page.evaluate(probe, threshold)
  total += rows.length
  for (const r of rows) worst.push({ file: file.replace(/\.html$/, ''), ...r })
}
await browser.close()
worst.sort((a, b) => a.ratio - b.ratio)
const seen = new Set()
let printed = 0
for (const r of worst) {
  const key = `${r.file}|${r.path}|${r.fg}|${r.bg}`
  if (seen.has(key)) continue
  seen.add(key)
  if (printed++ >= 40) break
  console.log(`${String(r.ratio).padEnd(6)}${r.file.padEnd(20)}${r.size.padEnd(7)}${r.fg.padEnd(20)}on ${r.bg.padEnd(20)}${r.path}`)
}
console.log(`\n${files.length} 份导出、${total} 处文本低于 ${threshold}:1（去重后按最差排序，上示前 40）。`)
