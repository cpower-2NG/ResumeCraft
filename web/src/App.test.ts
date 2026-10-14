import { describe, expect, it } from 'vitest'
import { ALL_IDS, BANNER_BUDGET, GRID_BUDGET, LINE_BUDGET, MAIN_BUDGET, MAIN_IDS, RAIL_BUDGET, SIDE_BUDGET, SIDE_IDS, TIMELINE_BUDGET, layoutBudget, layoutMainIds, splitText, streamItems } from './lib/resume'
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
    // 单栏布局（含 grid/line/timeline/plain）都用页头呈现姓名与联系方式；求职目标
    // 变成页头下的意向横带，不再是栏目；sidebar 侧栏承载基本信息/技能/成果（预算 px）。
    expect(layoutMainIds('grid')).toEqual(ALL_IDS.filter(id => id !== 'basics' && id !== 'target'))
    expect(layoutMainIds('line')).toEqual(layoutMainIds('banner'))
    expect(layoutMainIds('timeline')).toEqual(ALL_IDS.filter(id => id !== 'basics' && id !== 'target'))
    expect(layoutMainIds('plain')).toEqual(ALL_IDS.filter(id => id !== 'basics' && id !== 'target'))
    expect(layoutMainIds('rail')).toEqual(layoutMainIds('plain'))
    expect(layoutMainIds('sidebar')).toEqual(MAIN_IDS)
    expect(layoutBudget('grid')).toBe(GRID_BUDGET)
    expect(layoutBudget('line')).toBe(LINE_BUDGET)
    expect(layoutBudget('timeline')).toBe(TIMELINE_BUDGET)
    expect(layoutBudget('banner')).toBe(BANNER_BUDGET)
    expect(layoutBudget('rail')).toBe(RAIL_BUDGET)
    expect(layoutBudget('sidebar')).toBe(MAIN_BUDGET)
    expect(layoutBudget('sidebar')).toBeGreaterThan(0)
  })

  it('paginates long content into multiple pages for the new layouts', () => {
    for (const layout of ['grid', 'line', 'timeline']) {
      const pages = streamItems(
        makeContent([{ id: 'experience', blocks: [makeBlock('long', '很'.repeat(6000))] }]),
        layoutMainIds(layout), layoutBudget(layout), false, layout,
      )
      expect(pages.length).toBeGreaterThan(1)
      // 排在长栏目之后的空栏目可能被挤到后续页，续页标记只应检查长栏目自身的条目。
      const later = pages.slice(1).flatMap(page => flowOf(page)).filter(it => it.section.id === 'experience')
      expect(later.length).toBeGreaterThan(0)
      expect(later.every(it => it.continued)).toBe(true)
    }
  })

  it('pairs short adjacent sections only in the table layout, without reordering the resume', () => {
    // 相邻短栏目并排成表格行 belong to 表格表单 only；其余版式一律整宽通排（依据见
    // app/services.py 的 PAIR_BUDGET_BY_LAYOUT 注释）。配对也不得打乱栏目顺序。
    const content = makeContent([
      { id: 'target', blocks: [makeBlock('t', '求职目标内容')] },
      { id: 'profile', blocks: [makeBlock('p', '个人简介内容')] },
      { id: 'experience', blocks: [makeBlock('e', '很长的经历正文'.repeat(60))] },
      { id: 'education', blocks: [makeBlock('edu', '教育内容')] },
      { id: 'skills', blocks: [makeBlock('skill', '技能内容')] },
      { id: 'awards', blocks: [makeBlock('award', '成果内容')] },
      { id: 'links', blocks: [makeBlock('link', '链接内容')] },
    ])
    const gridUnits = streamItems(content, ALL_IDS.filter(id => id !== 'basics'), layoutBudget('grid'), false, 'grid').flat()
    const appeared: string[] = []
    for (const unit of gridUnits) {
      const group = unit.kind === 'pair' ? [unit.sectionA.id, unit.sectionB.id] : [unit.section.id]
      for (const id of group) if (!appeared.includes(id)) appeared.push(id)
    }
    expect(appeared).toEqual(ALL_IDS.filter(id => id !== 'basics'))
    expect(pairsOf(gridUnits).length).toBeGreaterThan(0)
    // 主栏内容（项目与实践）不参与并排，保持整宽通排。
    expect(pairsOf(gridUnits).some(p => p.sectionA.id === 'experience' || p.sectionB.id === 'experience')).toBe(false)
    // 其余版式一处都不并排：单栏（兼容性优先）、侧栏（页级两栏）、时间轴（左时间栏是识别特征）。
    for (const layout of ['plain', 'banner', 'line', 'sidebar', 'timeline']) {
      const ids = layout === 'sidebar' ? MAIN_IDS : layoutMainIds(layout)
      const units = streamItems(content, ids, layoutBudget(layout), false, layout).flat()
      expect(pairsOf(units).length, layout).toBe(0)
    }
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
    // Every main section renders (empty ones become a "pick content" placeholder).
    const firstPageFlow = flowOf(empty[0])
    expect(firstPageFlow.length).toBe(MAIN_IDS.length)
    expect(flowOf(empty[0]).at(-1)?.section.id).toBe('links')
    const side = streamItems(makeContent([{ id: 'skills', blocks: [makeBlock('s1', '技能描述')] }]), SIDE_IDS, SIDE_BUDGET, true)
    const sideFlow = flowOf(side[0])
    expect(sideFlow.length).toBe(SIDE_IDS.length)
    expect(sideFlow.find(it => it.section.id === 'skills')?.continued).toBe(false)
  })

  it('charges empty sections no budget so preview breaks match the export', () => {    // 导出端（app/services.py）把这些栏目整个剔掉，画布则保留它们作为可点选入口。
    // 只有占位行不计版面，预览与导出的断页才会落在同一处——回归过：占位行一旦计价，
    // 它会替后面的第一个栏目占掉 header_first 的便宜，预览比导出更早断页。
    const blocks = [makeBlock('long', '很'.repeat(3000))]
    const withEmpty = streamItems(
      makeContent([{ id: 'profile', blocks: [] }, { id: 'experience', blocks }]),
      ['profile', 'experience'], MAIN_BUDGET, false,
    )
    const withoutEmpty = streamItems(makeContent([{ id: 'experience', blocks }]), ['experience'], MAIN_BUDGET, false)
    expect(withEmpty.length).toBe(withoutEmpty.length)
    const placeholders = flowOf(withEmpty.flat()).filter(it => it.block.origin === 'empty')
    expect(placeholders.map(it => it.section.id)).toEqual(['profile'])
    // 每一页上的真实条目（不含占位行）与没有空栏目时完全一致。
    const realIds = (pages: typeof withEmpty) => pages.map(page => flowOf(page).filter(it => it.block.origin !== 'empty').map(it => it.block.id))
    expect(realIds(withEmpty)).toEqual(realIds(withoutEmpty))
  })
})
