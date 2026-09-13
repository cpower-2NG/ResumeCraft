import { Canvas } from './Canvas'
import { Loading, Modal, useLoad } from './ui'
import { layoutLabel, type TemplateDescriptor } from '../lib/templates'
import { SAMPLE_CONTENT } from '../lib/sampleResume'

// Creation-time template gallery: a large-card modal listing every template
// with a real A4 preview, so the template is chosen before entering the
// workbench instead of being switched afterwards.
export function TemplateGalleryModal({current,onChoose,close}:{current:number|undefined;onChoose:(templateVersionId:number)=>void;close:()=>void}){
  const templates=useLoad<TemplateDescriptor[]>('/api/templates',[])
  return <Modal title="选择简历模板" close={close} className="template-gallery-modal">
    <p className="modal-note">先选模板确定 A4 版式与配色，再进入临时简历选择资料。卡片即真实渲染效果，与正式导出一致。</p>
    {templates.loading?<Loading/>:<div className="gallery-grid">{templates.data.map(t=><button key={t.slug} className={`gallery-card${t.template_version_id===current?' current':''}`} onClick={()=>onChoose(t.template_version_id)}>
      <div className="gallery-preview"><div className="template-preview-stage" style={{zoom:.26}}><Canvas content={SAMPLE_CONTENT} mode="select" template={t}/></div></div>
      <div className="gallery-info">
        <b>{t.name}</b>
        <small>{t.description}</small>
        <em>{layoutLabel(t.layout)}{t.template_version_id===current?' · 已在模板库选中':''}</em>
      </div>
      <span className="gallery-cta">用此模板创建</span>
    </button>)}</div>}
  </Modal>
}
