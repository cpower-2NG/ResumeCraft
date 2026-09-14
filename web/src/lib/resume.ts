// Resume domain types and pure rendering logic shared by every page.
// The page-packing code mirrors render_resume_html() in app/services.py so the
// SPA preview paginates exactly like the exported A4 HTML.
import { mdLite } from './markdown'

export type CustomField = { key:string; label:string; value:string; displayable:boolean; sort_order:number }
export type Fact = { id:number; category:string; title:string; content:Record<string,string>; details:Record<string,string>; custom_fields:CustomField[]; display_fields:string[]; tags:string[]; status:string; updated_at:string; evidence_count:number }
export type Profile = { id:number; name:string; role_direction:string; core_requirements:string[]; resume_strategy:string; raw_jd:string; status:string; updated_at:string; active_resume_id?:number; opportunity_count?:number }
export type Block = { id:string; title:string; content:string; fields?:Record<string,string>; field_labels?:Record<string,string>; display_fields?:string[]; source_refs:number[]; origin:string; fragment_index?:number; continuation?:boolean }
export type Section = { id:string; title:string; visibility:boolean; blocks:Block[] }
export type Content = { sections:Section[] }
export type Resume = { id:number; display_name:string; profile_name:string; current_version:number; updated_at:string; dirty:boolean; warnings:number; status:string }
export type Pending = { id:number; resume_id:number; fact_id:number; message:string; kind:string; created_at:string; affected:{section_id:string;block_id:string}[] }
export type SearchResult = { type:'fact'|'evidence'|'profile'|'opportunity'|'resume'; id:number; title:string; subtitle:string; status:string; updated_at:string; payload:any }
export type BlockRef = { sectionId:string; blockId:string; fragmentIndex:number }
export type UpdateBlock = (sectionId:string, blockId:string, value:string, key?:'content'|'title'|'field', fieldKey?:string, fragmentIndex?:number)=>void

export const labels:Record<string,string> = { basics:'基本信息', target:'求职目标', profile:'个人简介', education:'教育经历', experience:'项目与实践', skills:'技能', awards:'成果', links:'链接与作品集' }
export const categories = ['basics','education','experience','skills','awards','links']
export const fieldLabels:Record<string,string> = { name:'姓名', phone:'电话', email:'邮箱', city:'所在地', desired_city:'目标城市', birth_date:'出生日期', age:'年龄', hometown:'籍贯', status:'身份状态', graduation:'毕业时间', availability:'到岗安排', bio:'个人简介', school:'学校', major:'专业', degree:'学历', start_date:'入学时间', end_date:'毕业时间', period:'时间', gpa:'GPA', ranking:'专业排名', achievement:'成绩与成果', courses:'相关课程', kind:'经历类型', organization:'组织/公司', role:'角色', team_size:'团队规模', context:'背景/使用场景', work:'具体工作', tools:'工具与技术', outcome:'结果', challenge:'挑战', solution:'解决方案', public_note:'公开说明', skill_category:'技能分类', proficiency:'熟练程度', issuer:'颁发方', result:'结果', note:'说明', link_type:'链接类型', url:'地址', label:'显示名称', role_direction:'岗位方向', core_requirements:'核心要求', summary:'简介' }
export const searchTypeLabels:Record<string,string> = { fact:'事实资料', evidence:'证据', profile:'岗位画像', opportunity:'招聘机会', resume:'正式简历' }
export const pendingKindLabels:Record<string,string> = { source_changed:'来源资料变化', source_recycled:'来源移入回收站' }

export const date = (v?:string) => v ? new Intl.DateTimeFormat('zh-CN',{dateStyle:'medium'}).format(new Date(v)) : '—'
export const brief = (f:Fact) => Object.values(f.details || f.content || {}).filter(Boolean).slice(0,3).join(' · ') || '尚未补充详细信息'
export const section = (content:Content,id:string):Section => content.sections.find(s=>s.id===id) || {id,title:labels[id],visibility:true,blocks:[]}
export const sourceIdOf = (b:Block) => b.id.split('--fragment-')[0]
export const factCategories = (id:string) => id === 'basics' || id === 'profile' ? ['basics'] : id === 'target' ? [] : [id]

export { mdLite }

export function factBlock(f:Fact,sid:string):Block{const d=f.details||f.content||{};const fields=Object.fromEntries(Object.entries(d).filter(([,v])=>v));if(sid==='profile')delete fields.bio;const extra=(f.custom_fields||[]).filter(x=>x.value);const field_labels=Object.fromEntries(extra.map(x=>[x.key,x.label||x.key]));extra.forEach(x=>{fields[x.key]=x.value});const standard=sid==='profile'?(d.bio?['bio']:['summary']):sid==='basics'?['phone','email','city','desired_city','hometown','status','graduation','availability']:sid==='education'?['period','major','degree','gpa','ranking']:sid==='experience'?['period','organization','role','team_size','tools']:sid==='skills'?['skill_category','proficiency']:sid==='awards'?['period','issuer','result']:['link_type','label','url'];const display_fields=standard.filter(k=>fields[k]).concat(extra.filter(x=>x.displayable).map(x=>x.key));const content=sid==='profile'?(d.bio||d.summary||''):sid==='education'?[d.achievement,d.courses].filter(Boolean).join('\n'):sid==='experience'?['context','work','outcome','challenge','solution','public_note'].map(k=>d[k]).filter(Boolean).join('\n'):sid==='skills'?(d.context||''):sid==='awards'?(d.note||''):sid==='links'?(d.note||''):'';return {id:`fact-${f.id}-${Date.now()}`,type:'fact',title:f.title,content:content||brief(f),fields,field_labels,display_fields,source_refs:[f.id],origin:'fact'} as Block}

export function splitText(value:string,max=900){if(!value)return [''];const chunks:string[]=[];for(let start=0;start<value.length;start+=max)chunks.push(value.slice(start,start+max));return chunks}
// 正文切片上限：侧栏版心只有约 44mm，切片要更短。与 services.py 的
// section_fragment_limit 保持一致。
export const fragmentLimit=(inSidebar:boolean)=>inSidebar?520:900
// 该栏目是否由侧栏承载，决定正文的切片口径。编辑续段时要按同一口径重新切片，
// 否则会切在与预览不同的位置上。
export const inSidebarStream=(layout:string|undefined,sectionId:string)=>layout==='sidebar'&&SIDE_IDS.includes(sectionId)

export const MAIN_IDS=['target','profile','experience','education','links']
// 侧栏布局里由侧栏承载的栏目。基本信息不在此列——它已经由侧栏页头（姓名 +
// 联系方式 + 简介）呈现，重复成栏目会让同一段内容在侧栏出现两次。
export const SIDE_IDS=['skills','awards']
export const ALL_IDS=['basics','target','profile','experience','education','skills','awards','links']

// —— 分页权重模型（单位：px，96dpi 下的 A4 = 1123px 高）——
// 权重即估算的渲染高度，预算即版心可用高度。与 app/services.py 的
// LAYOUT_METRICS / PAGE_BUDGET_PX 是同一张表：数值由
// `python scripts/calibrate_layout.py && node web/scripts/measure_calib.mjs`
// 从真实导出 CSS 的浏览器布局中实测得出，并按“安全一侧”取整（行高与固定成本向上
// 取、每行字符数向下取），保证估算不低于实际渲染——低估会让导出正文越过 A4 底边
// 被 overflow:hidden 裁掉。
//
// 衬线模板不需要单独一列：实测 Georgia/Times 对中文会落到 SimSun，中文字宽不变，
// 每行字符数与同布局的非衬线模板一致。
const LAYOUT_METRICS:Record<string,{header:number;header_first:number;title:number;base:number;extra:number;content_line:number;chars_per_line:number;meta:number;meta_chars:number;pair_chars_per_line:number;pair_meta_chars:number}> = {
  sidebar:  {header:47, header_first:33, title:21, base:37, extra:0, content_line:18, chars_per_line:46, meta:15, meta_chars:35, pair_chars_per_line:22, pair_meta_chars:23},
  side:     {header:22, header_first:22, title:21, base:33, extra:0, content_line:15, chars_per_line:17, meta:15, meta_chars:14, pair_chars_per_line:17, pair_meta_chars:14},
  plain:    {header:47, header_first:33, title:21, base:34, extra:0, content_line:18, chars_per_line:68, meta:15, meta_chars:70, pair_chars_per_line:32, pair_meta_chars:34},
  banner:   {header:47, header_first:33, title:21, base:34, extra:0, content_line:18, chars_per_line:68, meta:15, meta_chars:70, pair_chars_per_line:32, pair_meta_chars:34},
  grid:     {header:49, header_first:39, title:21, base:32, extra:0, content_line:18, chars_per_line:68, meta:15, meta_chars:70, pair_chars_per_line:34, pair_meta_chars:34},
  line:     {header:45, header_first:31, title:21, base:43, extra:0, content_line:18, chars_per_line:68, meta:15, meta_chars:70, pair_chars_per_line:33, pair_meta_chars:34},
  timeline: {header:47, header_first:33, title:24, base:37, extra:0, content_line:18, chars_per_line:58, meta:15, meta_chars:70, pair_chars_per_line:32, pair_meta_chars:34},
}
export const MAIN_BUDGET=1032
export const SIDE_BUDGET=1032
export const BANNER_BUDGET=927
export const GRID_BUDGET=999
export const LINE_BUDGET=1002
export const TIMELINE_BUDGET=961
const BUDGETS:Record<string,number>={sidebar:MAIN_BUDGET,side:SIDE_BUDGET,plain:961,banner:BANNER_BUDGET,grid:GRID_BUDGET,line:LINE_BUDGET,timeline:TIMELINE_BUDGET}
// 侧栏首页除了栏目，还要放侧栏页头（姓名 + 联系方式 + 简介），这部分高度必须从第一页
// 的侧栏预算里扣掉，否则侧栏首页会溢出 A4 底边被裁掉。与 services.py 的
// SIDEBAR_* 常数同一口径。
const SIDEBAR_NAME_PX=51
const SIDEBAR_FIELD_PX=19
const SIDEBAR_BIO_LINE_PX=18
const SIDEBAR_HEAD_BASE_PX=20
// 双栏收尾：短栏目两两并排（一行两个模块）。时间轴保持单列，左时间栏是它的
// 识别特征。配对只发生在相邻栏目之间以保持栏目顺序，且必须真正省下纵向空间才
// 配对——半宽折行会让正文变高，落差悬殊的栏目并排反而更费版面。
// 并排上限 = 页预算 × PAIR_MAX_SHARE，再按半栏宽度等比收紧（PAIR_REF_CHARS 为最宽
// 的半栏口径）：半栏越窄，能并排的单元就该越矮。侧栏布局的主栏只有 128mm，半栏
// 58mm，上限收到约 275px，只有短栏目会并排。常数与 app/services.py 的
// PAIRING_BY_LAYOUT/PAIR_MAX_SHARE/PAIR_REF_CHARS/PAIR_MIN_SAVING 保持一致。
const PAIRING_BY_LAYOUT:Record<string,boolean>={sidebar:true,plain:true,banner:true,grid:true,line:true,timeline:false}
const PAIR_MAX_SHARE=0.4
const PAIR_REF_CHARS=33
const PAIR_MIN_SAVING=20
type Metrics=typeof LAYOUT_METRICS[string]
// 当前布局允许的并排单元高度上限（半栏越窄上限越低）。
const pairHeightCap=(layout:string,budget:number)=>{
  const style=LAYOUT_METRICS[layout]||LAYOUT_METRICS.sidebar
  return Math.min(style.pair_chars_per_line/PAIR_REF_CHARS,1)*budget*PAIR_MAX_SHARE
}
// 侧栏页头（姓名 + 联系方式 + 简介）的估算高度，与 services.py 的
// sidebar_head_height 同一公式：姓名行 + 每个联系字段一行 + 简介行数。
export const sidebarHeadHeight=(basic:Block|undefined):number=>{
  const style=LAYOUT_METRICS.side
  const fields=basic?.fields||{}
  const displayed=basic?.display_fields||Object.keys(fields)
  let rows=0
  for(const key of displayed){
    const value=fields[key]
    if(!value)continue
    rows+=Math.max(1,Math.ceil((String(fieldLabels[key]??key)+String(value)).length/style.meta_chars))
  }
  const bioLines=contentLineCount(basic?.content||'',style.chars_per_line)
  return SIDEBAR_HEAD_BASE_PX+SIDEBAR_NAME_PX+rows*SIDEBAR_FIELD_PX+bioLines*SIDEBAR_BIO_LINE_PX
}
// Section order and packing budget per template layout; mirrors render_resume_html().
// 侧栏布局：基本信息由侧栏页头（姓名 + 联系方式 + 简介）呈现，不再重复成栏目；
// 技能与成果在侧栏，主栏承载其余五栏。其余布局的姓名与联系方式由页头呈现。
export const layoutMainIds=(layout:string)=>layout==='sidebar'?MAIN_IDS:ALL_IDS.filter(id=>id!=='basics')
// 按布局直接查表：曾用一串条件挑预算，plain 没有分支而落到 sidebar 的预算上，
// 凭空多出近百像素，导出正文因此越过 A4 底边被裁掉。
export const layoutBudget=(layout:string)=>BUDGETS[layout]??MAIN_BUDGET


export type FlowUnit={kind:'flow';section:Section;block:Block;continued?:boolean}
export type PairUnit={kind:'pair';sectionA:Section;blocksA:Block[];sectionB:Section;blocksB:Block[];weight:number}
export type Unit=FlowUnit|PairUnit

const emptyBlock=(sid:string):Block=>({id:`${sid}--empty`,title:'',content:'',source_refs:[],origin:'empty'})
// 正文行数：末尾换行先去掉——render_markdown 会把它变成行尾 <br>，而行尾 <br> 不
// 产生新的行盒；按“多一行”计价会让每条内容凭空高一整行（真实正文大多以换行结尾），
// 页数因此被高估、页面被过早切断。与 services.py 的 content_line_count 同一口径。
const contentLineCount=(content:string,charsPerLine:number)=>{
  const text=String(content||'').replace(/\n+$/,'')
  if(!text)return 0
  return text.split('\n').reduce((s,seg)=>s+Math.max(1,Math.ceil(seg.length/charsPerLine)),0)
}
const metaFieldLines=(b:Block,side:boolean,charsPerLine:number)=>{
  const fields=b.fields||{}
  const displayed=(b.display_fields||Object.keys(fields)).filter(k=>fields[k])
  if(!displayed.length)return 0
  if(side)return displayed.reduce((s,k)=>s+Math.max(1,Math.ceil((String(fieldLabels[k]??k)+String(fields[k])).length/charsPerLine)),0)
  const total=displayed.reduce((s,k)=>s+(String(fieldLabels[k]??k)+String(fields[k])).length,0)
  return Math.max(1,Math.ceil(total/charsPerLine))
}
// 与 services.py 的 section_item_weight 同一公式：固定成本 + 正文行数 × 行高
// + 元信息行数 × 行高，否则预览分页与导出断点会错位。
// 该条目是否渲染自己的标题行（与栏目标题同名时由栏目承载，不再重复渲染），
// 以及条目标题行的成本——与 services.py 的 block_has_title/section_item_weight 同口径。
const blockHasTitle=(block:Block,sid:string)=>{
  const title=String(block.title||'')
  return !!title&&title!==(labels[sid]||sid)
}
const itemWeight=(block:Block,style:Metrics,sid:string)=>{
  const weight=style.base+style.extra+contentLineCount(block.content,style.chars_per_line)*style.content_line+metaFieldLines(block,false,style.meta_chars)*style.meta
  return weight-(blockHasTitle(block,sid)?0:style.title)
}

// 把栏目切成页面单元并分页：flow = 某栏目的一个条目（栏目标题行按页计一次），
// pair = 相邻两个短栏目并排成一行两个模块。与 render_resume_html() 的
// stream_pages 逐项镜像，预览分页与导出断点保持一致。
//
// 配对以栏目顺序为准，只并排相邻栏目，因此不会打乱栏目次序；并且只在真正省下
// 纵向空间时成立。pair 是原子单元，放不下当前页剩余空间时退化回两个 flow 单元，
// 避免为等一整对而空出大半页、形成只有一两行的尾页。
//
// inSidebar 决定用哪一列的口径计价——侧栏版心只有约 44mm，每行字数与条目固定成本
// 都和主栏差一个量级，用错口径会让整页的估算失真。firstPageHead 是首页额外的固定
// 占用（侧栏页头），只从第一页扣。
export function streamItems(content:Content,ids:string[],budget:number,inSidebar:boolean,layout:string='',firstPageHead=0):Unit[][]{
  const styleFor=()=>LAYOUT_METRICS[inSidebar?'side':layout]||LAYOUT_METRICS.side
  const sectionOf=(id:string)=>section(content,id)
  const blocksOf=(sid:string)=>sectionOf(sid).blocks
  const fragmentFlow=(sid:string,blocks:Block[]):Unit[]=>{
    const style=styleFor()
    const limit=fragmentLimit(inSidebar)
    const out:Unit[]=[]
    if(!blocks.length){
      // 空栏目保留标题行（选择/添加来源的点击入口）。
      out.push({kind:'flow',section:sectionOf(sid),block:emptyBlock(sid)})
      return out
    }
    for(const block of blocks){
      const chunks=splitText(block.content||'',limit)
      // 续段只带正文：重复标题与元信息会让同一个条目看起来出现两次。
      chunks.forEach((chunk,index)=>out.push({kind:'flow',section:sectionOf(sid),block:{...block,title:index?'':block.title,id:index?`${block.id}--fragment-${index}`:block.id,content:chunk,fields:index===0?block.fields:{},display_fields:index===0?block.display_fields:[],fragment_index:index,continuation:index>0}}))
    }
    return out
  }
  // 整栏估算高度：栏目标题行 + 各条目（固定成本 + 正文行 + 元信息行）。
  const columnHeight=(sid:string,charsPerLine:number,metaChars:number)=>{
    const style=styleFor()
    const blocks=blocksOf(sid)
    let total=style.header
    if(!blocks.length)return total+style.base
    for(const block of blocks){
      total+=style.base+style.extra+contentLineCount(block.content,charsPerLine)*style.content_line+metaFieldLines(block,false,metaChars)*style.meta
      if(!blockHasTitle(block,sid))total-=style.title
    }
    return total
  }
  // 相邻两栏并排的估算高度；不值得配对时返回 null（保持整宽通排）。
  const pairHeight=(sid:string,sid2:string):number|null=>{
    const style=LAYOUT_METRICS[layout]||LAYOUT_METRICS.sidebar
    const stacked=columnHeight(sid,style.chars_per_line,style.meta_chars)+columnHeight(sid2,style.chars_per_line,style.meta_chars)
    const paired=Math.max(
      columnHeight(sid,style.pair_chars_per_line,style.pair_meta_chars),
      columnHeight(sid2,style.pair_chars_per_line,style.pair_meta_chars),
    )
    if(paired>pairHeightCap(layout,budget)||stacked-paired<PAIR_MIN_SAVING)return null
    return paired
  }

  const units:Unit[]=[]
  const pairable=!inSidebar&&(PAIRING_BY_LAYOUT[layout]??false)
  let index=0
  while(index<ids.length){
    const sid=ids[index]
    if(pairable&&index+1<ids.length){
      const sid2=ids[index+1]
      const weight=pairHeight(sid,sid2)
      if(weight!==null){
        units.push({kind:'pair',sectionA:sectionOf(sid),blocksA:blocksOf(sid),sectionB:sectionOf(sid2),blocksB:blocksOf(sid2),weight})
        index+=2
        continue
      }
    }
    units.push(...fragmentFlow(sid,blocksOf(sid)))
    index+=1
  }

  const pages:Unit[][]=[];let current:Unit[]=[];let size=0;let currentId:string|null=null
  const pageBudget=()=>budget-(pages.length?0:firstPageHead)
  let cursor=0
  while(cursor<units.length){
    const unit=units[cursor]
    if(unit.kind==='pair'){
      if(!current.length||size+unit.weight<=pageBudget()){current.push(unit);size+=unit.weight;cursor+=1;continue}
      // 放不下当前页剩余的这一点空间：退化成两个整宽栏目接着排，把本页填满。
      units.splice(cursor,1,...fragmentFlow(unit.sectionA.id,unit.blocksA),...fragmentFlow(unit.sectionB.id,unit.blocksB))
      continue
    }
    const style=styleFor()
    const w=itemWeight(unit.block,style,unit.section.id)
    let header=unit.section.id!==currentId?style.header:0
    if(current.length&&size+w+header>pageBudget()){pages.push(current);current=[];size=0;currentId=null;header=style.header_first}
    if(header){size+=header;currentId=unit.section.id}
    unit.continued=false
    current.push(unit);size+=w
    cursor+=1
  }
  if(current.length||!pages.length)pages.push(current)
  const seen=new Set<string>()
  for(const page of pages){
    const local=new Set<string>()
    for(const unit of page){
      if(unit.kind==='flow'){unit.continued=seen.has(unit.section.id);local.add(unit.section.id)}
    }
    for(const key of local)seen.add(key)
  }
  return pages
}
