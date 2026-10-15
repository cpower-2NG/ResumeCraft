// Open a resume in the running app and report what the canvas actually paints inside
// dark regions (sidebar / banner / table header / empty placeholder / edit affordances).
//
// Written to answer "深色底上的字看不见" with evidence from the real application instead
// of from the exported HTML, because the canvas has its own stylesheet and its own
// edit-mode elements. Requires the app to be running.
//
// Usage: node scripts/inspect_canvas.mjs [baseUrl] [resumeId] [out.png]
import { chromium } from 'playwright'

const base = process.argv[2] || 'http://127.0.0.1:5173'
const onlyResume = process.argv[3] ? Number(process.argv[3]) : null
// 前端把 API 指向独立端口（web/src/api.ts），dev server 不做代理。
const apiBase = process.env.API_BASE || 'http://127.0.0.1:8000'

const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const page = await browser.newPage({ viewport: { width: 1600, height: 1200 } })
page.on('console', m => { if (m.type() === 'error') console.log('console error:', m.text()) })

const resumes = await (await page.request.get(`${apiBase}/api/resumes`)).json()
await page.goto(base, { waitUntil: 'domcontentloaded' })
await page.waitForSelector('.module-card', { timeout: 20000 })

for (const resume of resumes) {
  if (onlyResume && resume.id !== onlyResume) continue
  // 首页 -> 简历工作台模块 -> 简历列表 -> 打开该简历。
  // 选择器按当前界面文案（模块卡「简历工作台」）；以前写成旧项目名 "ResumeCraft"，
  // 点不到又被 .catch 吞掉，于是脚本静默地在首页上跑完全程。
  await page.locator('.module-card', { hasText: '简历工作台' }).first().click()
  await page.waitForSelector('.resume-row', { timeout: 15000 }).catch(() => {})
  const row = page.locator('.resume-row', { hasText: resume.display_name }).first()
  if (!(await row.count())) { console.log(`resume ${resume.id}: 列表里没找到行`); continue }
  await row.click()
  await page.waitForSelector('.resume-paper', { timeout: 15000 }).catch(() => {})
  await page.waitForTimeout(600)

  // 可选：先把这份简历切到指定模板，便于查看某种版式的画布（例如侧栏版式的深色侧栏）。
  const switchTo = process.argv[5]
  if (switchTo) {
    await page.getByRole('button', { name: '模板' }).first().click().catch(() => {})
    await page.waitForSelector('.template-card', { timeout: 10000 }).catch(() => {})
    const card = page.locator('.template-card', { hasText: switchTo }).first()
    if (await card.count()) { await card.click(); await page.waitForTimeout(1200) }
    else console.log(`  没找到模板卡片「${switchTo}」`)
  }

  const info = await page.evaluate(() => {
    const stage = document.querySelector('.resume-stage')
    const sidebar = document.querySelector('.resume-sidebar')
    const texts = (root) => root ? [...root.querySelectorAll('*')].filter(el => [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())).map(el => {
      const cs = getComputedStyle(el)
      return { cls: (el.className || '').toString().split(' ')[0] || el.tagName, text: el.textContent.trim().slice(0, 24), color: cs.color, bg: cs.backgroundColor, size: cs.fontSize }
    }) : null
    return {
      template: stage?.dataset.template,
      stageClass: stage?.className,
      paperClass: document.querySelector('.resume-paper')?.className,
      sidebarExists: Boolean(sidebar),
      sidebarTexts: texts(sidebar),
      // 侧栏页头（姓名 + 联系方式 + 简介）在画布里是否存在
      hasSidebarHead: Boolean(document.querySelector('.resume-sidebar h1, .side-meta, .side-copy')),
      mainSections: [...document.querySelectorAll('.resume-main .resume-section')].map(s => s.querySelector('.template-section-title b')?.textContent),
    }
  })
  console.log(`\n=== resume ${resume.id} 「${resume.display_name}」 template=${info.template} stage=${info.stageClass}`)
  console.log(`    paper=${info.paperClass}`)
  console.log(`    侧栏存在=${info.sidebarExists}  侧栏页头(姓名/联系方式)=${info.hasSidebarHead}`)
  console.log(`    主栏栏目=${JSON.stringify(info.mainSections)}`)
  if (info.sidebarTexts) for (const t of info.sidebarTexts) console.log(`    侧栏 «${t.text}»  ${t.cls}  color=${t.color}  bg=${t.bg}  ${t.size}`)
}

const stage = await page.locator('.resume-stage').first().boundingBox().catch(() => null)
if (stage) await page.screenshot({ path: process.argv[4] || '../output/tmp/shots/canvas-live.png', clip: stage })
await browser.close()
