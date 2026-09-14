import { describe, expect, it } from 'vitest'
import { ALL_IDS, BANNER_BUDGET, GRID_BUDGET, LINE_BUDGET, MAIN_BUDGET, MAIN_IDS, SIDE_BUDGET, SIDE_IDS, TIMELINE_BUDGET, layoutBudget, layoutMainIds, splitText, streamItems } from './lib/resume'
import type { Block, Content, Unit } from './lib/resume'

const makeBlock = (id: string, content: string): Block => ({ id, title: `标题${id}`, content, source_refs: [], origin: 'fact' })
const makeContent = (sections: { id: string; blocks: Block[] }[]): Content => ({
  sections: sections.map(s => ({ id: s.id, title: s.id, visibility: true, blocks: s.blocks })),
})
const flowOf = (page: readonly Unit[]) => page.filter((u): u is Extract<Unit, { kind: 'flow' }> => u.kind === 'flow')
const pairsOf = (units: Unit[]) => units.filter((u): u is Extract<Unit, { kind: 'pair' }> => u.kind === 'pair')

describe('splitText', () => {
  it('splits long text into fixed-size chunks', () => {
    expect(splitText('a'.repeat(10), 4)).toEqual(['aaaa', 'aaaa', 'aa'])
    expect(splitText('', 4)).toEqual([''])
  })
})

describe('layoutMainIds / layoutBudget for new layouts', () => {
  it('mirrors the export renderer for grid/line/timeline', () => {
    // 单栏布局（含 grid/line/timeline/plain）都用页头呈现姓名与联系方式，正文
    // 从求职目标开始；sidebar 侧栏承载基本信息/技能/成果，主栏五栏（预算 px）。
    expect(layoutMainIds('grid')).toEqual(ALL_IDS.filter(id => id !== 'basics'))
    expect(layoutMainIds('line')).toEqual(layoutMainIds('banner'))
    expect(layoutMainIds('timeline')).toEqual(ALL_IDS.filter(id => id !== 'basics'))
    expect(layoutMainIds('plain')).toEqual(ALL_IDS.filter(id => id !== 'basics'))
    expect(layoutMainIds('sidebar')).toEqual(MAIN_IDS)
    expect(layoutBudget('grid')).toBe(GRID_BUDGET)
    expect(layoutBudget('line')).toBe(LINE_BUDGET)
    expect(layoutBudget('timeline')).toBe(TIMELINE_BUDGET)
    expect(layoutBudget('banner')).toBe(BANNER_BUDGET)
    expect(layoutBudget('sidebar')).toBe(MAIN_BUDGET)
    expect(layoutBudget('sidebar')).toBeGreaterThan(0)
  })

  it('paginates long content into multiple pages for the new layouts', () => {
    for (const layout of ['grid', 'line', 'timeline']) {
      const pages = streamItems(
        makeContent([{ id: 'experience', blocks: [makeBlock('long', '很'.repeat(2000))] }]),
        layoutMainIds(layout), layoutBudget(layout), false, layout,
      )
      expect(pages.length).toBeGreaterThan(1)
      // 排在长栏目之后的空栏目可能被挤到后续页，续页标记只应检查长栏目自身的条目。
      const later = pages.slice(1).flatMap(page => flowOf(page)).filter(it => it.section.id === 'experience')
      expect(later.length).toBeGreaterThan(0)
      expect(later.every(it => it.continued)).toBe(true)
    }
  })

  it('pairs the compact tail sections of single-column layouts', () => {
    // 教育/技能高度接近时两两并排（一行两个模块）；时间轴不参与配对。
    const content = makeContent([
      { id: 'education', blocks: [makeBlock('edu', '教育内容')] },
      { id: 'skills', blocks: [makeBlock('skill', '技能内容')] },
      { id: 'awards', blocks: [makeBlock('award', '成果内容')] },
      { id: 'links', blocks: [makeBlock('link', '链接内容')] },
    ])
    for (const layout of ['plain', 'grid', 'line', 'banner', 'sidebar']) {
      const ids = layout === 'sidebar' ? MAIN_IDS : ALL_IDS.filter(id => id !== 'basics')
      const units = streamItems(content, ids, layoutBudget(layout), false, layout).flat()
      const pairs = pairsOf(units)
      expect(pairs.length, layout).toBeGreaterThan(0)
      expect(pairs[0].sectionA.id, layout).toBe('education')
    }
    const timelineUnits = streamItems(content, layoutMainIds('timeline'), layoutBudget('timeline'), false, 'timeline').flat()
    expect(pairsOf(timelineUnits).length).toBe(0)
  })
})

describe('streamItems section aggregation', () => {
  it('keeps consecutive blocks in one section so headings do not repeat', () => {
    const pages = streamItems(
      makeContent([{ id: 'experience', blocks: [makeBlock('p1', 'p1 的内容'), makeBlock('p2', 'p2 的内容'), makeBlock('p3', 'p3 的内容')] }]),
      MAIN_IDS, MAIN_BUDGET, false,
    )
    const first = flowOf(pages[0]).filter(it => it.section.id === 'experience')
    expect(first.map(it => it.block.id)).toEqual(['p1', 'p2', 'p3'])
    expect(new Set(first.map(it => it.section.id)).size).toBe(1)
    expect(first.every(it => !it.continued)).toBe(true)
  })

  it('marks a heading as continued when its blocks move to a later page', () => {
    const pages = streamItems(
      makeContent([{ id: 'experience', blocks: [makeBlock('short', '短内容'), makeBlock('long', '很'.repeat(2000))] }]),
      MAIN_IDS, MAIN_BUDGET, false, 'sidebar',
    )
    expect(pages.length).toBeGreaterThan(1)
    const later = pages.slice(1).flatMap(page => flowOf(page)).filter(it => it.section.id === 'experience')
    expect(later.length).toBeGreaterThan(0)
    expect(later.every(it => it.continued)).toBe(true)
  })

  it('keeps empty sections renderable and packs the sidebar stream independently', () => {
    const empty = streamItems(makeContent([{ id: 'links', blocks: [] }]), MAIN_IDS, MAIN_BUDGET, false)
    // Every main section renders (empty ones show their title only).
    const firstPageFlow = flowOf(empty[0])
    expect(firstPageFlow.length).toBe(MAIN_IDS.length)
    expect(flowOf(empty[0]).at(-1)?.section.id).toBe('links')
    const side = streamItems(makeContent([{ id: 'skills', blocks: [makeBlock('s1', '技能描述')] }]), SIDE_IDS, SIDE_BUDGET, true)
    const sideFlow = flowOf(side[0])
    expect(sideFlow.length).toBe(SIDE_IDS.length)
    expect(sideFlow.find(it => it.section.id === 'skills')?.continued).toBe(false)
  })
})
