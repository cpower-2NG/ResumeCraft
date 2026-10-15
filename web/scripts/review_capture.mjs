// Screenshot every main page plus the template library and a real export, so the
// current interface can be reviewed from images instead of only from CSS.
//
// Usage: node scripts/review_capture.mjs [baseUrl] [apiBase]
import { chromium } from 'playwright'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const base = process.argv[2] || 'http://127.0.0.1:5173'
const apiBase = process.argv[3] || 'http://127.0.0.1:8000'
const outDir = resolve(process.cwd(), '..', 'output', 'review')
mkdirSync(outDir, { recursive: true })

const shot = async (page, name, opts = {}) => {
  await page.screenshot({ path: resolve(outDir, `${name}.png`), ...opts })
  console.log('saved', name)
}

const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const context = await browser.newContext({ viewport: { width: 1560, height: 1000 }, deviceScaleFactor: 1 })
const page = await context.newPage()
const errors = []
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })

const home = async () => { await page.locator('.brand').click(); await page.waitForSelector('.module-card') }

try {
  await page.goto(base, { waitUntil: 'domcontentloaded' })
  await page.locator('.module-card').first().waitFor({ timeout: 20000 })
  await page.waitForTimeout(500)

  await shot(page, '01-home', { fullPage: true })

  await page.locator('.module-card', { hasText: '资料库' }).click()
  await page.getByRole('heading', { name: '资料库' }).waitFor()
  await page.waitForTimeout(400)
  await shot(page, '02-facts', { fullPage: true })

  await home()
  await page.locator('.module-card', { hasText: '岗位画像' }).click()
  await page.getByRole('heading', { name: '岗位画像' }).waitFor()
  await page.waitForTimeout(400)
  await shot(page, '03-profiles', { fullPage: true })

  await home()
  await page.locator('.module-card', { hasText: '简历工作台' }).click()
  await page.getByRole('heading', { name: '正式简历' }).waitFor()
  await page.waitForTimeout(400)
  await shot(page, '04-resumes', { fullPage: true })

  // 待处理事项面板
  if (await page.locator('.pending-fab').count()) {
    await page.locator('.pending-fab').click()
    await page.waitForTimeout(300)
    await shot(page, '05-pending-panel')
    await page.locator('.pending-panel .icon-btn').click()
  }

  await page.getByRole('button', { name: '模板库' }).click()
  await page.locator('.template-library-card').first().waitFor()
  await page.waitForTimeout(900)
  await shot(page, '06-templates', { fullPage: true })
  const cards = page.locator('.template-library-card')
  const total = await cards.count()
  console.log('template cards:', total)
  for (let i = 0; i < total; i++) {
    const card = cards.nth(i)
    const slug = await card.locator('.template-info b').innerText()
    await card.locator('.template-preview').screenshot({ path: resolve(outDir, `card-${String(i).padStart(2, '0')}.png`) })
  }
  console.log('saved per-card A4 previews')

  // 编辑器：打开一份已有正式简历（只读打开，不改数据）
  await home()
  await page.locator('.module-card', { hasText: '简历工作台' }).click()
  await page.getByRole('heading', { name: '正式简历' }).waitFor()
  await page.waitForSelector('.resume-row', { timeout: 15000 }).catch(() => {})
  await page.waitForTimeout(600)
  const row = page.locator('.resume-row:not(.continue-card)').first()
  if (await row.count()) {
    await row.click()
    await page.waitForSelector('.resume-paper', { timeout: 20000 })
    await page.waitForTimeout(1000)
    await shot(page, '07-editor', { fullPage: true })

    // 体检条默认折叠成一行；展开后应重新列出逐条问题（仍可点击定位）。
    const lintToggle = page.locator('.lint-toggle')
    if (await lintToggle.count()) {
      await lintToggle.click()
      await page.waitForTimeout(300)
      await shot(page, '07b-editor-lint-expanded')
      await lintToggle.click()
      await page.waitForTimeout(200)
    }

    // 编辑器里的模板选择弹层（含机器可读性标签），只看不改
    await page.locator('.actionbar button', { hasText: '模板' }).first().click()
    await page.waitForSelector('.template-card')
    await page.waitForTimeout(400)
    await shot(page, '08-template-modal')
    await page.keyboard.press('Escape')
    await page.waitForTimeout(300)
  } else {
    console.log('no formal resume row to open')
  }

  // 真实导出 HTML 的纸面效果
  const resumes = await (await page.request.get(`${apiBase}/api/resumes`)).json()
  const target = resumes.find(r => r.status === 'active' && r.current_version)
  if (target) {
    const res = await page.request.post(`${apiBase}/api/resumes/${target.id}/versions/${target.current_version}/export`)
    const html = await res.text()
    const file = resolve(outDir, `export-${target.id}-v${target.current_version}.html`)
    writeFileSync(file, html, 'utf8')
    const epage = await context.newPage()
    await epage.goto('file:///' + file.replace(/\\/g, '/'), { waitUntil: 'load' })
    await epage.waitForTimeout(800)
    await epage.screenshot({ path: resolve(outDir, '09-export.png'), fullPage: true })
    console.log('saved export render for resume', target.id)
    await epage.close()
  }

  console.log('console errors:', errors.length ? errors.join(' | ') : 'none')
} finally {
  await browser.close()
}
