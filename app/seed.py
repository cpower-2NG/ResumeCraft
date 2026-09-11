import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Award, Education, Experience, JobTarget, Profile, ResumeTemplate, Skill


ROOT = Path(__file__).resolve().parent.parent
SOURCE = "个人经历信息收集表.md"


def tags(*items: str) -> str:
    return json.dumps(list(items), ensure_ascii=False)


def seed_database(db: Session, template_content: str) -> bool:
    if db.scalar(select(Profile.id).limit(1)):
        return False

    db.add(Profile(
        name="许榕鑫", city="深圳", desired_city="深圳", status="在读学生",
        graduation="2028", availability="每周可实习 5 天；最长可连续实习时间不限",
        bio="踏实肯干，善于分析问题，学习能力强。从算法竞赛转向具身智能，能够耐心完成物理设备联调与工程验证。",
        source_ref=SOURCE,
    ))
    db.add(Education(
        school="深圳技术大学", major="数据科学与大数据技术", degree="本科", period="2024 - 2028",
        achievement="GPA 3.7/4.5；专业排名 9/153",
        courses="具身智能系统概论、ROS 系统与编程、开源鸿蒙设备开发、具身智能体开发、数据结构、操作系统",
        tags=tags("具身智能", "ROS2", "数据科学", "算法"), source_ref=SOURCE,
    ))

    experiences = [
        dict(title="越疆 X-Trainer 竞赛与优必选人形机器人挑战赛", kind="竞赛", period="2026.05 - 至今", organization="实验室小组", role="主要贡献者", context="围绕包裹分拣、流水线履带分拣等工业任务，完成数据采集、模型训练、仿真测试与部署测试。", work="使用 VR 头显和主从机械臂操作杆采集机器人运动数据，分析模型表现瓶颈并提出数据处理与任务策略改进。", tools="Python、Linux、Isaac Sim、ACT、Diffusion", outcome="包裹分拣任务可完成约 60% - 70%；越疆 X-Trainer 省三等奖、优必选挑战赛第 20 名。", challenge="工业任务复杂，适合人类的执行策略不一定适合机器人；模型存在训练集过拟合。", solution="通过视频抽帧处理训练数据，结合任务场景分析较优解，并用场景随机化测试模型，筛选更稳健的策略。", tags=tags("机器人", "数据采集", "具身智能", "VR", "Isaac Sim", "模型训练"), source_ref=SOURCE),
        dict(title="优必选机器人教材开发：YOLO 视觉检测与 IK", kind="教材开发", period="2026.07 - 2026.08", organization="深技大人工智能学院具身智能小组", role="章节编写者与示范项目开发者", context="参与机器人教材编写，覆盖传统方法与新式方法，并满足教材文案和项目规范。", work="负责 YOLO 感知章节文案、示范项目和自动标注脚本；为仿真抓取模块提供实践基线。", tools="C++、Python、YOLO、ROS2、Gazebo、Linux/WSL", outcome="完成教材章节文案、示范项目和仿真数据自动标注流程。", challenge="教学表达、感知抓取全链路复杂度和章节协作需要同时平衡。", solution="与老师和同学协作调整内容，采用简化仿真降低理解成本，并根据仿真场景生成自动标注数据训练 YOLO 模型。", tags=tags("机器人", "YOLO", "视觉", "ROS2", "数据标注", "自动化"), source_ref=SOURCE),
        dict(title="基于 YOLO 的跌倒检测系统", kind="课程设计", period="2025.12", organization="课程项目", role="项目成员", context="面向视频场景实现跌倒行为检测。", work="完成视觉检测相关项目开发与实验验证。", tools="Python、YOLO", outcome="完成课程项目。", tags=tags("计算机视觉", "YOLO", "Python", "机器学习"), source_ref=SOURCE),
        dict(title="基于 Isaac Sim 的小车自主走迷宫", kind="课程设计", period="2025.12", organization="课程项目", role="项目成员", context="在仿真环境中验证小车自主导航与走迷宫。", work="完成仿真场景配置、算法验证和结果调试。", tools="Isaac Sim、Python、Linux", outcome="完成课程项目。", tags=tags("机器人", "Isaac Sim", "仿真", "Python"), source_ref=SOURCE),
        dict(title="B 站弹幕网页爬虫与数据分析", kind="课程设计", period="2025.06", organization="课程项目", role="项目成员", context="采集网页弹幕并进行数据整理与分析。", work="完成网页数据采集、清洗和可视化分析。", tools="Python、HTML", outcome="完成课程项目。", tags=tags("Python", "数据采集", "数据分析", "爬虫"), source_ref=SOURCE),
        dict(title="城市餐饮数据分析", kind="课程设计", period="2025.12", organization="课程项目", role="项目成员", context="对城市餐饮数据进行整理和分析。", work="完成数据处理、统计分析和结论整理。", tools="Python", outcome="完成课程项目。", tags=tags("Python", "数据分析", "数据科学"), source_ref=SOURCE),
        dict(title="智能台灯：鸿蒙星闪应用", kind="课程设计", period="2025.06", organization="课程项目", role="项目成员", context="使用鸿蒙星闪完成智能设备交互。", work="参与嵌入式设备开发和联调。", tools="开源鸿蒙、嵌入式设备", outcome="完成课程项目。", tags=tags("鸿蒙", "嵌入式", "设备开发"), source_ref=SOURCE),
        dict(title="蓝桥杯与码蹄杯算法竞赛", kind="竞赛", period="2025 - 2026", organization="个人参赛", role="独立参赛者", context="完成算法竞赛题目并提交通过代码。", work="使用 C++ 进行算法设计、编码和调试。", tools="C++、VS Code、Linux", outcome="蓝桥杯、码蹄杯相关奖项，具体等级需以证书核对。", tags=tags("算法", "C++", "竞赛", "数据结构"), is_verified=False, public_note="原始资料对具体奖项等级存在不同表述，导出前请核对证书。", source_ref=SOURCE),
    ]
    for index, item in enumerate(experiences):
        db.add(Experience(sort_order=index, **item))

    skills = [
        ("C/C++", "编程语言", "熟练", "ACM 算法竞赛、机器人传统 IK", ("算法", "机器人")),
        ("Python", "编程语言", "能用", "项目自动化脚本、ROS2、数据分析", ("Python", "数据采集", "数据分析")),
        ("YOLO", "视觉与模型", "能用", "视觉检测与教材示范项目", ("YOLO", "视觉", "机器人")),
        ("ACT / Diffusion", "视觉与模型", "能用", "机器人动作策略训练与测试", ("具身智能", "模型训练")),
        ("ROS2", "机器人开发", "能用", "机器人教材与仿真项目", ("ROS2", "机器人")),
        ("Isaac Sim / Gazebo / CoppeliaSim", "仿真平台", "能用", "机器人课程项目与实验室任务", ("仿真", "机器人")),
        ("VR 头显与主从机械臂", "数据采集设备", "能用", "机器人运动数据采集", ("VR", "数据采集", "机器人")),
        ("Windows + WSL / Ubuntu", "开发环境", "熟练", "个人与实验室开发", ("Linux", "开发工具")),
    ]
    for index, (name, category, proficiency, context, skill_tags) in enumerate(skills):
        db.add(Skill(name=name, category=category, proficiency=proficiency, context=context, tags=tags(*skill_tags), sort_order=index, source_ref=SOURCE))

    db.add_all([
        Award(title="越疆 X-Trainer 竞赛", period="2026.06", issuer="越疆", result="省三等奖", tags=tags("机器人", "竞赛"), source_ref=SOURCE),
        Award(title="优必选天工无疆全球人形机器人挑战赛", period="2026.08", issuer="优必选", result="第 20 名", tags=tags("机器人", "具身智能", "竞赛"), source_ref=SOURCE),
        Award(title="蓝桥杯 / 码蹄杯算法竞赛", period="2025 - 2026", issuer="相关赛事", result="奖项等级待证书核对", note="原始资料存在多处不同表述，暂不在默认正式简历中突出。", tags=tags("算法", "C++", "竞赛"), is_verified=False, source_ref=SOURCE),
    ])
    db.add(JobTarget(name="机器人数据采集员", company="具身智能 / 机器人企业", description="关注机器人运动数据采集、数据标注、仿真验证、设备联调与问题分析。", tags=tags("机器人", "数据采集", "数据标注", "具身智能", "VR", "Isaac Sim", "Linux"), is_default=True))
    db.add(ResumeTemplate(name="经典侧栏模板", slug="classic", description="适合技术项目型岗位的一页式侧栏 HTML 模板。", content=template_content, is_builtin=True))
    db.commit()
    return True
