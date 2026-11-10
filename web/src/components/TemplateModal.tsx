import { Modal, Loading } from './ui'
import { layoutLabel, parsingNote, templateThumbStyle, type TemplateDescriptor } from '../lib/templates'

export function TemplateModal({current,templates,loading,onChoose,close}:{current:number|undefined;templates:TemplateDescriptor[];loading:boolean;onChoose:(templateId:number)=>void;close:()=>void}){
  const note=current===undefined?null:parsingNote(templates.find(t=>t.id===current)||{layout:'plain'})
  return <Modal title="选择模板" close={close}>
    <p className="modal-note">模板决定当前 A4 版式与配色，画布与导出使用同一份模板数据。切换模板只改变视觉，不修改正文、不标记内容脏、也不会生成正式版本。</p>
    <p className="modal-note">版式的“机器可读性”是取舍，不是好坏：<b className="parse-badge safe">单栏</b> 解析顺序与阅读顺序一致，最稳但占页；<b className="parse-badge caution">双栏页</b> 用侧栏装短内容，省页但部分 ATS 会读乱右栏；<b className="parse-badge risky">表格</b> 最省页，却被 Greenhouse 明文列为解析失败原因。</p>
    {loading?<Loading/>:<div className="template-grid">{templates.map(t=><button key={t.template_key} className={`template-card${t.id===current?' current':''}`} onClick={()=>onChoose(t.id)}>
      <span className="template-thumb" style={templateThumbStyle(t)}/>
      <b>{t.display_name}</b>
      <small>{t.description}</small>
      <em>{layoutLabel(t.layout)}<span className={`parse-badge ${parsingNote(t).level}`} title={parsingNote(t).hint}>{parsingNote(t).label}</span></em>
      {t.id===current&&<span className="template-current">当前模板</span>}
    </button>)}</div>}
    {note&&<p className="modal-note parse-hint">{note.hint}</p>}
  </Modal>
}
