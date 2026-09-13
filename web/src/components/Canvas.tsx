import type { MouseEvent as ReactMouseEvent, ReactNode } from 'react'
import type { Block, Content, Section } from '../lib/resume'
import { fieldLabels, factCategories, labels, layoutBudget, layoutMainIds, mdLite, section, SIDE_IDS, SIDE_BUDGET, sourceIdOf, streamItems } from '../lib/resume'
import { templateVars, type TemplateInfo } from '../lib/templates'

type CanvasShared={mode:'select'|'edit';select?:(s:string)=>void;changed?:string[];addFact?:(s:string)=>void;onEdit?:(target:{sectionId:string;blockId:string;fragmentIndex:number})=>void;onContext?:(target:{sectionId:string;blockId:string;fragmentIndex:number},x:number,y:number)=>void}

// Live A4 canvas: renders the same section/block stream as the export renderer,
// themed by the template descriptor through CSS variables (no per-template CSS).
export function Canvas({content,mode,template,select,changed=[],addFact,onEdit,onContext}:{content:Content;mode:'select'|'edit';template?:TemplateInfo;select?:(s:string)=>void;changed?:string[];addFact?:(s:string)=>void;onEdit?:(target:{sectionId:string;blockId:string;fragmentIndex:number})=>void;onContext?:(target:{sectionId:string;blockId:string;fragmentIndex:number},x:number,y:number)=>void}){
  const layout=template?.layout||'sidebar'
  const plain=layout==='plain'
  const banner=layout==='banner'
  const single=plain||banner
  const mainPages=streamItems(content,layoutMainIds(layout),layoutBudget(layout),false)
  const sidePages=single?[]:streamItems(content,SIDE_IDS,SIDE_BUDGET,true)
  const count=Math.max(mainPages.length,sidePages.length,1)
  const shared:CanvasShared={mode,select,changed,addFact,onEdit,onContext}
  const basicBlock=section(content,'basics').blocks[0]
  const bannerName=basicBlock?.title||'简历'
  return <section className={`resume-stage ${mode==='edit'?'edit-mode':'select-mode'}`} style={templateVars(template)} data-template={template?.slug||'classic'}>
    {Array.from({length:count},(_,i)=><Paper key={i} number={i+1} layout={layout} serif={template?.serif} sidebar={!single&&(sidePages[i]?.length?<Sidebar items={sidePages[i]} {...shared}/>:<div className="continuation-mark">RESUME / {String(i+1).padStart(2,'0')}</div>)}>
      {banner&&(i===0
        ?<header className="resume-banner"><h1>{bannerName}</h1><div className="banner-meta">{bannerFields(basicBlock)}</div></header>
        :<header className="resume-banner banner-slim"><h1>{bannerName}</h1></header>)}
      <main className="resume-main"><div className="main-sections">{renderGroups(mainPages[i]||[],shared)}</div></main>
    </Paper>)}
  </section>
}

function bannerFields(b:Block|undefined){if(!b)return null;const fields=b.fields||{};const keys=(b.display_fields||Object.keys(fields)).filter(k=>fields[k]);const labelsFor={...fieldLabels,...(b.field_labels||{})};return <>{keys.map(k=><span key={k}><b>{labelsFor[k]||k}</b> {fields[k]}</span>)}</>}

function Paper({number,layout,serif,sidebar,children}:{number:number;layout:string;serif?:boolean;sidebar:ReactNode;children:ReactNode}){const plain=layout!=='sidebar';return <article className={`resume-paper${plain?' plain':''}${layout==='banner'?' banner':''}${serif?' serif':''}`} id={`resume-page-${number}`} data-page={number}>{plain?children:<><aside className="resume-sidebar">{sidebar}</aside>{children}</>}</article>}

function Sidebar({items,...shared}:{items:{section:Section;block:Block;continued:boolean}[]}&CanvasShared){return <div className="sidebar-content">{renderGroups(items,shared)}</div>}

function renderGroups(items:{section:Section;block:Block;continued:boolean}[],shared:CanvasShared){return <>{items.length?renderGroupList(items,shared):<SectionGroup section={emptySection('target')} blocks={[]} continued={false} {...shared}/>}</>}

function emptySection(id:string):Section{return {id,title:labels[id],visibility:true,blocks:[]}}

function renderGroupList(items:{section:Section;block:Block;continued:boolean}[],shared:CanvasShared){
  const groups:{section:Section;blocks:Block[];continued:boolean}[]=[]
  for(const it of items){
    const last=groups[groups.length-1]
    if(last&&last.section.id===it.section.id){if(!it.block.id.endsWith('--empty'))last.blocks.push(it.block)}
    else groups.push({section:it.section,blocks:it.block.id.endsWith('--empty')?[]:[it.block],continued:it.continued})
  }
  if(!groups.length)groups.push({section:emptySection('target'),blocks:[],continued:false})
  return groups.map((g,index)=><SectionGroup key={`${g.section.id}-${index}`} section={g.section} blocks={g.blocks} continued={g.continued} {...shared}/>)
}

function SectionGroup({section:s,blocks,continued=false,mode,select,changed,addFact,sidebar=false,onEdit,onContext}:{section:Section;blocks:Block[];continued?:boolean}&CanvasShared&{sidebar?:boolean}){
  if(!s.visibility)return null
  const canPick=factCategories(s.id).length>0
  return <section className={`resume-section ${sidebar?'sidebar-section':''} ${mode==='select'&&canPick?'selection-ready':''}`} onClick={()=>mode==='select'&&canPick&&select?.(s.id)}>
    <div className="template-section-title"><b>{s.title}{continued&&<span className="continued-mark">（续）</span>}</b>{mode==='edit'&&canPick&&<button className="mini-button" onClick={e=>{e.stopPropagation();addFact?.(s.id)}}>添加来源</button>}</div>
    {blocks.map(b=><BlockView key={b.id} section={s} block={b} mode={mode} changed={(changed||[]).includes(`${s.id}:${sourceIdOf(b)}`)} sidebar={sidebar} onEdit={onEdit} onContext={onContext}/>)}
  </section>
}

function BlockView({section:s,block:b,mode,changed,sidebar,onEdit,onContext}:{section:Section;block:Block;mode:'select'|'edit';changed:boolean;sidebar:boolean}&Pick<CanvasShared,'onEdit'|'onContext'>){const fields=b.fields||{};const fieldKeys=(b.display_fields||Object.keys(fields)).filter(k=>fields[k]);const sourceId=sourceIdOf(b);const labelsFor={...fieldLabels,...(b.field_labels||{})};const editClick=(e:ReactMouseEvent)=>{if(mode!=='edit')return;e.stopPropagation();onEdit?.({sectionId:s.id,blockId:sourceId,fragmentIndex:b.fragment_index??0})};const editContext=(e:ReactMouseEvent)=>{if(mode!=='edit')return;e.preventDefault();e.stopPropagation();onContext?.({sectionId:s.id,blockId:sourceId,fragmentIndex:b.fragment_index??0},e.clientX,e.clientY)};const showTitle=!!b.title&&b.title!==s.title;return <article className={`resume-block ${changed?'changed-block':''} ${b.continuation?'continuation-block':''} ${mode==='edit'?'editable-block':''}`} data-block-key={`${s.id}:${sourceId}`} onClick={editClick} onContextMenu={editContext} title={mode==='edit'?'点击编辑，右键更多操作':undefined}><div className="block-head">{showTitle&&<b>{b.title}</b>}{b.continuation&&<small className="continuation-label">续</small>}{mode==='edit'&&b.source_refs.length>0&&<small className={`source-tag${changed?' alert':''}`}>{changed?'来源已变化':'事实来源'}</small>}</div>{fieldKeys.length>0&&<div className="block-meta">{fieldKeys.map(k=><span key={k}><b>{labelsFor[k]||k}</b> {fields[k]}</span>)}</div>}<p className="block-copy" dangerouslySetInnerHTML={{__html:mdLite(b.content)}}/></article>}
