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
export const fragmentLimit=(sid:string)=>['basics','skills','awards'].includes(sid)?520:900

export const MAIN_IDS=['target','profile','experience','education','links']
export const SIDE_IDS=['basics','skills','awards']
export const ALL_IDS=['basics','target','profile','experience','education','skills','awards','links']

// —— 分页权重模型（单位：px，96dpi 下 A4 = 1122px 高）——
// 与 app/services.py 的 LAYOUT_METRICS / PAGE_BUDGET_PX 保持同一公式与数值：
// 权重即估算渲染高度，预算即页面可用高度。常数由导出 CSS 反推（正文 9pt×1.6、
// 条目 h3 + 5mm 边距、栏目标题 12pt + 7mm 上边距、页内首栏目 margin 归零）。
const LAYOUT_METRICS:Record<string,{header:number;header_first:number;base:number;extra:number;content_line:number;chars_per_line:number;meta:number;meta_chars:number}> = {
  sidebar:  {header:52, header_first:31, base:38, extra:0,  content_line:19, chars_per_line:40, meta:14, meta_chars:45},
  side:     {header:46, header_first:46, base:30, extra:0,  content_line:15, chars_per_line:15, meta:14, meta_chars:15},
  plain:    {header:52, header_first:31, base:38, extra:0,  content_line:19, chars_per_line:56, meta:14, meta_chars:65},
  banner:   {header:52, header_first:31, base:38, extra:0,  content_line:19, chars_per_line:56, meta:14, meta_chars:65},
  grid:     {header:42, header_first:29, base:30, extra:0,  content_line:19, chars_per_line:56, meta:14, meta_chars:65},
  line:     {header:52, header_first:31, base:52, extra:0,  content_line:19, chars_per_line:56, meta:14, meta_chars:65},
  timeline: {header:52, header_first:31, base:38, extra:0,  content_line:19, chars_per_line:56, meta:14, meta_chars:65},
}
export const MAIN_BUDGET=1015
export const SIDE_BUDGET=1015
export const BANNER_BUDGET=915
export const GRID_BUDGET=950
export const LINE_BUDGET=940
export const TIMELINE_BUDGET=895
const MAIN_META_CHARS_PER_LINE=60
const SIDE_META_CHARS_PER_LINE=15
// Section order and packing budget per template layout; mirrors render_resume_html().
// 侧栏布局：基本信息/技能/成果在侧栏，主栏五栏目；其余布局的姓名与联系方式
// 由页头呈现，正文从求职目标开始。
export const layoutMainIds=(layout:string)=>layout==='sidebar'?MAIN_IDS:ALL_IDS.filter(id=>id!=='basics')
export const layoutBudget=(layout:string)=>layout==='banner'?BANNER_BUDGET:layout==='grid'?GRID_BUDGET:layout==='line'?LINE_BUDGET:layout==='timeline'?TIMELINE_BUDGET:MAIN_BUDGET

export type Item={section:Section;block:Block;continued:boolean}
const emptyBlock=(sid:string):Block=>({id:`${sid}--empty`,title:'',content:'',source_refs:[],origin:'empty'})
const contentLineCount=(content:string,charsPerLine:number)=>{
  const text=String(content||'')
  if(!text)return 0
  return text.split('\n').reduce((s,seg)=>s+Math.max(1,Math.ceil(seg.length/charsPerLine)),0)
}
const metaFieldLines=(b:Block,side:boolean,layout:string)=>{
  const fields=b.fields||{}
  const displayed=(b.display_fields||Object.keys(fields)).filter(k=>fields[k])
  if(!displayed.length)return 0
  if(side){
    const chars=LAYOUT_METRICS.side.meta_chars
    return displayed.reduce((s,k)=>s+Math.max(1,Math.ceil((String(fieldLabels[k]??k)+String(fields[k])).length/chars)),0)
  }
  const chars=(LAYOUT_METRICS[layout]||LAYOUT_METRICS.plain).meta_chars
  const total=displayed.reduce((s,k)=>s+(String(fieldLabels[k]??k)+String(fields[k])).length,0)
  return Math.max(1,Math.ceil(total/chars))
}
const itemWeight=(it:Item,side:boolean,layout:string)=>{
  const style=LAYOUT_METRICS[side?'side':layout]||LAYOUT_METRICS.sidebar
  // 与 services.py 的 section_item_weight 同一公式：固定成本 + 正文行数 × 行高
  // + 元信息行数 × 行高，否则预览分页与导出断点会错位。
  return style.base+style.extra+contentLineCount(it.block.content,style.chars_per_line)*style.content_line+metaFieldLines(it.block,side,layout)*style.meta
}

// Fragments blocks, packs them into fixed-size pages, and marks headings that
// continue from an earlier page. Mirrors render_resume_html() in app/services.py
// so preview page breaks match the exported A4 HTML.
export function streamItems(content:Content,ids:string[],budget:number,side:boolean,layout:string=''):Item[][]{
  const items:Item[]=[]
  for(const id of ids){
    const original=section(content,id)
    if(!original.blocks.length){items.push({section:original,block:emptyBlock(id),continued:false});continue}
    const limit=fragmentLimit(id)
    for(const block of original.blocks){
      const chunks=splitText(block.content||'',limit)
      chunks.forEach((chunk,index)=>items.push({section:original,block:{...block,id:index?`${block.id}--fragment-${index}`:block.id,content:chunk,fields:index===0?block.fields:{},display_fields:index===0?block.display_fields:[],fragment_index:index,continuation:index>0},continued:false}))
    }
  }
  const headerWeightFor=(sid:string)=>(LAYOUT_METRICS[side?'side':layout]||LAYOUT_METRICS.sidebar).header
  const headerFirst=(sid:string)=>(LAYOUT_METRICS[side?'side':layout]||LAYOUT_METRICS.sidebar).header_first
  const pages:Item[][]=[];let current:Item[]=[];let size=0;let currentId:string|null=null
  for(const it of items){
    // 栏目在每个页面上计一次标题行成本；换页后首个栏目 margin 归零。
    const w=itemWeight(it,side,layout)
    let header=it.section.id!==currentId?headerWeightFor(it.section.id):0
    if(current.length&&size+w+header>budget){pages.push(current);current=[];size=0;currentId=null;header=headerFirst(it.section.id)}
    if(header){size+=header;currentId=it.section.id}
    current.push(it);size+=w
  }
  if(current.length||!pages.length)pages.push(current)
  const seen=new Set<string>()
  for(const page of pages){const local=new Set<string>();for(const it of page){it.continued=seen.has(it.section.id);local.add(it.section.id)}for(const key of local)seen.add(key)}
  return pages
}
