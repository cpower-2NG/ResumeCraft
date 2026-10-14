// 测量意向横带 / 成果表格 / 技能分组的真实高度，并验证紧凑档收缩比。
import { chromium } from 'playwright'
import { readFileSync } from 'node:fs'

const dir = 'C:/Users/29673/Documents/Codex/projects/ResumeCraft/output/tmp'
const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const page = await browser.newPage({ viewport: { width: 900, height: 1300 } })

// 1) composed-ink：横带 + 成果表格 + 技能分组
await page.goto('file:///' + dir + '/v2-previews/composed-ink.html')
await page.waitForTimeout(120)
const parts = await page.evaluate(() => {
  const px = v => parseFloat(v) || 0
  const band = document.querySelector('.intent-band')
  const bandH = band ? band.getBoundingClientRect().height + px(getComputedStyle(band).marginBottom) : 0
  const th = document.querySelector('.awards-table th')
  const thH = th ? th.getBoundingClientRect().height : 0
  const td = document.querySelector('.awards-table td')
  const tdH = td ? td.getBoundingClientRect().height + 0 : 0
  // 行高 = td 高（含 border）
  const skillPs = [...document.querySelectorAll('.block-copy p strong')].map(s => s.closest('p'))
  let groupGap = 0
  if (skillPs.length >= 2) {
    const a = skillPs[0].getBoundingClientRect(), b = skillPs[1].getBoundingClientRect()
    groupGap = b.top - a.bottom + px(getComputedStyle(skillPs[0]).marginBottom) - (px(getComputedStyle(skillPs[0]).marginBottom) ? 0 : 0)
    groupGap = b.top - a.bottom
  }
  const li = document.querySelector('.block li')
  const liLine = li ? px(getComputedStyle(li).lineHeight) : 0
  return { bandH, thH, tdH, groupGap, liLine, bandCount: skillPs.length }
})
console.log('parts:', JSON.stringify(parts))

// 2) 紧凑档收缩比：同一份内容渲染 normal 与 compact 两个版本，量主栏内容高度
const probe = await page.evaluate(() => null).catch(() => null)
const content = readFileSync(dir + '/v2-previews/composed-ink.html', 'utf-8')
const compacted = content.replace('class="page page-plain"', 'class="page compact page-plain"')
await page.setContent(content, { waitUntil: 'load' })
const normalH = await page.evaluate(() => {
  const main = document.querySelector('.main')
  let h = 0
  for (const child of main.children) h += child.getBoundingClientRect().height
  return h
})
await page.setContent(compacted, { waitUntil: 'load' })
const compactH = await page.evaluate(() => {
  const main = document.querySelector('.main')
  let h = 0
  for (const child of main.children) h += child.getBoundingClientRect().height
  return h
})
console.log('normal:', normalH, 'compact:', compactH, 'ratio:', (compactH / normalH).toFixed(4), 'need <=', (1 / 1.08).toFixed(4))
await browser.close()
