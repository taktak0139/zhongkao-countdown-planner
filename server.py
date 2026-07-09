from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import csv
import json
import re
from datetime import datetime
from urllib.parse import quote


BASE_DIR = Path(__file__).resolve().parent
DATA_ROOT = BASE_DIR / "data"
ABILITY_PATH = DATA_ROOT / "学生能力库.csv"
VIDEO_PATH = DATA_ROOT / "薄弱知识点视频推荐.csv"
PLAN_PATH = DATA_ROOT / "学生暑期任务计划.csv"
BUDGET_PATH = DATA_ROOT / "学习预算设置.csv"
DAILY_FILTER_TYPES = {"日常测试", "专项训练"}
FULL_TEST_TYPES = {"月考", "终考", "综合模拟", "阶段大测"}
PLAN_HEADERS = ["日期", "周次", "星期", "学生", "任务类型", "学科", "知识点ID", "知识点", "阶段", "45分钟任务内容", "是否主线任务", "是否补弱任务", "是否允许跳过", "任务来源", "预计时长"]


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path not in {"/api/grade", "/api/tasks", "/api/progress", "/api/budget"}:
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if self.path == "/api/grade":
            result = grade(payload)
        elif self.path == "/api/tasks":
            result = generate_tasks(payload)
        elif self.path == "/api/progress":
            result = progress_dashboard(payload)
        else:
            result = apply_budget(payload)
        body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def normalize(text):
    return re.sub(r"\s+", "", str(text or "").lower())


def grade(payload):
    paper = payload["paper"]
    student = payload["student"]
    answers = payload.get("answers", {})
    elapsed_seconds = int(payload.get("elapsedSeconds", 0) or 0)
    items = []
    total = 0
    weak = []
    questions = available_questions(paper)
    paper_total = sum(int(q.get("score", 0) or 0) for q in questions)
    for q in questions:
        raw_answer = answers.get(q["no"], "")
        ans = normalize(raw_answer)
        full = int(q["score"])
        if q["grading"] == "objective":
            ok = ans == normalize(q["answer"]) or ans == normalize(str(q["answer"])[0:1])
            score = full if ok else 0
            reason = "答案正确。" if ok else f"标准答案为 {q['answer']}。"
            error_type = "" if ok else "基础知识错误"
        else:
            keywords = q.get("keywords", [])
            hit = sum(1 for word in keywords if normalize(word) in ans)
            ratio = hit / max(len(keywords), 1)
            score = round(full * min(1, ratio))
            reason = "回答覆盖主要得分点。" if score == full else f"得分点覆盖不足，参考标准：{q['rubric']}"
            error_type = "" if score >= full * 0.8 else "表达/方法不完整"
        total += score
        if score < full:
            weak.append(q["knowledge"])
        items.append({
            "no": q["no"],
            "score": score,
            "fullScore": full,
            "studentAnswer": raw_answer or "未作答",
            "correctAnswer": q["answer"],
            "rubric": q["rubric"],
            "explanation": build_explanation(q),
            "deductionReason": reason,
            "errorType": error_type,
            "errorKnowledge": "" if score == full else q["knowledge"],
            "knowledgeId": q["knowledgeId"],
            "knowledgeName": q["knowledge"],
            "knowledgeExplanation": knowledge_explanation(paper["subject"], q["knowledge"]),
            "mastery": mastery(score, full),
            "suggestion": "保持巩固。" if score == full else f"复盘 {q['knowledge']}，完成同类题 3 道后复测。",
            "bilibiliLink": bilibili_link(paper["subject"], q["knowledge"]),
            "publicCourseKeyword": public_course_keyword(paper["subject"], q["knowledge"]),
            "publicCourseLink": public_course_link(paper["subject"], q["knowledge"]),
            "subject": paper["subject"],
            "difficultyLevel": difficulty_level(q),
            "gradeScope": q.get("grade_scope", "初二升初三暑期"),
            "learnedUntil": q.get("learned_until", "初二下学期结束"),
            "isAvailableForGrade8Summer": q.get("is_available_for_grade8_summer", True) is not False,
            **resource_for(paper["subject"], q["knowledge"]),
        })
    weak_text = "、".join(dict.fromkeys(weak)) or "暂无明显薄弱点"
    result = {
        "studentId": student["id"],
        "studentName": student["name"],
        "paperId": paper["id"],
        "subject": paper["subject"],
        "totalScore": total,
        "paperTotal": paper_total,
        "elapsedSeconds": elapsed_seconds,
        "items": items,
        "todayTask": f"优先复盘：{weak_text}。",
        "nextPlan": f"围绕 {weak_text} 安排基础讲解、同类训练和复测。",
        "trend": "已完成首轮诊断，后续趋势将在多次测试后生成。",
    }
    persist_learning_assets(result)
    return result


def difficulty_level(question):
    raw = question.get("difficulty_level")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    return {"基础": 1, "中档": 2, "综合": 3}.get(question.get("difficulty"), 4)


def available_questions(paper):
    questions = [q for q in paper.get("questions", []) if q.get("is_available_for_grade8_summer", True) is not False]
    return sorted(questions, key=lambda q: (difficulty_level(q), int(q["no"]) if str(q["no"]).isdigit() else 999))


def build_explanation(q):
    return f"本题考查{q['knowledge']}。参考答案：{q['answer']}。评分依据：{q['rubric']}"


def knowledge_explanation(subject, knowledge):
    return (
        f"{knowledge}是初中{subject}里很基础也很常用的知识点。学习时先抓住题目问什么，再找对应规则或公式，"
        f"不要急着套答案。做题后要把错因写清楚：是概念没懂、步骤漏写，还是计算失误。下次遇到同类题，先复述方法，"
        f"再独立完成一题，最后用答案检查关键步骤。"
    )


def mastery(score, full):
    if full <= 0:
        return "未评估"
    rate = score / full
    if rate >= 0.9:
        return "掌握较好"
    if rate >= 0.7:
        return "基本掌握，需巩固"
    if rate >= 0.6:
        return "掌握不稳，需重新讲解"
    return "薄弱，需要基础补课"


def bilibili_link(subject, knowledge):
    return "https://search.bilibili.com/all?keyword=" + quote(f"苏教版 八年级 初中 {subject} {knowledge}")


def public_course_keyword(subject, knowledge):
    return f"苏教版 八年级 初中 {subject} {knowledge}"


def public_course_link(subject, knowledge):
    return "https://basic.smartedu.cn/syncClassroom?keyword=" + quote(public_course_keyword(subject, knowledge))


def resource_for(subject, knowledge):
    return {
        "textbookVersion": "苏教版",
        "resourceGrade": "八年级",
        "resourceTitle": f"苏教版八年级{subject}：{knowledge}",
        "resourceUrl": "",
        "resourceSource": "待补充",
        "resourceStatus": "pending_review",
        "resourceNote": "待补充苏教版资源，推荐人工审核后上线",
    }


def ensure_csv(path, headers):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8-sig") as file:
            csv.DictWriter(file, fieldnames=headers).writeheader()


def read_csv(path, headers):
    ensure_csv(path, headers)
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    return [{header: row.get(header, "") for header in headers} for row in rows]


def write_csv(path, headers, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def persist_learning_assets(result):
    update_ability_library(result)
    append_video_recommendations(result)


def update_ability_library(result):
    headers = ["学生", "学生ID", "学科", "知识点ID", "知识点", "答题次数", "正确次数", "错误次数", "连续错误次数", "连续正确次数", "正确率", "状态", "最近更新时间"]
    rows = read_csv(ABILITY_PATH, headers)
    index = {(row.get("学生ID", ""), row.get("学科", ""), row.get("知识点ID", "")): row for row in rows if row.get("知识点ID")}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for item in result["items"]:
        key = (result["studentId"], result["subject"], item["knowledgeId"])
        row = index.get(key) or {
            "学生": result["studentName"],
            "学生ID": result["studentId"],
            "学科": result["subject"],
            "知识点ID": item["knowledgeId"],
            "知识点": item["knowledgeName"],
            "答题次数": "0",
            "正确次数": "0",
            "错误次数": "0",
            "连续错误次数": "0",
            "连续正确次数": "0",
            "正确率": "0%",
            "状态": "未测试",
            "最近更新时间": "",
        }
        full = max(float(item["fullScore"]), 1)
        correct = item["score"] >= full * 0.9
        attempts = int(row["答题次数"]) + 1
        correct_count = int(row["正确次数"]) + (1 if correct else 0)
        wrong_count = int(row["错误次数"]) + (0 if correct else 1)
        consecutive_wrong = 0 if correct else int(row["连续错误次数"]) + 1
        consecutive_correct = int(row["连续正确次数"]) + 1 if correct else 0
        rate = correct_count / attempts
        row.update({
            "学生": result["studentName"],
            "知识点": item["knowledgeName"],
            "答题次数": str(attempts),
            "正确次数": str(correct_count),
            "错误次数": str(wrong_count),
            "连续错误次数": str(consecutive_wrong),
            "连续正确次数": str(consecutive_correct),
            "正确率": f"{round(rate * 100)}%",
            "状态": ability_status(correct, consecutive_wrong, consecutive_correct, rate, wrong_count),
            "最近更新时间": now,
        })
        index[key] = row
    write_csv(ABILITY_PATH, headers, list(index.values()))


def ability_status(correct, consecutive_wrong, consecutive_correct, rate, wrong_count):
    if consecutive_correct >= 2 or rate >= 0.9:
        return "已掌握"
    if correct and wrong_count > 0:
        return "改善中"
    if consecutive_wrong >= 2:
        return "重点薄弱"
    if not correct:
        return "薄弱"
    return "改善中"


def append_video_recommendations(result):
    headers = ["学生", "学科", "知识点ID", "知识点", "错误次数", "教材版本", "年级", "B站搜索链接", "公开课搜索关键词", "资源状态", "推荐用途"]
    rows = read_csv(VIDEO_PATH, headers)
    existing = {(row["学生"], row["学科"], row["知识点ID"]) for row in rows}
    wrong_counts = {}
    for item in result["items"]:
        if item["score"] >= item["fullScore"]:
            continue
        key = item["knowledgeId"]
        wrong_counts[key] = wrong_counts.get(key, {"item": item, "count": 0})
        wrong_counts[key]["count"] += 1
    for data in wrong_counts.values():
        item = data["item"]
        key = (result["studentName"], result["subject"], item["knowledgeId"])
        if key in existing:
            continue
        rows.append({
            "学生": result["studentName"],
            "学科": result["subject"],
            "知识点ID": item["knowledgeId"],
            "知识点": item["knowledgeName"],
            "错误次数": str(data["count"]),
            "教材版本": item.get("textbookVersion", "苏教版"),
            "年级": item.get("resourceGrade", "八年级"),
            "B站搜索链接": item["bilibiliLink"],
            "公开课搜索关键词": item["publicCourseKeyword"],
            "资源状态": item.get("resourceStatus", "pending_review"),
            "推荐用途": "用于薄弱知识点讲解、同类题复盘和复测前预习",
        })
    write_csv(VIDEO_PATH, headers, rows)


def generate_tasks(payload):
    student_id = payload["studentId"]
    subject = payload.get("subject", "数学")
    test_type = payload.get("testType", "日常测试")
    paper = payload.get("paper") or {"questions": []}
    headers = ["学生", "学生ID", "学科", "知识点ID", "知识点", "答题次数", "正确次数", "错误次数", "连续错误次数", "连续正确次数", "正确率", "状态", "最近更新时间"]
    rows = [row for row in read_csv(ABILITY_PATH, headers) if row["学生ID"] == student_id and row["学科"] == subject]
    status_rank = {"重点薄弱": 1, "薄弱": 2, "改善中": 3, "未测试": 4, "新知识": 5, "已掌握": 99}
    allow_mastered = test_type in FULL_TEST_TYPES
    if test_type in DAILY_FILTER_TYPES:
        rows = [row for row in rows if row["状态"] != "已掌握"]
    rows.sort(key=lambda row: status_rank.get(row["状态"], 50))
    tasks = [{"知识点ID": row["知识点ID"], "知识点": row["知识点"], "状态": row["状态"], "任务类型": test_type} for row in rows]
    if allow_mastered and paper.get("questions"):
        known = {task["知识点ID"] for task in tasks}
        for q in available_questions(paper):
            if q["knowledgeId"] not in known:
                tasks.append({"知识点ID": q["knowledgeId"], "知识点": q["knowledge"], "状态": "新知识", "任务类型": test_type})
    return {"testType": test_type, "allowMastered": allow_mastered, "tasks": tasks}


def current_budget():
    headers = ["每日学习预算"]
    rows = read_csv(BUDGET_PATH, headers)
    if rows and rows[0].get("每日学习预算"):
        return int(rows[0]["每日学习预算"])
    return 135


def ability_map():
    headers = ["学生", "学生ID", "学科", "知识点ID", "知识点", "答题次数", "正确次数", "错误次数", "连续错误次数", "连续正确次数", "正确率", "状态", "最近更新时间"]
    rows = read_csv(ABILITY_PATH, headers)
    index = {}
    for row in rows:
        for identity in {row.get("学生", ""), row.get("学生ID", "")}:
            if identity:
                index[(identity, row.get("学科", ""), row.get("知识点ID", ""))] = row
    return index


def progress_dashboard(payload):
    student_id = payload.get("studentId", "")
    student_name = payload.get("studentName", "")
    plan_rows = [row for row in read_csv(PLAN_PATH, PLAN_HEADERS) if row.get("学生") == student_name]
    abilities = ability_map()
    mainline = [row for row in plan_rows if row.get("是否主线任务") == "是"]
    unique_mainline = {(row["学科"], row["知识点ID"]) for row in mainline}
    mastered = 0
    unmastered = 0
    weak_backlog = 0
    touched = 0
    for subject, kid in unique_mainline:
        ability = abilities.get((student_id, subject, kid)) or abilities.get((student_name, subject, kid))
        status = ability.get("状态", "未测试") if ability else "未测试"
        if status == "已掌握":
            mastered += 1
            touched += 1
        elif status in {"薄弱", "重点薄弱", "改善中"}:
            unmastered += 1
            touched += 1
            if status in {"薄弱", "重点薄弱"}:
                weak_backlog += 1
        else:
            unmastered += 1
    completion_rate = round((touched / max(len(unique_mainline), 1)) * 100)
    current_week = min(8, max(1, completion_rate // 13 + 1))
    current_stage = stage_for_week(current_week)
    expected_rate = current_week / 8 * 100
    deviation = "进度正常" if completion_rate >= expected_rate - 10 else "轻微滞后" if completion_rate >= expected_rate - 25 else "明显滞后"
    can_complete = deviation != "明显滞后"
    target_score = 525
    current_score = round(750 * (mastered / max(mastered + unmastered, 1)))
    gap = max(0, target_score - current_score)
    target_risk = "绿色" if gap <= 40 else "黄色" if gap <= 120 else "红色"
    return {
        "studentId": student_id,
        "studentName": student_name,
        "currentWeek": current_week,
        "currentStage": current_stage,
        "mainlineCompletionRate": completion_rate,
        "weakBacklogCount": weak_backlog,
        "masteredCount": mastered,
        "unmasteredCount": unmastered,
        "canCompleteIn8Weeks": can_complete,
        "progressDeviation": deviation,
        "budgetMinutes": current_budget(),
        "target": {
            "name": "无锡中考基础平均线目标",
            "currentScore": current_score,
            "targetScore": target_score,
            "gap": gap,
            "riskLevel": target_risk,
        },
        "heatmap": heatmap(plan_rows, abilities, student_id, student_name),
    }


def stage_for_week(week):
    if week <= 2:
        return "快速诊断与基础铺底"
    if week <= 4:
        return "基础知识快速覆盖"
    if week <= 6:
        return "薄弱点讲解与错题回炉"
    return "综合提升与模拟训练"


def heatmap(plan_rows, abilities, student_id, student_name):
    weeks = [f"第{i}周" for i in range(1, 9)]
    subjects = ["数学", "语文", "英语", "物理"]
    cells = {subject: [] for subject in subjects}
    for subject in subjects:
        for week in weeks:
            rows = [row for row in plan_rows if row.get("周次") == week and row.get("学科") == subject]
            kids = {(row["学科"], row["知识点ID"]) for row in rows if row.get("知识点ID")}
            mastered = weak = touched = unmastered = 0
            for sub, kid in kids:
                ability = abilities.get((student_id, sub, kid)) or abilities.get((student_name, sub, kid))
                status = ability.get("状态", "未测试") if ability else "未测试"
                if status == "已掌握":
                    mastered += 1
                    touched += 1
                elif status in {"薄弱", "重点薄弱", "改善中"}:
                    touched += 1
                    unmastered += 1
                    if status in {"薄弱", "重点薄弱"}:
                        weak += 1
                else:
                    unmastered += 1
            rate = round(touched / max(len(kids), 1) * 100)
            risk = "green" if rate >= 70 and weak <= 1 else "yellow" if rate >= 35 else "red"
            cells[subject].append({
                "week": week,
                "mainlineCompletionRate": rate,
                "weakCount": weak,
                "masteredCount": mastered,
                "unmasteredCount": unmastered,
                "riskLevel": {"green": "进度正常", "yellow": "轻微滞后", "red": "明显滞后"}[risk],
                "riskClass": f"risk-{risk}",
            })
    return {"weeks": weeks, "subjects": subjects, "cells": cells}


def apply_budget(payload):
    budget = int(payload.get("budgetMinutes", 135))
    if budget not in {90, 120, 135, 180}:
        budget = 135
    rows = read_csv(PLAN_PATH, PLAN_HEADERS)
    grouped = {}
    for row in rows:
        grouped.setdefault((row["学生"], row["周次"], row["星期"]), []).append(row)
    for items in grouped.values():
        per_task = budget // max(len(items), 1)
        for row in items:
            row["预计时长"] = str(per_task)
            row["45分钟任务内容"] = row["45分钟任务内容"].replace("45分钟", f"{per_task}分钟")
    write_csv(PLAN_PATH, PLAN_HEADERS, rows)
    write_csv(BUDGET_PATH, ["每日学习预算"], [{"每日学习预算": str(budget)}])
    max_daily = max(sum(int(row["预计时长"]) for row in items) for items in grouped.values()) if grouped else 0
    return {"budgetMinutes": budget, "maxDailyMinutes": max_daily, "timelinePreserved": True, "days": len(grouped)}


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
