import { describe, expect, it } from 'vitest'
import { MAIN_BUDGET, MAIN_IDS, SIDE_BUDGET, SIDE_IDS, splitText, streamItems } from './App'
import type { Block, Content } from './App'

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
