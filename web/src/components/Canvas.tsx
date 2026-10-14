import type { MouseEvent as ReactMouseEvent, ReactNode } from 'react'
import type { Block, Content, FlowUnit, Section, Unit } from '../lib/resume'
import { awardsTableRows, factCategories, hydrateContent, inSidebarStream, labels, layoutBudget, layoutMainIds, mdLite, metaValues, renderableIds, section, SIDE_IDS, SIDE_BUDGET, sidebarHeadHeight, skillGroups, sourceIdOf, streamItems, streamPages, targetBand } from '../lib/resume'
import { templateVars, type TemplateInfo } from '../lib/templates'

type CanvasShared={mode:'select'|'edit';select?:(s:string)=>void;changed?:string[];addFact?:(s:string)=>void;onEdit?:(target:{sectionId:string;blockId:string;fragmentIndex:number})=>void;onContext?:(target:{sectionId:string;blockId:string;fragmentIndex:number},x:number,y:number)=>void;onToggleSection?:(s:string,visible:boolean)=>void;layout?:string}

// Live A4 canvas: renders the same section/block stream as the export renderer,
// themed by the template descriptor through CSS variables (no per-template CSS).
export function Canvas({content,mode,template,select,changed=[],addFact,onEdit,onContext,onToggleSection}:{content:Content;mode:'select'|'edit';template?:TemplateInfo;select?:(s:string)=>void;changed?:string[];addFact?:(s:string)=>void;onEdit?:(target:{sectionId:string;blockId:string;fragmentIndex:number})=>void;onContext?:(target:{sectionId:string;blockId:string;fragmentIndex:number},x:number,y:number)=>void;onToggleSection?:(s:string,visible:boolean)=>void}){
  const layout=template?.layout||'sidebar'
  const banner=layout==='banner'
  const grid=layout==='grid'
  const rail=layout==='rail'
  const single=layout!=='sidebar'
  // 字段兜底回收：历史数据可能把 meta/时间压平进正文（与导出端 hydrate_content 同一
  // 规则），预览必须先回收再编排，两端的断点与条目形态才一致。
  const hydrated=hydrateContent(content)
  // 画布要保留没有内容的栏目：它们是"点击选择资料"的入口，临时简历初始就是靠这些
  // 空栏目名告诉用户简历有哪几栏（导出端相反——成品纸面上不留只有标题的空条，
  // 由 app/services.py 的 section_has_content 剔除）。
  // 被关掉的栏目（visibility=false）两边都不排，且不占版面预算，预览断页才与导出一致。
  // 求职意向横带出现在第一页主栏最前（全部版式统一），高度从首页预算里扣除。
  const band=targetBand(hydrated,layout)
  const {pages:mainPages,compact}=streamPages(hydrated,renderableIds(hydrated,layoutMainIds(layout)),layoutBudget(layout),false,layout,band?.height||0)
  const sidePages=single?[]:streamItems(hydrated,renderableIds(hydrated,SIDE_IDS),SIDE_BUDGET,true,'sidebar',sidebarHeadHeight(section(hydrated,'basics').blocks[0]))
  const count=Math.max(mainPages.length,sidePages.length,1)
  const shared:CanvasShared={mode,select,changed,addFact,onEdit,onContext,onToggleSection,layout}
  const basicBlock=section(hydrated,'basics').blocks[0]
  const bannerName=basicBlock?.title||'简历'
  // 所有单栏布局都用页头呈现姓名与联系方式；侧栏布局的基本信息在侧栏。
  const headClass=banner?'resume-banner':grid?'grid-head':rail?'rail-head':'line-head'
  const headSlimClass=banner?'banner-slim':grid?'grid-head-slim':rail?'rail-head-slim':'line-head-slim'
  const bandNode=band&&<div className="intent-band"><b>求职意向</b><span>{band.primary}</span>{band.secondary&&<em>{band.secondary}</em>}</div>
  return <section className={`resume-stage ${mode==='edit'?'edit-mode':'select-mode'}`} style={templateVars(template)} data-template={template?.slug||'classic'}>
    {Array.from({length:count},(_,i)=><Paper key={i} number={i+1} layout={layout} serif={template?.serif} compact={compact} sidebar={!single&&<>
      {i===0&&<SidebarHead block={basicBlock} fallback={bannerName}/>}
      {sidePages[i]?.length?<Sidebar items={sidePages[i]||[]} shared={shared}/>:<div className="continuation-mark">RESUME / {String(i+1).padStart(2,'0')}</div>}
    </>}>
      {single?(i===0
        ?<header className={headClass}><h1>{bannerName}</h1><div className="banner-meta">{bannerFields(basicBlock)}</div></header>
        :<header className={`${headClass} ${headSlimClass}`}><h1>{bannerName}</h1></header>)
        :null}
      <main className="resume-main"><div className="main-sections">{i===0?bandNode:null}{renderPageUnits(mainPages[i]||[],shared)}</div></main>
    </Paper>)}
  </section>
}

// 元信息行 = 值 · 值 · 值（无标签、去重）；分隔点由 CSS 的 ::before 补上。
function bannerFields(b:Block|undefined){if(!b)return null;return <>{metaValues(b).map((v,i)=><span className="meta" key={i}>{v}</span>)}</>}

// 侧栏页头：姓名 + 联系方式 + 简介。侧栏布局的基本信息由它呈现（导出渲染器的
// sidebar_head 是同构的），栏目流里不再重复一个"基本信息"栏目。分页估算本来就
// 从侧栏首页预算里扣掉了这块高度（sidebarHeadHeight），此前画布却没画它。
function SidebarHead({block,fallback}:{block:Block|undefined;fallback:string}){
  const content=(block?.content||'').trim()
  return <>
    <h1>{block?.title||fallback}</h1>
    {block&&<div className="side-meta">{bannerFields(block)}</div>}
    {content&&<p className="side-copy">{content}</p>}
  </>
}

// 页面单元渲染：flow 单元按连续栏目聚合，pair 单元渲染为一行两栏。
function renderPageUnits(units:Unit[],shared:CanvasShared):ReactNode{
  const out:ReactNode[]=[]
  let flow:FlowUnit[]=[]
  const flush=(key:string)=>{
    if(flow.length){
      out.push(<FlowGroups key={`f${key}`} items={flow} shared={shared}/>)
      flow=[]
    }
  }
  units.forEach((unit,i)=>{
    if(unit.kind==='pair'){
      flush(String(i))
      out.push(<div className="pair" key={`p${i}`}>
        <SectionGroup section={unit.sectionA} blocks={unit.blocksA} continued={false} {...shared}/>
        <SectionGroup section={unit.sectionB} blocks={unit.blocksB} continued={false} {...shared}/>
      </div>)
    }else{
      flow.push(unit)
    }
  })
  flush('end')
  return <>{out}</>
}

function FlowGroups({items,shared}:{items:FlowUnit[];shared:CanvasShared}){
  const groups:{section:Section;blocks:Block[];continued?:boolean}[]=[]
  for(const it of items){
    const last=groups[groups.length-1]
    if(last&&last.section.id===it.section.id){if(!it.block.id.endsWith('--empty'))last.blocks.push(it.block)}
    else groups.push({section:it.section,blocks:it.block.id.endsWith('--empty')?[]:[it.block],continued:it.continued})
  }
  if(!groups.length)groups.push({section:emptySection('target'),blocks:[],continued:false})
  return <>{groups.map((g,index)=><SectionGroup key={`${g.section.id}-${index}`} section={g.section} blocks={g.blocks} continued={g.continued} {...shared}/>)}</>
}

function Paper({number,layout,serif,compact,sidebar,children}:{number:number;layout:string;serif?:boolean;compact:boolean;sidebar:ReactNode;children:ReactNode}){
  const single=layout!=='sidebar'
  const variant=layout==='grid'||layout==='line'||layout==='timeline'||layout==='rail'?` ${layout}`:''
  return <article className={`resume-paper${single?' plain':''}${layout==='banner'?' banner':''}${variant}${serif?' serif':''}${compact?' compact':''}`} id={`resume-page-${number}`} data-page={number}>{single?children:<><aside className="resume-sidebar">{sidebar}</aside>{children}</>}</article>
}

function Sidebar({items,shared}:{items:Unit[];shared:CanvasShared}){
  // 侧栏流永远只有 flow 单元（侧栏不参与双栏配对）。
  return <div className="sidebar-content"><FlowGroups items={items.filter((u):u is FlowUnit=>u.kind==='flow')} shared={shared}/></div>
}

function emptySection(id:string):Section{return {id,title:labels[id],visibility:true,blocks:[]}}


function SectionGroup({section:s,blocks,continued=false,mode,select,changed,addFact,layout,onEdit,onContext,onToggleSection}:{section:Section;blocks:Block[];continued?:boolean}&CanvasShared){
  if(!s.visibility)return null
  const canPick=factCategories(s.id).length>0
  // 由布局与栏目 id 推出"这一栏排在深色侧栏里"，而不是靠调用方传参：此前 FlowGroups
  // 忘了把 sidebar 传下去，侧栏里的栏目就少了 sidebar-section 类，于是深色底上照白纸
  // 配色排字——栏目名、条目标题、正文、字段值全都读不出来。
  const sidebar=inSidebarStream(layout,s.id)
  // 编辑态每栏给一个"隐藏"按钮：栏目可以整栏关掉（写进内容的 visibility，随版本保存，
  // 导出端同样不排）。关掉之后靠画布上方的"已隐藏栏目"条恢复，否则就再也点不到了。
  // 两个按钮放进 .title-actions 横排：标题行的绝对定位容器只认直接子按钮，不这样包
  // 两个按钮会叠在同一位置，后一个挡住前一个的点击。
  const actions=mode==='edit'&&(onToggleSection||canPick)
    ? <span className="title-actions">
        {onToggleSection&&<button className="mini-button hide-button" title="本栏目不排进简历，随版本保存，可随时恢复" onClick={e=>{e.stopPropagation();onToggleSection(s.id,false)}}>隐藏本栏</button>}
        {canPick&&<button className="mini-button" onClick={e=>{e.stopPropagation();addFact?.(s.id)}}>添加来源</button>}
      </span>
    : null
  // 空栏目：画布上显示为一条"点击选择资料"的占位，导出端不会渲染这些栏目。
  if(!blocks.length) return <section className={`resume-section empty-section ${sidebar?'sidebar-section':''}`} onClick={()=>mode==='select'&&canPick&&select?.(s.id)}>
    <div className="template-section-title"><b>{s.title}</b>{actions}</div>
    {canPick&&<p className="empty-hint">{mode==='select'?'点击选择要放进本栏目的资料':'本栏目还没有内容，点击条目区添加来源'}</p>}
  </section>
  // 技能按分类分组、成果排三列表格——与导出渲染器（section_body/fragment_flow）同一套
  // 形态：并排列与整宽通排、预览与导出必须一致，否则并排的实际高度会超出估算权重。
  // 分组行/表格行是派生视图，不在画布上逐条编辑（字段在资料库或条目编辑器里改）。
  let view:ReactNode
  if(s.id==='skills'&&skillGroups(blocks).length){
    view=<>{skillGroups(blocks).map(([category,line])=><BlockView key={`g-${category}`} section={s} block={{id:`${s.id}--group-${category}`,title:'',content:`**${category}**：${line}`,fields:{},display_fields:[],source_refs:[],origin:'skill-group'}} mode={mode} changed={false} sidebar={sidebar} layout={layout} onEdit={onEdit} onContext={onContext}/>)}</>
  }else if(s.id==='awards'&&awardsTableRows(blocks).length){
    view=<BlockView section={s} block={{id:`${s.id}--table`,title:'',content:'',fields:{},display_fields:[],source_refs:[],origin:'awards-table',table_rows:awardsTableRows(blocks)}} mode={mode} changed={false} sidebar={sidebar} layout={layout} onEdit={onEdit} onContext={onContext}/>
  }else{
    view=<>{blocks.map(b=><BlockView key={b.id} section={s} block={b} mode={mode} changed={(changed||[]).includes(`${s.id}:${sourceIdOf(b)}`)} sidebar={sidebar} layout={layout} onEdit={onEdit} onContext={onContext}/>)}</>
  }
  return <section className={`resume-section ${sidebar?'sidebar-section':''} ${mode==='select'&&canPick?'selection-ready':''}`} onClick={()=>mode==='select'&&canPick&&select?.(s.id)}>
    <div className="template-section-title"><b>{s.title}{continued&&<span className="continued-mark">（续）</span>}</b>{actions}</div>
    {view}
  </section>
}

function BlockView({section:s,block:b,mode,changed,sidebar,layout,onEdit,onContext}:{section:Section;block:Block;mode:'select'|'edit';changed:boolean;sidebar:boolean;layout?:string}&Pick<CanvasShared,'onEdit'|'onContext'>){
  const timeline=layout==='timeline'
  const sourceId=sourceIdOf(b)
  const editClick=(e:ReactMouseEvent)=>{if(mode!=='edit')return;e.stopPropagation();onEdit?.({sectionId:s.id,blockId:sourceId,fragmentIndex:b.fragment_index??0})}
  const editContext=(e:ReactMouseEvent)=>{if(mode!=='edit')return;e.preventDefault();e.stopPropagation();onContext?.({sectionId:s.id,blockId:sourceId,fragmentIndex:b.fragment_index??0},e.clientX,e.clientY)}
  // 成果三列表格（与导出渲染器的 awards-table 同构）。
  if(b.origin==='awards-table'&&b.table_rows)return <article className={`resume-block ${mode==='edit'?'editable-block':''}`} data-block-key={`${s.id}:${sourceId}`} onClick={editClick} onContextMenu={editContext}>
    <table className="awards-table"><thead><tr><th>时间</th><th>奖项 / 赛事</th><th>成绩（颁奖单位）</th></tr></thead>
      <tbody>{b.table_rows.map((row,i)=><tr key={i}><td className="awards-time">{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td></tr>)}</tbody></table>
  </article>
  const fields=b.fields||{}
  // 时间轴布局把时间放进左栏时间列；其余布局的时间右对齐到条目标题行行尾。
  const period=fields['period']&&(b.display_fields||Object.keys(fields)).includes('period')?fields['period']:''
  const metaList=metaValues(b,['period'])
  const showTitle=!!b.title&&b.title!==s.title
  const body=<>
    <div className="block-head">{showTitle&&<b>{b.title}</b>}{!timeline&&period&&<span className="entry-period">{period}</span>}{b.continuation&&<small className="continuation-label">续</small>}{mode==='edit'&&b.source_refs.length>0&&<small className={`source-tag${changed?' alert':''}`}>{changed?'来源已变化':'事实来源'}</small>}</div>
    {metaList.length>0&&<div className="block-meta">{metaList.map((v,i)=><span className="meta" key={i}>{v}</span>)}</div>}
    <p className="block-copy" dangerouslySetInnerHTML={{__html:mdLite(b.content)}}/>
  </>
  return <article className={`resume-block ${changed?'changed-block':''} ${b.continuation?'continuation-block':''} ${mode==='edit'?'editable-block':''}`} data-block-key={`${s.id}:${sourceId}`} onClick={editClick} onContextMenu={editContext} title={mode==='edit'?'点击编辑，右键更多操作':undefined}>{timeline?<><span className="t-time">{period}</span><div className="t-body">{body}</div></>:body}</article>
}
