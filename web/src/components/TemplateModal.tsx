import { Modal, Loading } from './ui'
import { layoutLabel, templateThumbStyle, type TemplateDescriptor } from '../lib/templates'

export function TemplateModal({current,templates,loading,onChoose,close}:{current:number|undefined;templates:TemplateDescriptor[];loading:boolean;onChoose:(templateVersionId:number)=>void;close:()=>void}){
  return <Modal title="选择模板" close={close}>
    <p className="modal-note">模板决定 A4 版式与配色，画布与导出使用同一份模板数据。切换先保存在工作副本中，正式保存后形成新版本（原因标记为“模板调整”），历史版本继续使用原模板。</p>
    {loading?<Loading/>:<div className="template-grid">{templates.map(t=><button key={t.slug} className={`template-card${t.template_version_id===current?' current':''}`} onClick={()=>onChoose(t.template_version_id)}>
      <span className="template-thumb" style={templateThumbStyle(t)}/>
      <b>{t.name}</b>
      <small>{t.description}</small>
      <em>{layoutLabel(t.layout)}</em>
      {t.template_version_id===current&&<span className="template-current">当前模板</span>}
    </button>)}</div>}
  </Modal>
}
