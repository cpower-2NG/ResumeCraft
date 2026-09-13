import type { Content } from './resume'

// Sample facts used only by template previews (template library page and the
// creation-time template gallery): one compact entry per section so every
// template shows its real layout, colours and typography.
export const SAMPLE_CONTENT:Content={sections:[
  {id:'basics',title:'基本信息',visibility:true,blocks:[{id:'sample-basics',title:'陈晓萌',content:'',fields:{phone:'138 0000 0000',email:'chenxiaomeng@example.com',city:'上海',desired_city:'上海',status:'应届毕业生',graduation:'2026年6月'},display_fields:['phone','email','city','desired_city','status','graduation'],source_refs:[],origin:'fact'}]},
  {id:'target',title:'求职目标',visibility:true,blocks:[{id:'sample-target',title:'机器人数据采集工程师',content:'突出数据采集流水线与标注质量管理的工程实践，强调跨团队协作。',fields:{role_direction:'机器人 · 数据工程'},display_fields:['role_direction'],source_refs:[],origin:'profile'}]},
  {id:'profile',title:'个人简介',visibility:true,blocks:[{id:'sample-profile',title:'个人简介',content:'三年机器人数据采集与标注经验，熟悉采集规范制定、质量抽检与交付复盘。',fields:{},display_fields:[],source_refs:[],origin:'fact'}]},
  {id:'experience',title:'项目与实践',visibility:true,blocks:[
    {id:'sample-exp1',title:'越疆 X-Trainer 数据采集项目',content:'搭建 12 台机械臂的采集流水线，制定场景脚本与异常回传机制，累计交付 4.2 万条有效轨迹。',fields:{period:'2024.03 – 2025.06',organization:'智能机器人实验室',role:'数据采集负责人'},display_fields:['period','organization','role'],source_refs:[],origin:'fact'},
    {id:'sample-exp2',title:'标注质量管理专项',content:'设计三级抽检流程，把标注一致率从 86% 提升到 97%，沉淀质量手册并被两个团队复用。',fields:{period:'2023.09 – 2024.02',role:'质量组长'},display_fields:['period','role'],source_refs:[],origin:'fact'}]},
  {id:'education',title:'教育经历',visibility:true,blocks:[{id:'sample-edu',title:'华东理工大学 · 自动化',content:'主修控制理论与机器人学，毕业设计方向为遥操作数据合成。',fields:{period:'2022.09 – 2026.06',degree:'本科',gpa:'3.7/4.0'},display_fields:['period','degree','gpa'],source_refs:[],origin:'fact'}]},
  {id:'skills',title:'技能',visibility:true,blocks:[
    {id:'sample-skill1',title:'数据工具链',content:'ROS2 采集节点、标注平台管理、Python 数据清洗脚本。',fields:{skill_category:'工程工具',proficiency:'熟练'},display_fields:['skill_category','proficiency'],source_refs:[],origin:'fact'},
    {id:'sample-skill2',title:'质量管理',content:'抽检设计、一致性度量、标注规范撰写。',fields:{skill_category:'方法论',proficiency:'熟练'},display_fields:['skill_category','proficiency'],source_refs:[],origin:'fact'}]},
  {id:'awards',title:'成果',visibility:true,blocks:[{id:'sample-award',title:'校级优秀毕业设计',content:'遥操作数据合成方向，评级 A。',fields:{period:'2026.06',issuer:'华东理工大学'},display_fields:['period','issuer'],source_refs:[],origin:'fact'}]},
  {id:'links',title:'链接与作品集',visibility:true,blocks:[{id:'sample-link',title:'个人作品集',content:'采集规范、质量手册与项目复盘节选。',fields:{link_type:'作品集',url:'https://example.com/portfolio',label:'example.com/portfolio'},display_fields:['link_type','label'],source_refs:[],origin:'fact'}]},
]}
