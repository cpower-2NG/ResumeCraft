import { describe, expect, it } from 'vitest'
import { ALL_IDS, BANNER_BUDGET, GRID_BUDGET, LINE_BUDGET, MAIN_BUDGET, MAIN_IDS, SIDE_BUDGET, SIDE_IDS, layoutBudget, layoutMainIds, splitText, streamItems } from './lib/resume'
import type { Block, Content } from './lib/resume'

const makeBlock = (id: string, content: string): Block => ({ id, title: `标题${id}`, content, source_refs: [], origin: 'fact' })
const makeContent = (sections: { id: string; blocks: Block[] }[]): Content => ({
  sections: sections.map(s => ({ id: s.id, title: s.id, visibility: true, blocks: s.blocks })),
})

describe('splitText', () => {
  it('splits long text into fixed-size chunks', () => {
    expect(splitText('a'.repeat(10), 4)).toEqual(['aaaa', 'aaaa', 'aa'])
    expect(splitText('', 4)).toEqual([''])
  })
})

describe('layoutMainIds / layoutBudget for new layouts', () => {
  it('mirrors the export renderer for grid/line/timeline', () => {
    // grid/line 页头取代基本信息栏目；timeline 与 plain 一样通排全部栏目。
    expect(layoutMainIds('grid')).toEqual(ALL_IDS.filter(id => id !== 'basics'))
    expect(layoutMainIds('line')).toEqual(layoutMainIds('banner'))
    expect(layoutMainIds('timeline')).toEqual(ALL_IDS)
    expect(layoutBudget('grid')).toBe(GRID_BUDGET)
    expect(layoutBudget('line')).toBe(LINE_BUDGET)
    expect(layoutBudget('timeline')).toBe(2200)
    expect(layoutBudget('banner')).toBe(BANNER_BUDGET)
    expect(layoutBudget('sidebar')).toBe(MAIN_BUDGET)
  })

  it('paginates long content into multiple pages for the new layouts', () => {
    for (const layout of ['grid', 'line', 'timeline']) {
      const pages = streamItems(
        makeContent([{ id: 'experience', blocks: [makeBlock('long', '很'.repeat(MAIN_BUDGET))] }]),
        layoutMainIds(layout), layoutBudget(layout), false,
      )
      expect(pages.length).toBeGreaterThan(1)
      // 排在长栏目之后的空栏目可能被挤到后续页，续页标记只应检查长栏目自身的条目。
      const later = pages.slice(1).flat().filter(it => it.section.id === 'experience')
      expect(later.length).toBeGreaterThan(0)
      expect(later.every(it => it.continued)).toBe(true)
    }
  })
})

describe('streamItems section aggregation', () => {
  it('keeps consecutive blocks in one section so headings do not repeat', () => {
    const pages = streamItems(
      makeContent([{ id: 'experience', blocks: [makeBlock('p1', 'p1 的内容'), makeBlock('p2', 'p2 的内容'), makeBlock('p3', 'p3 的内容')] }]),
      MAIN_IDS, MAIN_BUDGET, false,
    )
    const first = pages[0].filter(it => it.section.id === 'experience')
    expect(first.map(it => it.block.id)).toEqual(['p1', 'p2', 'p3'])
    expect(new Set(first.map(it => it.section.id)).size).toBe(1)
    expect(first.every(it => !it.continued)).toBe(true)
  })

  it('marks a heading as continued when its blocks move to a later page', () => {
    const pages = streamItems(
      makeContent([{ id: 'experience', blocks: [makeBlock('short', '短内容'), makeBlock('long', '很'.repeat(MAIN_BUDGET))] }]),
      MAIN_IDS, MAIN_BUDGET, false,
    )
    expect(pages.length).toBeGreaterThan(1)
    const later = pages.slice(1).flat().filter(it => it.section.id === 'experience')
    expect(later.length).toBeGreaterThan(0)
    expect(later.every(it => it.continued)).toBe(true)
  })

  it('keeps empty sections renderable and packs the sidebar stream independently', () => {
    const empty = streamItems(makeContent([{ id: 'links', blocks: [] }]), MAIN_IDS, MAIN_BUDGET, false)
    // Every main section renders (empty ones show their title only).
    expect(empty[0].length).toBe(MAIN_IDS.length)
    expect(empty[0].at(-1)?.block.id).toBe('links--empty')
    const side = streamItems(makeContent([{ id: 'skills', blocks: [makeBlock('s1', '技能描述')] }]), SIDE_IDS, SIDE_BUDGET, true)
    expect(side[0].length).toBe(SIDE_IDS.length)
    expect(side[0].find(it => it.section.id === 'skills')?.continued).toBe(false)
  })
})
