// Contrast audit of the LIVE SPA canvas, for every resume × every template.
//
// Why this exists next to audit_render_contrast.mjs: that one audits the exported HTML,
// which is a different renderer with its own stylesheet. The canvas additionally paints
// edit-mode affordances (来源徽标 / 添加来源 / 续段标记 / 空栏目占位 / 行内输入) and gets
// its palette injected as CSS variables at runtime — a palette or dark-surface mistake
// can be invisible in the export and obvious to the user here. Two real defects were
// found this way: sidebar sections missing their `sidebar-section` marker (so the whole
// dark-surface vocabulary never applied), and `.resume-paper .block-copy` out-specifying
// the sidebar override, leaving body copy in paper colour on the dark sidebar.
//
// Requires the app to be running (scripts/Start-ResumeCraft.ps1).
// Usage: node scripts/audit_canvas_contrast.mjs [baseUrl] [threshold]
import { chromium } from 'playwright'

const base = process.argv[2] || 'http://127.0.0.1:5173'
const threshold = Number(process.argv[3] || 4.5)
const apiBase = process.env.API_BASE || 'http://127.0.0.1:8000'

const probe = (threshold) => {
  const lin = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4 }
  const lum = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
  const parse = (s) => { const m = s.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(',').map(Number); return { rgb: p.slice(0, 3), a: p.length > 3 ? p[3] : 1 } }
  const over = (fg, bg, a) => fg.map((c, i) => c * a + bg[i] * (1 - a))
  // 沿祖先链合成有效背景：必须带着"已合成层"的 alpha 往下算，否则内层一个 8% 透明度
  // 的白底会被当成不透明白色，把深色侧栏整个盖掉（首版就栽在这里，报出一堆假阳性）。
  const bgOf = (el) => {
    let node = el, acc = null
    while (node) {
      const c = parse(getComputedStyle(node).backgroundColor)
      if (c && c.a > 0) {
        if (!acc) acc = { rgb: c.rgb, a: c.a }
        else {
          acc = { rgb: over(acc.rgb, c.rgb, acc.a), a: acc.a + c.a * (1 - acc.a) }
        }
        if (acc.a >= 0.999) return acc.rgb
      }
      node = node.parentElement
    }
    return acc ? over(acc.rgb, [255, 255, 255], acc.a) : [255, 255, 255]
  }
  const ratio = (a, b) => { const la = lum(a), lb = lum(b); return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05) }
  const path = (el) => { const parts = []; let n = el; while (n && n.tagName !== 'BODY') { parts.unshift(n.className && typeof n.className === 'string' && n.className.trim() ? n.className.trim().split(/\s+/).join('.') : n.tagName.toLowerCase()); n = n.parentElement } return parts.join('>') }
  const out = []
  document.querySelectorAll('.resume-paper *').forEach((el) => {
    const own = Array.from(el.childNodes).filter(n => n.nodeType === 3 && n.textContent.trim()).map(n => n.textContent.trim()).join(' ')
    if (!own) return
    const rect = el.getBoundingClientRect()
    if (!rect.width || !rect.height) return
    const cs = getComputedStyle(el)
    const fg = parse(cs.color)
    if (!fg) return
    const bg = bgOf(el)
    const colour = fg.a < 1 ? over(fg.rgb, bg, fg.a) : fg.rgb
    const r = ratio(colour, bg)
    if (r < threshold) out.push({ path: path(el), text: own.slice(0, 18), size: cs.fontSize, fg: `rgb(${colour.map(Math.round)})`, bg: `rgb(${bg.map(Math.round)})`, ratio: Math.round(r * 100) / 100 })
  })
  return { rows: out, template: document.querySelector('.resume-stage')?.dataset.template || '?' }
}

const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const page = await browser.newPage({ viewport: { width: 1600, height: 1200 } })

// 打开某份简历的工作台：首页有两个入口（模块卡「简历工作台」、或「最近简历」列表）。
// 每一步都显式判断，走不到位就报错——首版把点击失败 swallow 掉了，审计实际上是在
// "碰巧打开"的页面上跑，界面一改版就会静默审错对象。
const openResume = async (name) => {
  await page.goto(base, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.module-card', { timeout: 20000 })
  const module = page.locator('.module-card', { hasText: '简历工作台' }).first()
  if (await module.count()) await module.click()
  await page.waitForSelector('.resume-row', { timeout: 15000 })
  const row = page.locator('.resume-row', { hasText: name }).first()
  if (!(await row.count())) throw new Error(`简历列表里找不到「${name}」`)
  await row.click()
  await page.waitForSelector('.resume-paper', { timeout: 15000 })
  await page.waitForTimeout(400)
}

const resumes = await (await page.request.get(`${apiBase}/api/resumes`)).json()
const templates = await (await page.request.get(`${apiBase}/api/templates`)).json()
const resume = resumes.find(r => r.status === 'active') || resumes[0]
console.log(`resume ${resume.id} 「${resume.display_name}」 × ${templates.length} templates, threshold ${threshold}:1\n`)

const seen = new Map()
for (const template of templates) {
  await openResume(resume.display_name)
  const open = page.getByRole('button', { name: '模板' }).first()
  if (!(await open.count())) throw new Error('工作台上找不到「模板」按钮，无法切换模板')
  await open.click()
  await page.waitForSelector('.template-card', { timeout: 10000 })
  const card = page.locator('.template-card', { hasText: template.name }).first()
  if (!(await card.count())) throw new Error(`模板卡片里找不到「${template.name}」`)
  await card.click()
  await page.waitForTimeout(900)
  // 鼠标停在画布上会触发编辑态悬停底色，把"正常状态"的审计污染成悬停态；探针前先移开。
  await page.mouse.move(0, 0)
  const result = await page.evaluate(probe, threshold)
  if (result.template !== template.slug) throw new Error(`切到「${template.name}」后画布仍是 ${result.template}`)
  const tag = `${template.slug}(${template.layout})`
  for (const r of result.rows) {
    const key = `${tag}|${r.path}|${r.fg}|${r.bg}`
    if (!seen.has(key)) seen.set(key, { ...r, tag })
  }
  console.log(`${tag.padEnd(20)}低于阈值的文本 ${result.rows.length} 处`)
}
await browser.close()

console.log('')
for (const r of [...seen.values()].sort((a, b) => a.ratio - b.ratio)) {
  console.log(`${String(r.ratio).padEnd(6)}${r.tag.padEnd(20)}${r.size.padEnd(10)}${r.fg.padEnd(20)}on ${r.bg.padEnd(20)}${r.path}  「${r.text}」`)
}
console.log(`\n画布上低于 ${threshold}:1 的文本：${seen.size} 处（去重后）`)
