from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import csv
import json
import re
from datetime import date, datetime
from urllib.parse import quote



BASE_DIR = Path(__file__).resolve().parent
DATA_ROOT = BASE_DIR / "data"
ABILITY_PATH = DATA_ROOT / "学生能力库.csv"
VIDEO_PATH = DATA_ROOT / "薄弱知识点视频推荐.csv"
PLAN_PATH = DATA_ROOT / "学生暑期任务计划.csv"
BUDGET_PATH = DATA_ROOT / "学习预算设置.csv"
COMPLETION_PATH = DATA_ROOT / "学习任务完成记录.csv"
DAILY_HISTORY_PATH = DATA_ROOT / "每日试卷历史记录.csv"
REPORT_ROOT = BASE_DIR / "reports"
DAILY_FILTER_TYPES = {"日常测试", "专项训练"}
FULL_TEST_TYPES = {"月考", "终考", "综合模拟", "阶段大测"}
PLAN_HEADERS = ["日期", "周次", "星期", "学生", "任务类型", "学科", "知识点ID", "知识点", "阶段", "45分钟任务内容", "是否主线任务", "是否补弱任务", "是否允许跳过", "任务来源", "预计时长"]
COMPLETION_HEADERS = ["学生", "学生ID", "日期", "任务日期", "任务类型", "试卷ID", "学科", "得分", "总分", "提交时间"]
DAILY_HISTORY_HEADERS = ["学生", "学生ID", "日期", "提交时间", "试卷ID", "试卷名称", "学科", "得分", "总分", "用时秒", "已掌握知识点", "未掌握知识点", "学习建议", "报告文件"]

# 计划从 2026 年 7 月 6 日（周一）开始。CSV 中的“第X周周Y”由此映射到真实日期；
# 这样不会再把第 1 天的静态内容当作每天的内容。
TIMELINE_START_DATE = date(2026, 7, 6)
STUDY_WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六"]
TESTABLE_KNOWLEDGE = {
    "数学": {"M001", "M002", "M106", "M109", "M203", "M303", "M403", "M407", "M409", "M501"},
    "语文": {"Y101", "Y104", "Y201", "Y401", "Y105"},
    "英语": {"E103", "E202", "E404", "E105", "E203", "E406"},
    "物理": {"P002", "P004", "P106", "P203", "P205", "P208", "P301", "P302"},
}


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path not in {"/api/grade", "/api/tasks", "/api/progress", "/api/budget", "/api/daily-plan", "/api/daily-history"}:
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
        elif self.path == "/api/daily-plan":
            result = daily_plan(payload)
        elif self.path == "/api/daily-history":
            result = daily_history(payload)
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
    submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = {
        "studentId": student["id"],
        "studentName": student["name"],
        "paperId": paper["id"],
        "paperName": paper.get("name", paper["id"]),
        "subject": paper["subject"],
        "totalScore": total,
        "paperTotal": paper_total,
        "elapsedSeconds": elapsed_seconds,
        "items": items,
        "todayTask": f"优先复盘：{weak_text}。",
        "nextPlan": f"围绕 {weak_text} 安排基础讲解、同类训练和复测。",
        "trend": "已完成首轮诊断，后续趋势将在多次测试后生成。",
        "submittedAt": submitted_at,
    }
    persist_learning_assets(result)
    persist_daily_completion(result, payload.get("dailyPlan") or {})
    result["dailyReport"] = persist_daily_report(result, payload.get("dailyPlan") or {})
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


def timeline_slot(on_date=None):
    """Return the plan slot for a real calendar date.

    Sunday is intentionally a review/rest day because the current 8-week plan
    contains six study days per week. Dates before the plan starts are kept on
    the first slot so families can preview the plan without advancing it.
    """
    on_date = on_date or date.today()
    if on_date < TIMELINE_START_DATE:
        return {"isStudyDay": True, "week": 1, "weekday": "周一", "date": on_date.isoformat(), "preview": True}
    elapsed = (on_date - TIMELINE_START_DATE).days
    week = elapsed // 7 + 1
    weekday_index = elapsed % 7
    if weekday_index == 6:
        return {"isStudyDay": False, "week": min(week, 8), "weekday": "周日", "date": on_date.isoformat(), "preview": False}
    return {
        "isStudyDay": week <= 8,
        "week": min(week, 8),
        "weekday": STUDY_WEEKDAYS[weekday_index],
        "date": on_date.isoformat(),
        "preview": False,
    }


def completion_rows():
    return read_csv(COMPLETION_PATH, COMPLETION_HEADERS)


def persist_daily_completion(result, daily_plan):
    """Record one submitted daily assessment per student/date, replacing retries."""
    task_date = daily_plan.get("taskDate")
    if not task_date or daily_plan.get("mode") != "rolling_review":
        return
    rows = completion_rows()
    row = {
        "学生": result["studentName"],
        "学生ID": result["studentId"],
        "日期": task_date,
        "任务日期": task_date,
        "任务类型": "每日滚动复测",
        "试卷ID": result["paperId"],
        "学科": result["subject"],
        "得分": str(result["totalScore"]),
        "总分": str(result["paperTotal"]),
        "提交时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    rows = [item for item in rows if not (item.get("学生ID") == result["studentId"] and item.get("日期") == task_date)]
    write_csv(COMPLETION_PATH, COMPLETION_HEADERS, [row, *rows])


def safe_filename(text):
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", str(text or ""))
    return cleaned.strip("._") or "report"


def table_cell(text):
    return str(text or "").replace("|", "｜").replace("\n", " ").strip()


def mastery_groups(result):
    mastered = []
    unmastered = []
    for item in result["items"]:
        target = mastered if item["score"] >= item["fullScore"] * 0.9 else unmastered
        target.append(f"{item['knowledgeId']} {item['knowledgeName']}")
    return sorted(set(mastered)), sorted(set(unmastered))


def persist_daily_report(result, daily_plan):
    task_date = daily_plan.get("taskDate") or date.today().isoformat()
    mastered, unmastered = mastery_groups(result)
    advice = result["nextPlan"]
    report_stem = safe_filename(f"{task_date}-{result['studentName']}")
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)

    answer_rows = "\n".join(
        "| {no} | {kid} {knowledge} | {answer} | {score}/{full} | {mastery} | {reason} |".format(
            no=table_cell(item["no"]),
            kid=table_cell(item["knowledgeId"]),
            knowledge=table_cell(item["knowledgeName"]),
            answer=table_cell(item["studentAnswer"]),
            score=table_cell(item["score"]),
            full=table_cell(item["fullScore"]),
            mastery=table_cell(item["mastery"]),
            reason=table_cell(item["deductionReason"]),
        )
        for item in result["items"]
    )
    mastered_text = "、".join(mastered) if mastered else "暂无"
    unmastered_text = "、".join(unmastered) if unmastered else "暂无"
    wrong_items = [item for item in result["items"] if item["score"] < item["fullScore"] * 0.9]
    followups = "\n".join(f"- {item['knowledgeId']} {item['knowledgeName']}：{item['suggestion']}" for item in wrong_items) or "- 今天没有明显薄弱题，保持同类题巩固。"

    title = f"{task_date} {result['studentName']} 日结报告"
    report = f"""# {title}

## 基本情况

- 试卷：{result['paperName']}
- 学科：{result['subject']}
- 得分：{result['totalScore']} / {result['paperTotal']}
- 用时：{result['elapsedSeconds']} 秒
- 提交时间：{result['submittedAt']}

## 今日回答与评分

| 题号 | 知识点 | 学生答案 | 得分 | 掌握判断 | 评分情况 |
| --- | --- | --- | --- | --- | --- |
{answer_rows}

## 知识点掌握情况

- 已掌握：{mastered_text}
- 未掌握：{unmastered_text}

## 学习建议

{followups}

总体建议：{advice}
"""
    report_path = REPORT_ROOT / f"{report_stem}.md"
    if report_path.exists():
        timestamp = datetime.now().strftime("%H%M%S")
        report_path = REPORT_ROOT / f"{report_stem}-{timestamp}.md"
        sequence = 2
        while report_path.exists():
            report_path = REPORT_ROOT / f"{report_stem}-{timestamp}-{sequence}.md"
            sequence += 1
    report_path.write_text(report, encoding="utf-8")

    try:
        relative = report_path.relative_to(BASE_DIR).as_posix()
        report_url = "/" + quote(relative, safe="/")
    except ValueError:
        relative = report_path.as_posix()
        report_url = ""
    rows = read_csv(DAILY_HISTORY_PATH, DAILY_HISTORY_HEADERS)
    row = {
        "学生": result["studentName"],
        "学生ID": result["studentId"],
        "日期": task_date,
        "提交时间": result["submittedAt"],
        "试卷ID": result["paperId"],
        "试卷名称": result["paperName"],
        "学科": result["subject"],
        "得分": str(result["totalScore"]),
        "总分": str(result["paperTotal"]),
        "用时秒": str(result["elapsedSeconds"]),
        "已掌握知识点": "、".join(mastered),
        "未掌握知识点": "、".join(unmastered),
        "学习建议": advice,
        "报告文件": relative,
    }
    rows = [item for item in rows if not (item.get("学生ID") == result["studentId"] and item.get("日期") == task_date and item.get("试卷ID") == result["paperId"])]
    write_csv(DAILY_HISTORY_PATH, DAILY_HISTORY_HEADERS, [row, *rows])
    return {
        "taskDate": task_date,
        "path": relative,
        "url": report_url,
        "mastered": mastered,
        "unmastered": unmastered,
        "advice": advice,
    }


def daily_history(payload):
    student_id = payload.get("studentId", "")
    student_name = payload.get("studentName", "")
    rows = read_csv(DAILY_HISTORY_PATH, DAILY_HISTORY_HEADERS)
    if student_id or student_name:
        rows = [
            row for row in rows
            if (student_id and row.get("学生ID") == student_id) or (student_name and row.get("学生") == student_name)
        ]
    return {"reports": rows[:120]}


def daily_plan(payload):
    """Build today's tasks from the timeline and the latest mastery state.

    The timeline decides what should be learned today; the ability library
    decides what must be retested today. This keeps a missed knowledge point in
    the loop until it is actually mastered, instead of replaying a diagnosis
    paper each time the page opens.
    """
    student_id = payload.get("studentId", "")
    student_name = payload.get("studentName", "")
    slot = timeline_slot()
    week_text = f"第{slot['week']}周"
    plan_rows = [
        row for row in read_csv(PLAN_PATH, PLAN_HEADERS)
        if row.get("学生") == student_name and row.get("周次") == week_text and row.get("星期") == slot["weekday"]
    ] if slot["isStudyDay"] else []

    abilities = [
        row for row in read_csv(ABILITY_PATH, ["学生", "学生ID", "学科", "知识点ID", "知识点", "答题次数", "正确次数", "错误次数", "连续错误次数", "连续正确次数", "正确率", "状态", "最近更新时间"])
        if row.get("学生ID") == student_id or row.get("学生") == student_name
    ]
    mainline_subject = next((row.get("学科") for row in plan_rows if row.get("是否主线任务") == "是"), "数学")
    priority = {"重点薄弱": 1, "薄弱": 2, "改善中": 3, "未测试": 4}
    candidates = [
        row for row in abilities
        if row.get("状态") != "已掌握" and row.get("知识点ID") in TESTABLE_KNOWLEDGE.get(row.get("学科", ""), set())
    ]
    # First retest the weak knowledge point in today's main subject. If none is
    # available, keep a weak point from another subject moving rather than
    # silently dropping it from the plan.
    same_subject = [row for row in candidates if row.get("学科") == mainline_subject]
    candidates = same_subject or candidates
    candidates.sort(key=lambda row: (priority.get(row.get("状态"), 99), -int(row.get("连续错误次数") or 0), row.get("最近更新时间", "")))
    quiz_subject = candidates[0].get("学科") if candidates else mainline_subject
    quiz_targets = [
        {"knowledgeId": row["知识点ID"], "knowledge": row["知识点"], "status": row["状态"], "consecutiveWrong": int(row.get("连续错误次数") or 0)}
        for row in candidates if row.get("学科") == quiz_subject
    ][:3]

    completed = any(
        row.get("学生ID") == student_id and row.get("日期") == slot["date"]
        for row in completion_rows()
    )
    stage = plan_rows[0].get("阶段", "计划外复盘") if plan_rows else "周日复盘与休整"
    return {
        "taskDate": slot["date"],
        "timelineStartDate": TIMELINE_START_DATE.isoformat(),
        "week": slot["week"],
        "weekday": slot["weekday"],
        "isStudyDay": slot["isStudyDay"],
        "isPreview": slot["preview"],
        "stage": stage,
        "tasks": plan_rows,
        "quizSubject": quiz_subject,
        "quizTargets": quiz_targets,
        "quizId": f"DAILY-{slot['date']}-{student_id}-{quiz_subject}",
        "quizTitle": f"{slot['date']}｜{quiz_subject}滚动复测",
        "completedToday": completed,
        "message": "今天是复盘与休整日，可查看错题解析；明天将自动切换到下一天任务。" if not slot["isStudyDay"] else "今日内容已按 timeline 更新：先完成主线任务，再完成未掌握知识点的滚动复测。",
    }


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
