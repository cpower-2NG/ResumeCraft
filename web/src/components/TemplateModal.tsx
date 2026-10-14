import { Modal, Loading } from './ui'
import { layoutLabel, parsingNote, templateThumbStyle, type TemplateDescriptor } from '../lib/templates'

export function TemplateModal({current,templates,loading,onChoose,close}:{current:number|undefined;templates:TemplateDescriptor[];loading:boolean;onChoose:(templateVersionId:number)=>void;close:()=>void}){
  const note=current===undefined?null:parsingNote(templates.find(t=>t.template_version_id===current)||{layout:'plain'})
  return <Modal title="选择模板" close={close}>
    <p className="modal-note">模板决定 A4 版式与配色，画布与导出使用同一份模板数据。切换先保存在工作副本中，正式保存后形成新版本（原因标记为“模板调整”），历史版本继续使用原模板。</p>
    <p className="modal-note">版式的“机器可读性”是取舍，不是好坏：<b className="parse-badge safe">单栏</b> 解析顺序与阅读顺序一致，最稳但占页；<b className="parse-badge caution">双栏页</b> 用侧栏装短内容，省页但部分 ATS 会读乱右栏；<b className="parse-badge risky">表格</b> 最省页，却被 Greenhouse 明文列为解析失败原因。</p>
    {loading?<Loading/>:<div className="template-grid">{templates.map(t=><button key={t.slug} className={`template-card${t.template_version_id===current?' current':''}`} onClick={()=>onChoose(t.template_version_id)}>
      <span className="template-thumb" style={templateThumbStyle(t)}/>
      <b>{t.name}</b>
      <small>{t.description}</small>
      <em>{layoutLabel(t.layout)}<span className={`parse-badge ${parsingNote(t).level}`} title={parsingNote(t).hint}>{parsingNote(t).label}</span></em>
      {t.template_version_id===current&&<span className="template-current">当前模板</span>}
    </button>)}</div>}
    {note&&<p className="modal-note parse-hint">{note.hint}</p>}
  </Modal>
}
