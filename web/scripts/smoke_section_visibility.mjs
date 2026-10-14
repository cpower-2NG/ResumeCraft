// Smoke-test the per-section show/hide affordance in the running app: hide a section
// from its title bar, check it leaves the canvas and a restore chip appears, then
// restore it and check it comes back. Requires the app to be running.
// Usage: node scripts/smoke_section_visibility.mjs [baseUrl] [resumeId]
import { chromium } from 'playwright'

const base = process.argv[2] || 'http://127.0.0.1:5173'
const resumeName = process.argv[3] || '交互测试岗位'

const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const page = await browser.newPage({ viewport: { width: 1600, height: 1200 } })
await page.goto(base, { waitUntil: 'domcontentloaded' })
await page.waitForSelector('.module-card', { timeout: 20000 })
const module = page.locator('.module-card', { hasText: '简历工作台' }).first()
if (await module.count()) await module.click()
await page.waitForSelector('.resume-row', { timeout: 15000 })
const row = page.locator('.resume-row', { hasText: resumeName }).first()
if (!(await row.count())) throw new Error(`简历列表里找不到「${resumeName}」`)
await row.click()
await page.waitForSelector('.resume-paper', { timeout: 15000 })
// 保证在编辑态（否则没有隐藏按钮）。
const edit = page.getByRole('button', { name: /编辑|开始编辑/ }).first()
if (await edit.count()) await edit.click().catch(() => {})
await page.waitForTimeout(500)

const sections = () => page.evaluate(() => [...document.querySelectorAll('.resume-main .resume-section .template-section-title b')].map(b => b.textContent.replace('（续）', '')))
const hiddenChips = () => page.evaluate(() => [...document.querySelectorAll('.hidden-sections button')].map(b => b.textContent))

const before = await sections()
console.log('隐藏前主栏栏目:', JSON.stringify(before))

// 找到「项目与实践」那一栏的隐藏按钮并点击。
const target = page.locator('.resume-main .resume-section', { hasText: '项目与实践' }).first()
await target.locator('.hide-button').first().click()
await page.waitForTimeout(900)
const after = await sections()
const chips = await hiddenChips()
console.log('隐藏后主栏栏目:', JSON.stringify(after))
console.log('恢复入口:', JSON.stringify(chips))
const hidden = !after.includes('项目与实践')
console.log(hidden ? '✓ 被隐藏的栏目已从画布消失' : '✗ 栏目仍在画布上')
console.log(chips.some(c => c.includes('项目与实践')) ? '✓ 出现恢复入口' : '✗ 没有恢复入口')

// 点恢复。
await page.locator('.hidden-sections button', { hasText: '项目与实践' }).first().click()
await page.waitForTimeout(900)
const restored = await sections()
console.log('恢复后主栏栏目:', JSON.stringify(restored))
console.log(restored.includes('项目与实践') ? '✓ 栏目已恢复' : '✗ 恢复失败')
console.log((await hiddenChips()).length === 0 ? '✓ 恢复入口已收起' : '✗ 恢复入口仍在')

await browser.close()
