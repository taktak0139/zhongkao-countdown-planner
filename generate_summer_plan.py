from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path


TARGET = Path("/Users/apple/作业/03_学生档案/学生暑期任务计划.csv")
ABILITY = Path("/Users/apple/作业/03_学生档案/学生能力库.csv")

STUDENTS = [("S001", "李悦嘉"), ("S002", "李承岳")]
WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六"]
SUBJECT_ORDER = ["数学", "语文", "英语", "物理", "数学", "四科综合"]
SUBJECT_ROTATION = {
    "周一": "数学",
    "周二": "语文",
    "周三": "英语",
    "周四": "物理",
    "周五": "数学",
    "周六": "四科综合",
}

KNOWLEDGE = {
    "数学": [
        ("M001", "整数与有理数混合运算"),
        ("M002", "绝对值概念"),
        ("M003", "合并同类项"),
        ("M004", "一元一次方程移项"),
        ("M005", "平方差公式与因式分解"),
        ("M101", "正数与负数"),
        ("M102", "数轴"),
        ("M103", "绝对值"),
        ("M104", "有理数四则运算"),
        ("M105", "单项式与多项式"),
        ("M106", "合并同类项"),
        ("M107", "整式加减"),
        ("M108", "方程概念"),
        ("M109", "解一元一次方程"),
        ("M110", "一元一次方程应用"),
        ("M203", "因式分解"),
        ("M303", "全等三角形证明"),
        ("M403", "勾股定理"),
        ("M407", "一次函数图像"),
        ("M409", "一次函数应用"),
        ("M501", "一元二次方程基础"),
        ("M503", "二次函数基础"),
    ],
    "语文": [
        ("Y101", "重点字音字形"),
        ("Y102", "词语辨析"),
        ("Y103", "记叙文阅读方法"),
        ("Y104", "古诗理解与背诵"),
        ("Y105", "审题立意基础"),
        ("Y201", "散文阅读方法"),
        ("Y202", "人物形象分析"),
        ("Y203", "文言文基础词汇"),
        ("Y204", "作文结构安排"),
        ("Y301", "新闻类文本阅读"),
        ("Y302", "说明文阅读方法"),
        ("Y403", "文言文翻译"),
        ("Y501", "现代文阅读"),
        ("Y503", "中考作文"),
    ],
    "英语": [
        ("E101", "核心词汇"),
        ("E103", "一般现在时"),
        ("E104", "句型转换"),
        ("E201", "短语搭配"),
        ("E202", "一般过去时"),
        ("E203", "句子翻译"),
        ("E302", "现在进行时"),
        ("E303", "比较级最高级"),
        ("E402", "现在完成时"),
        ("E403", "被动语态"),
        ("E404", "宾语从句"),
        ("E503", "阅读理解"),
        ("E504", "完形填空"),
        ("E406", "英语写作"),
    ],
    "物理": [
        ("P001", "长度与时间测量"),
        ("P002", "速度计算"),
        ("P003", "运动图像判断"),
        ("P004", "声音传播"),
        ("P101", "温度计与物态变化"),
        ("P105", "光的反射"),
        ("P106", "平面镜成像"),
        ("P107", "光的折射"),
        ("P201", "力的作用效果"),
        ("P203", "二力平衡"),
        ("P204", "摩擦力"),
        ("P205", "压强计算"),
        ("P206", "液体压强"),
        ("P208", "浮力"),
        ("P301", "功的计算"),
        ("P302", "功率计算"),
        ("P403", "欧姆定律"),
        ("P404", "电功率"),
    ],
}

STAGE_NAMES = {
    1: "第1阶段：快速诊断与基础铺底",
    2: "第1阶段：快速诊断与基础铺底",
    3: "第2阶段：基础知识快速覆盖",
    4: "第2阶段：基础知识快速覆盖",
    5: "第3阶段：薄弱点讲解与错题回炉",
    6: "第3阶段：薄弱点讲解与错题回炉",
    7: "第4阶段：综合提升与模拟训练",
    8: "第4阶段：综合提升与模拟训练",
}


def read_mastered() -> set[tuple[str, str, str]]:
    mastered: set[tuple[str, str, str]] = set()
    if not ABILITY.exists():
        return mastered
    with ABILITY.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("状态") == "已掌握":
                mastered.add((row.get("学生", ""), row.get("学科", ""), row.get("知识点ID", "")))
                if row.get("学生ID"):
                    mastered.add((row.get("学生ID", ""), row.get("学科", ""), row.get("知识点ID", "")))
    return mastered


def ability_rows() -> list[dict[str, str]]:
    if not ABILITY.exists():
        return []
    with ABILITY.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def weak_pool(student_id: str, student_name: str, mastered: set[tuple[str, str, str]]) -> list[tuple[str, str, str, str]]:
    priority = {"重点薄弱": 1, "薄弱": 2, "改善中": 3, "未测试": 4}
    rows = []
    for row in ability_rows():
        identity_match = row.get("学生ID") == student_id or row.get("学生") == student_name
        if not identity_match:
            continue
        status = row.get("状态") or "未测试"
        subject = row.get("学科", "")
        kid = row.get("知识点ID", "")
        if status == "已掌握" or (student_id, subject, kid) in mastered or (student_name, subject, kid) in mastered:
            continue
        rows.append((priority.get(status, 5), subject, kid, row.get("知识点", ""), status))
    rows.sort(key=lambda item: item[0])
    return [(subject, kid, name, status) for _, subject, kid, name, status in rows]


def next_item(subject: str, cursors: dict[str, int]) -> tuple[str, str]:
    items = KNOWLEDGE[subject]
    item = items[cursors[subject] % len(items)]
    cursors[subject] += 1
    return item


def row(date: str, week: int, weekday: str, student: str, task_type: str, subject: str, kid: str, knowledge: str,
        stage: str, content: str, mainline: str, weak: str, skippable: str, source: str, minutes: int) -> dict[str, str | int]:
    return {
        "日期": date,
        "周次": f"第{week}周",
        "星期": weekday,
        "学生": student,
        "任务类型": task_type,
        "学科": subject,
        "知识点ID": kid,
        "知识点": knowledge,
        "阶段": stage,
        "45分钟任务内容": content,
        "是否主线任务": mainline,
        "是否补弱任务": weak,
        "是否允许跳过": skippable,
        "任务来源": source,
        "预计时长": minutes,
    }


def generate() -> list[dict[str, str | int]]:
    mastered = read_mastered()
    rows: list[dict[str, str | int]] = []
    cursors = {subject: 0 for subject in KNOWLEDGE}
    weak_cursors = defaultdict(int)

    for student_id, student_name in STUDENTS:
        weak_items = weak_pool(student_id, student_name, mastered)
        if not weak_items:
            weak_items = [("数学", "M104", "有理数四则运算", "未测试")]
        for week in range(1, 9):
            for weekday in WEEKDAYS:
                date = f"第{week}周{weekday}"
                stage = STAGE_NAMES[week]
                subject = SUBJECT_ROTATION[weekday]
                if subject == "四科综合":
                    main_subject = SUBJECT_ORDER[(week + WEEKDAYS.index(weekday)) % 5]
                else:
                    main_subject = subject

                kid, knowledge = next_item(main_subject, cursors)
                task_type = "阶段测试" if weekday == "周六" and week in {2, 4, 6} else "综合模拟" if weekday == "周六" and week in {7, 8} else "主线推进"
                rows.append(row(
                    date, week, weekday, student_name, task_type, main_subject, kid, knowledge, stage,
                    f"主线推进：讲清{knowledge}的核心方法，完成基础例题和当堂小练。",
                    "是", "否", "否", "8周知识点主线时间表", 45,
                ))

                if week <= 4:
                    kid2, knowledge2 = next_item(main_subject, cursors)
                    rows.append(row(
                        date, week, weekday, student_name, "主线推进", main_subject, kid2, knowledge2, stage,
                        f"快速覆盖：完成{knowledge2}的典型题训练，标记已掌握和疑难点。",
                        "是", "否", "是", "前4周快速覆盖计划", 45,
                    ))
                    weak_subject, weak_id, weak_name, status = weak_items[weak_cursors[student_name] % len(weak_items)]
                    weak_cursors[student_name] += 1
                    rows.append(row(
                        date, week, weekday, student_name, "薄弱补救", weak_subject, weak_id, weak_name, stage,
                        f"滚动补弱：复盘{weak_name}前次错因，完成2道同类题。",
                        "否", "是", "是", f"能力库状态：{status}", 45,
                    ))
                else:
                    weak_subject, weak_id, weak_name, status = weak_items[weak_cursors[student_name] % len(weak_items)]
                    weak_cursors[student_name] += 1
                    rows.append(row(
                        date, week, weekday, student_name, "薄弱补救", weak_subject, weak_id, weak_name, stage,
                        f"讲解补弱：重讲{weak_name}的概念、方法和易错点，完成1组变式题。",
                        "否", "是", "否", f"能力库状态：{status}", 45,
                    ))
                    weak_subject2, weak_id2, weak_name2, status2 = weak_items[weak_cursors[student_name] % len(weak_items)]
                    weak_cursors[student_name] += 1
                    rows.append(row(
                        date, week, weekday, student_name, "错题复测" if weekday != "周六" else "综合模拟", weak_subject2, weak_id2, weak_name2, stage,
                        f"错题复测：针对{weak_name2}完成复测题，记录是否改善。",
                        "否", "是", "是" if weekday != "周六" else "否", f"能力库状态：{status2}", 45,
                    ))
    return rows


def validate(rows: list[dict[str, str | int]]) -> dict[str, int | bool]:
    by_day = defaultdict(list)
    for r in rows:
        by_day[(r["学生"], r["周次"], r["星期"])].append(r)

    required_days = {(student, f"第{week}周", weekday) for _, student in STUDENTS for week in range(1, 9) for weekday in WEEKDAYS}
    all_days_present = required_days.issubset(set(by_day))
    max_minutes = max(sum(int(r["预计时长"]) for r in items) for items in by_day.values())
    daily_mainline = all(any(r["是否主线任务"] == "是" for r in by_day[key]) for key in required_days)

    front_mainline = {(r["学科"], r["知识点ID"]) for r in rows if r["是否主线任务"] == "是" and int(str(r["周次"]).strip("第周")) <= 4}
    back_mainline = {(r["学科"], r["知识点ID"]) for r in rows if r["是否主线任务"] == "是" and int(str(r["周次"]).strip("第周")) >= 5}
    front_weak = sum(1 for r in rows if r["是否补弱任务"] == "是" and int(str(r["周次"]).strip("第周")) <= 4)
    back_weak = sum(1 for r in rows if r["是否补弱任务"] == "是" and int(str(r["周次"]).strip("第周")) >= 5)
    return {
        "任务总行数": len(rows),
        "每日最大时长": max_minutes,
        "完整8周": all_days_present,
        "每天主线": daily_mainline,
        "前4周知识点覆盖数量": len(front_mainline),
        "后4周新知识点数量": len(back_mainline),
        "前4周补弱复测任务数量": front_weak,
        "后4周补弱复测任务数量": back_weak,
        "验收通过": all_days_present and max_minutes <= 135 and daily_mainline and len(front_mainline) > len(back_mainline) and back_weak > front_weak,
    }


def main() -> None:
    rows = generate()
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    headers = ["日期", "周次", "星期", "学生", "任务类型", "学科", "知识点ID", "知识点", "阶段", "45分钟任务内容", "是否主线任务", "是否补弱任务", "是否允许跳过", "任务来源", "预计时长"]
    with TARGET.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    stats = validate(rows)
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
