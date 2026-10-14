// Template descriptor plumbing: the backend registry (app/templates.py) is the
// single source of truth; these helpers turn its payload into CSS variables so
// the canvas needs no per-template stylesheets.
import type { CSSProperties } from 'react'

export type TemplateLayout = 'sidebar' | 'plain' | 'banner' | 'grid' | 'line' | 'timeline' | 'rail'
// Row of GET /api/templates.
export type TemplateDescriptor = { id:number; slug:string; name:string; description:string; layout:string; serif?:boolean; tokens:Record<string,string>; version:number|null; template_version_id:number }
// Template info embedded in resume payloads (GET /api/resumes/{id}.template).
export type TemplateInfo = { slug:string; name:string; layout:string; serif?:boolean; tokens?:Record<string,string>; template_version_id?:number; template_id?:number } | null

// Classic palette doubles as the CSS fallback in styles.css. heading/tint are
// derived in app/templates.py from accent; the values here mirror that result.
export const CLASSIC_TOKENS:Record<string,string> = { sidebar_bg:'#163b43', sidebar_fg:'#f4f7f4', sidebar_muted:'#cad9d5', sidebar_heading:'#a7c9c2', on_dark_accent:'#39b0be', heading:'#1d5f66', tint:'#e9f0f1', title:'#263f40', meta:'#5f7873', meta_label:'#527875', copy:'#4c605d', accent:'#236b74', rule:'#d5e0dc' }
export const DEFAULT_TEMPLATE:TemplateInfo = { slug:'classic', name:'经典侧栏模板', layout:'sidebar', tokens:CLASSIC_TOKENS }

const VAR_NAMES:Record<string,string> = { sidebar_bg:'--t-sidebar-bg', sidebar_fg:'--t-sidebar-fg', sidebar_muted:'--t-sidebar-muted', sidebar_heading:'--t-sidebar-heading', on_dark_accent:'--t-on-dark-accent', heading:'--t-heading', tint:'--t-tint', title:'--t-title', meta:'--t-meta', meta_label:'--t-meta-label', copy:'--t-copy', accent:'--t-accent', rule:'--t-rule' }

// Inline style mapping a template's palette onto the CSS custom properties
// consumed by .resume-paper / .resume-banner rules.
export function templateVars(template?:TemplateInfo):CSSProperties{
  const tokens={...CLASSIC_TOKENS,...(template?.tokens||{})}
  const style:Record<string,string>={}
  for(const [key,value] of Object.entries(tokens)) if(VAR_NAMES[key]) style[VAR_NAMES[key]]=value
  return style as CSSProperties
}

export const layoutLabel=(layout?:string)=>layout==='plain'?'单栏通排':layout==='banner'?'横幅单栏':layout==='grid'?'表格表单':layout==='line'?'经典线式':layout==='timeline'?'时间轴通排':layout==='rail'?'标签栏':'侧栏双栏'

// 版式的"机器可读性"取舍，供模板选择器直接标出来。依据：
// - Greenhouse 官方支持文档把 "columned layout" 与 "complex resumes with tables,
//   headers, and footers" 直接列进简历解析失败原因清单；
// - TopResume 明确说右栏内容会被解析器打乱（"cannot read that right-hand column
//   effectively"），并建议"单栏最好，左栏可用"；
// - 各来源一致要求工作经历/项目经历整宽独行，不能并排；
// - 另有一份基准测试显示"技能用网格"未导致解析失败，故表格版式的短字段并排风险
//   低于整页双栏（但仍高于单栏）。
// 结论落成三档，而不是一个"好/坏"标签——侧栏与表格是刻意的排版选择，只是要让人
// 在选择时知道代价。
export type ParsingNote = { level:'safe'|'caution'|'risky'; label:string; hint:string }
export function parsingNote(template:Pick<TemplateDescriptor,'layout'>):ParsingNote{
  if(template.layout==='sidebar') return {
    level:'caution',
    label:'双栏页',
    hint:'主栏 + 深色侧栏两列。侧栏只放联系方式、技能、成果，工作/项目经历保持在主栏整宽；部分 ATS 仍会读乱右栏，投递机器筛选用单栏模板更稳。',
  }
  if(template.layout==='grid') return {
    level:'risky',
    label:'表格',
    hint:'短栏目并排成表格行，因此能一页装下更多内容。表格与并排栏被部分 ATS 列为解析失败原因（Greenhouse 明文），适合人工阅读、打印递交或明确不跑机器筛选的场景。',
  }
  if(template.layout==='rail') return {
    level:'caution',
    label:'标签栏',
    hint:'栏目名在左侧窄栏、内容在右侧，阅读顺序仍是自上而下；但"标签列 + 内容列"的行内两列仍可能被部分解析器串行读出，机器筛选场景请优先单栏通排。',
  }
  return {
    level:'safe',
    label:'单栏',
    hint:'所有栏目整宽通排、逐条从上到下，解析顺序与阅读顺序一致，兼容性最好；代价是同样内容可能比双栏/表格模板多出一页。',
  }
}

// Miniature thumbnail for template pickers, generated from the palette: dark
// band = 侧栏/横幅底色/表头行, tinted band = 分隔线/纸面, accent bar = 时间轴线。
export function templateThumbStyle(template:TemplateDescriptor):CSSProperties{
  const t={...CLASSIC_TOKENS,...template.tokens}
  if(template.layout==='banner') return {background:`linear-gradient(${t.sidebar_bg} 0 26%, #fff 26%)`}
  if(template.layout==='plain') return {background:`linear-gradient(#fff 0 18%, ${t.rule} 18% 100%)`}
  if(template.layout==='grid') return {background:`linear-gradient(#fff 0 24%, ${t.sidebar_bg} 24% 34%, #fff 34% 58%, ${t.rule} 58% 62%, #fff 62%)`,boxShadow:`inset 0 0 0 1px ${t.rule}`}
  if(template.layout==='line') return {background:`linear-gradient(#fff 0 26%, ${t.sidebar_bg} 26% 29%, #fff 29% 55%, ${t.rule} 55% 58%, #fff 58%)`}
  if(template.layout==='rail') return {background:`linear-gradient(90deg, ${t.tint} 0 22%, #fff 22%)`}
  if(template.layout==='timeline') return {background:`linear-gradient(90deg, #fff 0 30%, ${t.accent} 30% 32%, #fff 32%)`}
  return {background:`linear-gradient(105deg, ${t.sidebar_bg} 0 30%, #fff 30%)`}
}
