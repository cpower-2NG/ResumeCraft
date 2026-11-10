import { useEffect, useRef, useState } from 'react'
import { ArchiveRestore, CircleAlert, Download, Eye, FilePenLine, History, LayoutTemplate, Plus, Trash2 } from 'lucide-react'
import { del, patch, post } from '../api'
import { BenchHead } from '../components/BenchHead'
import { Canvas } from '../components/Canvas'
import { Picker } from '../components/Picker'
import { StageToolbar } from '../components/StageToolbar'
import { TemplateModal } from '../components/TemplateModal'
import { Field, Loading, Modal, useLoad } from '../components/ui'
import { brief, date, factBlock, factCategories, fieldLabels, fragmentLimit, inSidebarStream, labels, pageCountOf, SIDE_IDS, splitText, type Block, type Content, type Fact, type Pending, type UpdateBlock } from '../lib/resume'
import type { TemplateDescriptor } from '../lib/templates'

type BlockMenu={sectionId:string;blockId:string;fragmentIndex:number;x:number;y:number}
type LintIssue={level:string;section_id:string;block_id:string;message:string}

export function Editor({id,back,error,refresh,focusBlock,onFocusLocated}:{id:number;back:()=>void;error:(s:string)=>void;refresh:()=>void;focusBlock:{sectionId:string;blockId:string}|null;onFocusLocated:()=>void}){
  const resume=useLoad<any>(`/api/resumes/${id}`,null)
  const versions=useLoad<any[]>(`/api/resumes/${id}/versions`,[])
  const facts=useLoad<Fact[]>('/api/facts',[])
  const pending=useLoad<Pending[]>('/api/pending-issues',[])
  const templates=useLoad<TemplateDescriptor[]>('/api/templates',[])
  const [content,setContent]=useState<Content|null>(null)
  const baseline=useRef('')
  const [restore,setRestore]=useState<number|null>(null)
  const [pick,setPick]=useState<string|null>(null)
  const [saving,setSaving]=useState(false)
  const [editing,setEditing]=useState<{sectionId:string;blockId:string;fragmentIndex:number}|null>(null)
  const [menu,setMenu]=useState<BlockMenu|null>(null)
  const [confirmLeave,setConfirmLeave]=useState(false)
  const [diffWith,setDiffWith]=useState<number|null>(null)
  const [templateOpen,setTemplateOpen]=useState(false)
  const [zoom,setZoom]=useState(1)
  const [compact,setCompact]=useState(false)
  const [lint,setLint]=useState<LintIssue[]>([])
  // 体检结果默认只给一行汇总：问题多时（实测真实简历可到 9 条）平铺会把 A4 画布
  // 挤到首屏之外，而用户打开编辑器第一眼要看的是简历本身。
  const [lintOpen,setLintOpen]=useState(false)
  useEffect(()=>{const h=()=>setCompact(window.scrollY>150);window.addEventListener('scroll',h);return()=>window.removeEventListener('scroll',h)},[])
  useEffect(()=>{if(resume.data){setContent(resume.data.working_copy.content);baseline.current=JSON.stringify(resume.data.working_copy.content)}},[resume.data])
  // 导出体检与草稿同步：判定规则与导出 HTML 里的告警条同源（后端 lint_resume），
  // 草稿变化后防抖拉取，问题亮在画布上方，打印/导出正文不受影响。
  useEffect(()=>{
    if(!content)return
    const t=window.setTimeout(()=>{post<{issues:LintIssue[]}>(`/api/resumes/${id}/lint`,{}).then(r=>setLint(r.issues||[])).catch(()=>setLint([]))},600)
    return()=>window.clearTimeout(t)
  },[content,id])
  // Locate and flash the block affected by a pending item after navigation.
  useEffect(()=>{
    if(!content||!focusBlock)return
    const el=document.querySelector(`[data-block-key="${focusBlock.sectionId}:${focusBlock.blockId}"]`) as HTMLElement|null
    if(!el)return
    el.scrollIntoView({behavior:'smooth',block:'center'})
    el.classList.remove('flash-highlight');void el.offsetWidth;el.classList.add('flash-highlight')
    // Clear the focus target only after the flash finishes: clearing earlier
    // re-renders the canvas and would wipe the manually added class.
    window.setTimeout(()=>{el.classList.remove('flash-highlight');onFocusLocated()},3500)
  },[content,focusBlock])
  // Only edits that diverge from the loaded baseline count as unsaved changes;
  // merely opening a resume must never mark the working copy dirty. A template
  // switch or server-side draft (working_copy.dirty) also counts as unsaved.
  const localDirty=(!!content&&baseline.current!==''&&JSON.stringify(content)!==baseline.current)||resume.data?.working_copy.content_state==='dirty'
  useEffect(()=>{if(!content||!resume.data||resume.data.status==='recycled')return;const payload=JSON.stringify(content);if(payload===baseline.current)return;const t=window.setTimeout(()=>{patch(`/api/resumes/${id}/working-copy`,{content}).catch(e=>error(e.message))},500);return()=>clearTimeout(t)},[content,id,resume.data])
  if(!content||!resume.data)return <Loading/>
  const readOnly=resume.data.status==='recycled'
  const changed=pending.data.filter(x=>x.resume_id===id&&x.section_code&&x.block_key).map(x=>`${x.section_code}:${x.block_key}`)
  const lintErrors=lint.filter(issue=>issue.level==='error').length
  const update:UpdateBlock=(sid,bid,value,key='content',fieldKey,fragmentIndex)=>setContent(old=>{
    if(!old)return old
    return {sections:old.sections.map(s=>{
      if(s.id!==sid)return s
      return {...s,blocks:s.blocks.map(b=>{
        if(b.id!==bid)return b
        const next={...b,origin:'user'} as Block
        if(key==='field'&&fieldKey){next.fields={...b.fields,[fieldKey]:value};return next}
        if(key==='title'){next.title=value;return next}
        if(fragmentIndex===undefined){next.content=value;return next}
        const chunks=splitText(b.content||'',fragmentLimit(inSidebarStream(resume.data?.template?.layout,sid)))
        chunks[fragmentIndex]=value
        // splitText slices by position, so reassembly must be a plain concat;
        // joining with '\n' would inject newlines at every fragment boundary.
        next.content=chunks.join('')
        return next
      })}
    })}
  })
  const removeBlock=(sid:string,bid:string)=>setContent(old=>old?{sections:old.sections.map(s=>s.id!==sid?s:{...s,blocks:s.blocks.filter(b=>b.id!==bid)})}:old)
  // 整栏隐藏：写进内容的 visibility（工作副本 → 版本），导出端读同一个字段决定排不排。
  // 结构上保留栏目与条目，所以恢复时不需要重建任何东西。
  const setSectionVisible=(sid:string,visible:boolean)=>setContent(old=>{
    if(!old)return old
    const exists=old.sections.some(s=>s.id===sid)
    return {sections:exists
      ? old.sections.map(s=>s.id===sid?{...s,visibility:visible}:s)
      : [...old.sections,{id:sid,title:labels[sid],visibility:visible,blocks:[]}]}
  })
  const moveBlock=(sid:string,bid:string,dir:1|-1)=>setContent(old=>{
    if(!old)return old
    return {sections:old.sections.map(s=>{
      if(s.id!==sid)return s
      const index=s.blocks.findIndex(b=>b.id===bid),target=index+dir
      if(index<0||target<0||target>=s.blocks.length)return s
      const blocks=[...s.blocks];[blocks[index],blocks[target]]=[blocks[target],blocks[index]]
      return {...s,blocks}
    })}
  })
  const addFact=(fact:Fact)=>{
    if(!pick)return
    const block=factBlock(fact,pick)
    setContent(old=>old?{sections:old.sections.map(s=>s.id===pick?{...s,blocks:[...s.blocks,block]}:s)}:old)
    setPick(null)
  }
  const save=async()=>{
    if(saving||readOnly)return
    setSaving(true)
    try{await post(`/api/resumes/${id}/save`,{change_summary:'用户保存正式版本',expected_version_id:resume.data.current_version_id});resume.reload();versions.reload();refresh()}
    catch(e){error((e as Error).message)}
    finally{setSaving(false)}
  }
  const discard=async()=>{
    try{await post(`/api/resumes/${id}/versions/${resume.data.current_version}/restore`);resume.reload();versions.reload();refresh()}
    catch(e){error((e as Error).message)}
  }
  const exportVersion=async(v:number)=>{try{await downloadExport(id,v)}catch(e){error((e as Error).message)}}
  const openEdit=(target:{sectionId:string;blockId:string;fragmentIndex:number})=>{setMenu(null);setEditing(target)}
  const openMenu=(target:{sectionId:string;blockId:string;fragmentIndex:number},x:number,y:number)=>{setEditing(null);setMenu({...target,x,y})}
  const addSource=(sid:string)=>{setMenu(null);setPick(sid)}
  const requestBack=()=>{if(localDirty&&!readOnly)setConfirmLeave(true);else back()}
  const versionLabel=resume.data.current_version?`v${resume.data.current_version}`:'未保存'
  const menuSection=menu?content.sections.find(s=>s.id===menu.sectionId)||null:null
  const menuBlock=menu&&menuSection?menuSection.blocks.find(b=>b.id===menu.blockId)||null:null
  const menuIndex=menuSection&&menuBlock?menuSection.blocks.indexOf(menuBlock):-1
  const layout=resume.data.template?.layout||'sidebar'
  // 已隐藏的栏目：列表里给回恢复入口，否则隐藏后画布上就再也点不到它了。
  const hiddenTitles=content.sections.filter(s=>s.visibility===false).map(s=>[s.id,s.title||labels[s.id]] as [string,string])
  // 体检条目点击定位：滚动到对应块并闪烁一次（与待办定位同一套视觉）。
  const locateBlock=(sectionId:string,blockId:string)=>{
    const el=document.querySelector(`[data-block-key="${sectionId}:${blockId}"]`) as HTMLElement|null
    if(!el)return
    el.scrollIntoView({behavior:'smooth',block:'center'})
    el.classList.remove('flash-highlight');void el.offsetWidth;el.classList.add('flash-highlight')
    window.setTimeout(()=>el.classList.remove('flash-highlight'),1600)
  }
  return <main className="workbench">
    <BenchHead title={`正式简历 · ${versionLabel}`} subtitle={`${resume.data.profile_name} · ${readOnly?'已移入回收站':resume.data.evidence_sync_state!=='clean'?'证据同步待合并':resume.data.baseline_state==='stale'?'工作副本基线已过期':localDirty?'工作副本有未保存修改':'工作副本已同步'}`} back={requestBack} compact={compact}/>
    {changed.length>0&&!readOnly&&<div className="warning-banner compact"><CircleAlert size={17}/><div><b>来源资料已变化</b><span>受影响条目已标记；正文没有被自动改写。</span></div></div>}
    {!readOnly&&lint.length>0&&<div className="lint-banner compact">
      <CircleAlert size={17}/>
      <div>
        <b>导出体检发现 {lint.length} 个问题（打印时不会出现在简历上）{lintErrors>0?` · 必须处理 ${lintErrors} 项`:''}</b>
        <button className="lint-toggle" onClick={()=>setLintOpen(v=>!v)}>{lintOpen?'收起详情':'查看详情'}</button>
        {lintOpen&&<span>{lint.map(issue=><button key={`${issue.section_id}:${issue.block_id}:${issue.message}`} className={`lint-item lint-${issue.level}`} title={issue.block_id?'点击定位到对应条目':undefined} onClick={()=>issue.block_id&&locateBlock(issue.section_id,issue.block_id)}>{issue.level==='error'?'必须处理':'建议处理'}：{issue.message}</button>)}</span>}
      </div>
    </div>}
    <StageToolbar zoom={zoom} setZoom={setZoom} pageCount={pageCountOf(content,layout)}/>
    {!readOnly&&hiddenTitles.length>0&&<div className="hidden-sections">
      <span>已隐藏 {hiddenTitles.length} 个栏目：</span>
      {hiddenTitles.map(([sid,title])=><button key={sid} className="button" onClick={()=>setSectionVisible(sid,true)}><Eye size={13}/>{title} · 恢复</button>)}
    </div>}
    <div className="stage-zoom" style={{zoom}}>
      <Canvas content={content} mode={readOnly?'select':'edit'} template={resume.data.template} changed={changed} addFact={setPick} onEdit={openEdit} onContext={openMenu} onToggleSection={setSectionVisible}/>
    </div>
    <section className="version-panel">
      <header><History size={17}/><h2>版本历史</h2></header>
      {versions.data.map(v=><div className="version-row" key={v.id}><span><b>v{v.version_number}</b><small>{v.reason==='format_conversion'?'格式化简历、未润色':v.reason==='rollback'?'历史版本回退':v.reason==='evidence_sync'?'证据同步':v.change_summary} · {date(v.created_at)}</small></span><div className="card-actions">{v.version_number!==resume.data.current_version&&<button className="button" onClick={()=>setDiffWith(v.version_number)}>对比当前</button>}<button className="button" onClick={()=>exportVersion(v.version_number)}><Download size={14}/>导出 HTML</button>{!readOnly&&v.version_number!==resume.data.current_version&&<button className="button" onClick={()=>setRestore(v.version_number)}>以 v{v.version_number} 创建工作副本</button>}</div></div>)}
    </section>
    <footer className="actionbar">
      {readOnly
        ? <button className="button primary" onClick={async()=>{try{await post(`/api/resumes/${id}/restore`);resume.reload();versions.reload()}catch(e){error((e as Error).message)}}}><ArchiveRestore size={15}/>恢复简历</button>
        : <button className="button danger" onClick={async()=>{if(confirm('正式简历将进入回收站，历史版本会保留。确认继续？')){await del(`/api/resumes/${id}`);back()}}}><Trash2 size={15}/>删除简历</button>}
      {!readOnly&&<button className="button" disabled={!localDirty||!resume.data.current_version} onClick={discard}>放弃修改</button>}
      <button className="button" onClick={()=>setTemplateOpen(true)}><LayoutTemplate size={15}/>模板</button>
      <button className="button" disabled={!resume.data.current_version} onClick={()=>exportVersion(resume.data.current_version)}><Download size={15}/>导出正式简历</button>
      <button className="button primary" disabled={saving||readOnly} onClick={save}>{saving?'保存中…':readOnly?'已回收':'保存正式版本'}</button>
    </footer>
    {!readOnly&&pick&&<Picker title={`为${labels[pick]}添加来源`} facts={facts.data.filter(f=>factCategories(pick).includes(f.category_code))} chosen={[]} toggle={fid=>{const f=facts.data.find(x=>x.id===fid);if(f)addFact(f)}} close={()=>setPick(null)}/>}
    {!readOnly&&restore!==null&&<Modal title="以历史版本创建工作副本" close={()=>setRestore(null)}><p className="modal-note">将以 v{restore} 替换当前工作副本，历史版本不受影响。</p><div className="modal-actions"><button className="button" onClick={()=>setRestore(null)}>保留当前草稿</button><button className="button primary" onClick={async()=>{try{await post(`/api/resumes/${id}/versions/${restore}/restore`);setRestore(null);resume.reload();versions.reload()}catch(e){error((e as Error).message)}}}>创建工作副本</button></div></Modal>}
    {!readOnly&&confirmLeave&&<Modal title="有未保存的修改" close={()=>setConfirmLeave(false)}><p className="modal-note">当前工作副本存在未保存修改。可以选择正式保存、保留草稿离开，或放弃这些修改。</p><div className="modal-actions"><button className="button primary" onClick={async()=>{setConfirmLeave(false);await save();back()}}>保存正式版本</button><button className="button" onClick={()=>{setConfirmLeave(false);back()}}>保留工作副本并离开</button><button className="button danger" onClick={async()=>{setConfirmLeave(false);await discard();back()}}>放弃未保存修改</button></div></Modal>}
    {diffWith!==null&&<DiffModal id={id} from={diffWith} to={resume.data.current_version} close={()=>setDiffWith(null)}/>}
    {templateOpen&&<TemplateModal current={resume.data.template?.id} templates={templates.data} loading={templates.loading} onChoose={async(templateId)=>{try{await patch(`/api/resumes/${id}/template`,{template_id:templateId});setTemplateOpen(false);resume.reload()}catch(e){error((e as Error).message)}}} close={()=>setTemplateOpen(false)}/>}
    {!readOnly&&editing&&<BlockEditor content={content} target={editing} layout={layout} changed={changed.includes(`${editing.sectionId}:${editing.blockId}`)} update={update} removeBlock={removeBlock} close={()=>setEditing(null)}/>}
    {!readOnly&&menu&&<BlockContextMenu menu={menu} block={menuBlock} canMoveUp={menuBlock!==null&&menuIndex>0} canMoveDown={menuBlock!==null&&menuSection!==null&&menuIndex>-1&&menuIndex<menuSection.blocks.length-1} onEdit={openEdit} onAddSource={addSource} onRemove={sid=>{if(!menu)return;removeBlock(sid,menu.blockId);setMenu(null)}} onMove={(sid,dir)=>{if(!menu)return;moveBlock(sid,menu.blockId,dir);setMenu(null)}} onClose={()=>setMenu(null)}/>}
  </main>
}

function BlockEditor({content,target,changed,update,removeBlock,close,layout}:{content:Content;target:{sectionId:string;blockId:string;fragmentIndex:number};changed:boolean;update:UpdateBlock;removeBlock:(sid:string,bid:string)=>void;close:()=>void;layout:string}){
  const s=content.sections.find(x=>x.id===target.sectionId)
  const block=s?.blocks.find(x=>x.id===target.blockId)
  const factId=block&&block.source_refs.length?block.source_refs[0]:0
  const fact=useLoad<Fact|null>(factId?`/api/facts/${factId}`:'',null)
  const copyRef=useRef<HTMLTextAreaElement|null>(null)
  if(!s||!block)return null
  const fields=block.fields||{}
  const fieldKeys=(block.display_fields||Object.keys(fields)).filter(k=>fields[k])
  const labelsFor={...fieldLabels,...(block.field_labels||{})}
  const chunks=splitText(block.content||'',fragmentLimit(layout==='sidebar'&&SIDE_IDS.includes(target.sectionId)))
  const copy=chunks[target.fragmentIndex]||''
  const fragmentLabel=target.fragmentIndex>0?`正文 · 续段 ${target.fragmentIndex+1}`:'正文'
  const canRemove=block.source_refs.length>0
  const writeCopy=(next:string,start:number,len:number)=>{update(target.sectionId,target.blockId,next,'content',undefined,target.fragmentIndex);requestAnimationFrame(()=>{const el=copyRef.current;if(!el)return;el.focus();el.setSelectionRange(start,start+len)})}
  const wrapSelection=(before:string,after:string,placeholder:string)=>{const el=copyRef.current;if(!el)return;const start=el.selectionStart??0,end=el.selectionEnd??0;const sel=copy.slice(start,end)||placeholder;writeCopy(copy.slice(0,start)+before+sel+after+copy.slice(end),start+before.length,sel.length)}
  const makeList=()=>{const el=copyRef.current;if(!el)return;const start=el.selectionStart??0,end=el.selectionEnd??0;const sel=copy.slice(start,end)||'列表内容';const lines=sel.split('\n').map(l=>l.trim()?`- ${l}`:l).join('\n');writeCopy(copy.slice(0,start)+lines+copy.slice(end),start,lines.length)}
  const addLink=()=>{const el=copyRef.current;if(!el)return;const start=el.selectionStart??0,end=el.selectionEnd??0;const sel=copy.slice(start,end);if(!sel)return;const url=window.prompt('链接地址（https://…）');if(!url)return;const snippet=`[${sel}](${url})`;writeCopy(copy.slice(0,start)+snippet+copy.slice(end),start,snippet.length)}
  return <Modal title={`编辑 · ${labels[target.sectionId]} · ${block.title}`} close={close}>
    <Field label="条目标题"><input value={block.title} onChange={e=>update(target.sectionId,target.blockId,e.target.value,'title')}/></Field>
    {fieldKeys.length>0&&<div className="block-editor-fields">{fieldKeys.map(k=><Field key={k} label={labelsFor[k]||k}><input value={fields[k]} onChange={e=>update(target.sectionId,target.blockId,e.target.value,'field',k)}/></Field>)}</div>}
    <Field label={fragmentLabel} hint="支持 Markdown 子集：**粗体**、*斜体*、- 列表、[文字](链接)。修改会同步到工作副本并自动保存草稿。">
      <div className="format-bar">
        <button type="button" onClick={()=>wrapSelection('**','**','加粗文字')}>粗体</button>
        <button type="button" onClick={()=>wrapSelection('*','*','斜体文字')}>斜体</button>
        <button type="button" onClick={makeList}>列表</button>
        <button type="button" onClick={addLink}>链接</button>
      </div>
      <textarea ref={copyRef} className="block-editor-copy" value={copy} onChange={e=>update(target.sectionId,target.blockId,e.target.value,'content',undefined,target.fragmentIndex)}/>
    </Field>
    {block.source_refs.length>0?(
      <div className={`source-note${changed?' changed':''}`}>
        <header><b>来源提醒</b><span>{changed?'来源已变化':'事实来源 · 一致'}</span></header>
        <p><b>原始事实</b>：{fact.data?brief(fact.data):'加载中…'}</p>
        <p>编辑区中的措辞是简历正文；事实库后续修改不会自动改写这里。</p>
        {fact.data&&fact.data.evidence_count>0&&<small>该事实关联 {fact.data.evidence_count} 份证据；证据默认不出现在正文。</small>}
      </div>
    ):(
      <div className="source-note user-note">
        <header><b>来源提醒</b><span>{block.origin==='ai'?'AI 内容':'用户内容'}</span></header>
        <p>此段没有事实来源，将以用户内容呈现，不伪装为事实来源。</p>
      </div>
    )}
    <div className="modal-actions">
      {canRemove&&<button className="button danger" onClick={()=>{if(confirm('移除该条目？此操作只影响当前工作副本。')){removeBlock(target.sectionId,target.blockId);close()}}}><Trash2 size={14}/>移除条目</button>}
      <button className="button primary" onClick={close}>完成</button>
    </div>
  </Modal>
}

function BlockContextMenu({menu,block,canMoveUp,canMoveDown,onEdit,onAddSource,onRemove,onMove,onClose}:{menu:BlockMenu;block:Block|null;canMoveUp:boolean;canMoveDown:boolean;onEdit:(target:{sectionId:string;blockId:string;fragmentIndex:number})=>void;onAddSource:(sectionId:string)=>void;onRemove:(sectionId:string)=>void;onMove:(sectionId:string,dir:1|-1)=>void;onClose:()=>void}){
  const canAdd=factCategories(menu.sectionId).length>0
  const canRemove=!!block&&block.source_refs.length>0
  const left=Math.max(8,Math.min(menu.x,window.innerWidth-190))
  const top=Math.max(8,Math.min(menu.y,window.innerHeight-220))
  return <>
    <div className="context-menu-layer" onClick={onClose} onContextMenu={e=>{e.preventDefault();onClose()}}/>
    <div className="context-menu" style={{left,top}} onClick={e=>e.stopPropagation()}>
      <button onClick={()=>onEdit({sectionId:menu.sectionId,blockId:menu.blockId,fragmentIndex:menu.fragmentIndex})}><FilePenLine size={15}/>编辑文本</button>
      {canAdd&&<button onClick={()=>onAddSource(menu.sectionId)}><Plus size={15}/>添加来源</button>}
      {canRemove&&<button disabled={!canMoveUp} onClick={()=>onMove(menu.sectionId,-1)}>↑ 上移条目</button>}
      {canRemove&&<button disabled={!canMoveDown} onClick={()=>onMove(menu.sectionId,1)}>↓ 下移条目</button>}
      {canRemove&&<button className="danger" onClick={()=>{if(confirm('移除该条目？此操作只影响当前工作副本。'))onRemove(menu.sectionId)}}><Trash2 size={15}/>移除条目</button>}
      <button className="muted" onClick={onClose}>取消</button>
    </div>
  </>
}

function DiffModal({id,from,to,close}:{id:number;from:number;to:number;close:()=>void}){
  const diff=useLoad<any>(`/api/resumes/${id}/versions/${from}/diff/${to}`,{changes:[]})
  const kindLabels:Record<string,string>={added:'新增',removed:'移除',modified:'修改'}
  return <Modal title={`对比 v${from} 与 v${to}`} close={close}>
    {diff.loading?<Loading/>:diff.data.changes.length?diff.data.changes.map((c:any)=><div className="diff-row" key={c.key}>
      <div className="diff-head"><b>{c.after?.section_title||c.before?.section_title}</b><span className={`diff-kind ${c.kind}`}>{kindLabels[c.kind]||c.kind}</span></div>
      {c.before&&<p className="diff-line before"><b>v{from}</b> {c.before.title}{c.before.content?`：${c.before.content}`:''}</p>}
      {c.after&&<p className="diff-line after"><b>v{to}</b> {c.after.title}{c.after.content?`：${c.after.content}`:''}</p>}
    </div>):<p className="modal-note">两个版本的正文内容一致。</p>}
  </Modal>
}

async function downloadExport(id:number,version:number,force=false){const base=import.meta.env.VITE_API_URL||'http://127.0.0.1:8000';const r=await fetch(`${base}/api/resumes/${id}/versions/${version}/export${force?'?force=true':''}`,{method:'POST'});if(!r.ok){const detail=(await r.json().catch(()=>({}))).detail;if(r.status===409&&!force&&typeof detail==='string'&&window.confirm(`${detail}\n\n仍要导出吗？`)){return downloadExport(id,version,true)}throw new Error(typeof detail==='string'?detail:'导出失败')}const blob=await r.blob();const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`resume-v${version}.html`;a.click();URL.revokeObjectURL(url)}
