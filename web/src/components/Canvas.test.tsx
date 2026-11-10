import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { Canvas } from './Canvas'
import type { Content } from '../lib/resume'
import type { TemplateInfo } from '../lib/templates'

const photo = {
  photo_id: 9,
  evidence_id: 10,
  preview_url: '/api/evidence/10/file',
  filename: 'portrait.png',
  mime_type: 'image/png',
  data_url: 'data:image/png;base64,cG9ydHJhaXQ=',
}

function content(withPhoto: boolean): Content {
  return {
    sections: [
      {
        id: 'basics',
        title: '基本信息',
        visibility: true,
        blocks: [{
          id: 'fact-1',
          title: '陈晓',
          content: '',
          fields: { phone: '13800000000', email: 'chen@example.com' },
          display_fields: ['phone', 'email'],
          source_refs: [1],
          origin: 'fact',
          ...(withPhoto ? { photo } : {}),
        }],
      },
      {
        id: 'experience',
        title: '项目与实践',
        visibility: true,
        blocks: [{
          id: 'fact-2',
          title: '项目',
          content: '完成核心功能。',
          fields: {},
          display_fields: [],
          source_refs: [2],
          origin: 'fact',
        }],
      },
    ],
  }
}

const template = (layout: string): TemplateInfo => ({
  id: 1,
  template_key: layout,
  display_name: layout,
  layout,
  status: 'available',
})

describe('Canvas optional profile photo', () => {
  it.each(['sidebar', 'plain', 'banner', 'grid', 'line', 'timeline', 'rail'])(
    'renders the uploaded portrait in %s templates',
    layout => {
      const html = renderToStaticMarkup(
        <Canvas content={content(true)} mode="select" template={template(layout)} />
      )
      expect(html).toContain('class="resume-photo ')
      expect(html).toContain('src="data:image/png;base64,cG9ydHJhaXQ="')
      expect(html).toContain('alt="陈晓的档案照片"')
    },
  )

  it.each(['sidebar', 'plain', 'banner', 'grid', 'line', 'timeline', 'rail'])(
    'keeps %s templates unchanged when the optional photo is absent',
    layout => {
      const html = renderToStaticMarkup(
        <Canvas content={content(false)} mode="select" template={template(layout)} />
      )
      expect(html).not.toContain('resume-photo')
      expect(html).not.toContain(' has-photo')
    },
  )
})
