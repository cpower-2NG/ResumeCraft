import { LayoutTemplate, Plus } from 'lucide-react'
import { Canvas } from '../components/Canvas'
import { Loading, Title, useLoad } from '../components/ui'
import { layoutLabel, type TemplateDescriptor } from '../lib/templates'
import { SAMPLE_CONTENT } from '../lib/sampleResume'

// onCreate 带走所选模板：岗位画像里创建临时简历时会沿用这个模板。
export function TemplateLibrary({back,onCreate}:{back:()=>void;onCreate:(templateId:number)=>void}){
  const templates=useLoad<TemplateDescriptor[]>('/api/templates',[])
  return <main className="page">
    <Title crumb="模板库" title="简历模板库" desc="所有模板用同一份样例资料实时渲染，版式、配色与字体即最终导出效果。模板是全局只读目录，切换只改变当前视觉。" back={back} action={<button className="button primary" onClick={()=>onCreate(templates.data[0]?.id??0)} disabled={!templates.data.length}><Plus size={16}/>选用模板创建简历</button>}/>
    <section className="template-library-grid">{templates.loading?<Loading/>:templates.data.map(t=><article className="template-library-card" key={t.template_key}>
      <div className="template-preview"><div className="template-preview-stage" style={{zoom:.34}}><Canvas content={SAMPLE_CONTENT} mode="select" template={t}/></div></div>
      <div className="template-info"><b>{t.display_name}</b><small>{t.description}</small><em>{layoutLabel(t.layout)}</em></div>
      <div className="template-actions"><button className="button primary" onClick={()=>onCreate(t.id)}><LayoutTemplate size={15}/>用此模板创建简历</button></div>
    </article>)}</section>
  </main>
}
