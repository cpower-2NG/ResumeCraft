// Measure the real geometry of the calibration probes and print the constants
// LAYOUT_METRICS should carry. Usage: node scripts/measure_calib.mjs <dir>
//
// Every number is read from the browser's own layout of the real export CSS:
// - line heights come from getComputedStyle, so they cannot drift from the CSS
// - chars-per-line comes from counting actual line boxes with a Range, so it
//   accounts for the real font and the real column width (CJK + Latin mix)
// - header/header_first come from the distance between a section's top and its
//   first block, which is exactly what the packer charges per page.
import { chromium } from 'playwright'
import { readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const dir = resolve(process.argv[2] || '../output/tmp/calib')
const files = readdirSync(dir).filter(f => f.endsWith('.html')).sort()
const browser = await chromium.launch({ headless: true, channel: 'chromium' })
const page = await browser.newPage({ viewport: { width: 1200, height: 1400 } })

const rows = []
for (const file of files) {
  await page.setContent(readFileSync(join(dir, file), 'utf-8'), { waitUntil: 'load' })
  const row = await page.evaluate(() => {
    const cs = el => getComputedStyle(el)
    const px = v => parseFloat(v) || 0
    const lineCount = el => { const r = document.createRange(); r.selectNodeContents(el); return r.getClientRects().length }
    // Number of wrapped meta lines: distinct row tops among the flex items.
    const metaRows = el => new Set([...el.querySelectorAll('.meta')].map(c => Math.round(c.getBoundingClientRect().top))).size
    // Line boxes a text occupies at a given width, using the probe's own font.
    const boxesAt = (text, width, style) => {
      const box = document.createElement('div')
      box.style.cssText = `position:absolute;left:-9999px;top:0;width:${width}px;white-space:normal;overflow-wrap:anywhere;` +
        `font-family:${style.fontFamily};font-size:${style.fontSize};font-weight:${style.fontWeight};letter-spacing:${style.letterSpacing}`
      box.textContent = text
      document.body.appendChild(box)
      const n = lineCount(box)
      box.remove()
      return n
    }
    const main = document.querySelector('.main')
    const pageEl = main.closest('.page')
    const headEl = pageEl.querySelector('.line-head,.grid-head,.page-banner')
    const mainStyle = cs(main)
    const contentWidth = main.clientWidth - px(mainStyle.paddingLeft) - px(mainStyle.paddingRight)
    // The page is a 2-row grid (head, main) whose auto rows stretch to fill the
    // sheet, so a *short* page reports an inflated main height. The usable height
    // is what matters once content fills the page, so derive it from the head's
    // natural content height, not from its stretched row.
    const headNatural = headEl ? (() => {
      const st = cs(headEl)
      let h = px(st.paddingTop) + px(st.paddingBottom) + px(st.borderTopWidth) + px(st.borderBottomWidth)
      for (const child of headEl.children) h += child.getBoundingClientRect().height + px(cs(child).marginTop) + px(cs(child).marginBottom)
      return h
    })() : 0
    const blankHead = Boolean(pageEl.querySelector('.line-head-slim,.grid-head-slim,.banner-slim'))
    const pageBudget = Math.round(pageEl.getBoundingClientRect().height - headNatural
      - px(mainStyle.paddingTop) - px(mainStyle.paddingBottom))

    // Half-column width: inject a real .pair so the layout's own gap applies.
    const pairProbe = document.createElement('div')
    pairProbe.className = 'pair'
    pairProbe.innerHTML = '<section class="section"><h2>p</h2></section><section class="section"><h2>p</h2></section>'
    main.appendChild(pairProbe)
    const pairWidth = pairProbe.firstElementChild.getBoundingClientRect().width
    pairProbe.remove()

    // The long prose block is the estimation target: full width, no pair parent.
    const p = [...document.querySelectorAll('.main .block p')]
      .filter(el => el.textContent.length > 500 && !el.closest('.pair'))[0]
    const text = p.textContent
    const pStyle = cs(p)
    const block = p.closest('.block')
    const blockStyle = cs(block)
    const meta = block.querySelector('.block-meta')
    const metaSpan = meta.querySelector('.meta')
    const metaChars = [...meta.querySelectorAll('.meta')].reduce((sum, el) => {
      const b = el.querySelector('b')
      const label = b ? b.textContent : ''
      return sum + label.length + el.textContent.replace(label, '').trim().length
    }, 0)
    const metaLines = metaRows(meta)
    const metaStyle = cs(metaSpan || p)
    const line = px(pStyle.lineHeight)
    const metaLine = px(metaStyle.lineHeight)
    const blockLines = lineCount(p)
    const blockMetaLines = metaLines
    const base = Math.round(block.getBoundingClientRect().height + px(blockStyle.marginBottom)
      - blockLines * line - blockMetaLines * metaLine)

    // header = section top -> first block top; plus the section's own margin-top
    // for the "not first on the page" case.
    const section = block.closest('.section')
    const headerFirst = Math.round(block.getBoundingClientRect().top - section.getBoundingClientRect().top)
    const header = headerFirst + px(cs(section).marginTop)

    // meta_chars (declared above) is the probe's label+value character count;
    // divided by the rows it wrapped onto it is a slight *under*-estimate of the
    // true row capacity — the safe direction, since over-counting rows only
    // costs page space while under-counting clips text.
    const pairMetaLines = (() => {
      const holder = document.createElement('div')
      holder.className = 'pair'
      const col = document.createElement('section')
      col.className = 'section'
      col.appendChild(meta.cloneNode(true))
      holder.appendChild(col)
      main.appendChild(holder)
      const n = metaRows(holder.querySelector('.block-meta'))
      holder.remove()
      return n
    })()
    // Entry-title row cost, charged only for blocks that actually render a
    // title (a block whose title equals its section heading renders none).
    const titleRow = meta.closest('.block').querySelector('.entry-row')
    const titleEl = meta.closest('.block').querySelector('.t-body h3, h3')
    const titlePx = titleRow
      ? Math.round(titleRow.getBoundingClientRect().height + px(cs(titleRow).marginBottom))
      : (titleEl ? Math.round(titleEl.getBoundingClientRect().height + px(cs(titleEl).marginBottom)) : 0)

    const sidebar = document.querySelector('.sidebar')
    let side = null
    if (sidebar) {
      const sStyle = cs(sidebar)
      const sidePad = { top: px(sStyle.paddingTop), bottom: px(sStyle.paddingBottom) }
      const sParas = [...sidebar.querySelectorAll('.block p')].filter(el => el.textContent.length > 200)
      const sp = sParas[0]
      const sBlock = sp.closest('.block')
      const sLines = lineCount(sp)
      const sMeta = sBlock.querySelector('.block-meta')
      const sMetaLines = metaRows(sMeta)
      const sMetaLine = px(cs(sMeta.querySelector('.meta') || sp).lineHeight)
      const sMetaChars = [...sMeta.querySelectorAll('.meta')].reduce((sum, el) => {
        const b = el.querySelector('b')
        const label = b ? b.textContent : ''
        return sum + label.length + el.textContent.replace(label, '').trim().length
      }, 0)
      // Sidebar head = name + contact fields + bio, the block the first page pays for.
      const headParts = ['h1', '.side-meta', '.side-copy'].map(s => sidebar.querySelector(s)).filter(Boolean)
      const sidebarTop = sidebar.getBoundingClientRect().top + sidePad.top
      const headBottom = headParts.length
        ? Math.max(...headParts.map(el => el.getBoundingClientRect().bottom + px(cs(el).marginBottom)))
        : sidebarTop
      side = {
        width: Math.round(sidebar.clientWidth - px(sStyle.paddingLeft) - px(sStyle.paddingRight)),
        budget: Math.round(sidebar.clientHeight - sidePad.top - sidePad.bottom),
        head: Math.round(headBottom - sidebarTop),
        line: px(cs(sp).lineHeight),
        meta: sMetaLine,
        base: Math.round(sBlock.getBoundingClientRect().height + px(cs(sBlock).marginBottom)
          - sLines * px(cs(sp).lineHeight) - sMetaLines * sMetaLine),
        charsPerLine: Math.round(sp.textContent.length / sLines * 10) / 10,
        metaChars: Math.round(sMetaChars / sMetaLines * 10) / 10,
        header: Math.round(sBlock.getBoundingClientRect().top - sBlock.closest('.section').getBoundingClientRect().top),
      }
    }

    return {
      contentWidth: Math.round(contentWidth), pairWidth: Math.round(pairWidth),
      budget: pageBudget,
      pageH: Math.round(pageEl.getBoundingClientRect().height),
      headNatural: Math.round(headNatural),
      mainClient: main.clientHeight, mainScroll: main.scrollHeight,
      font: px(pStyle.fontSize), line,
      charsPerLine: Math.round(text.length / blockLines * 10) / 10,
      pairCharsPerLine: Math.round(text.length / boxesAt(text, pairWidth, pStyle) * 10) / 10,
      metaFont: px(metaStyle.fontSize), metaLine,
      metaChars: Math.round(metaChars / metaLines * 10) / 10,
      pairMetaChars: Math.round(metaChars / pairMetaLines * 10) / 10,
      titleRow: titlePx,
      header, headerFirst, base, blockLines, blockMetaLines,
      side,
    }
  })
  rows.push({ template: file.replace('.html', ''), ...row })
}
await browser.close()
console.log(JSON.stringify(rows, null, 1))
