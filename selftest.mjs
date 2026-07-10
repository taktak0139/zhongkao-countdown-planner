import fs from "node:fs";
import vm from "node:vm";

const BASE_URL = process.env.TEST_BASE_URL || "http://127.0.0.1:8080";
const abilityPath = "./data/学生能力库.csv";
const videoPath = "./data/薄弱知识点视频推荐.csv";
const dailyHistoryPath = "./data/每日试卷历史记录.csv";
const dataCode = fs.readFileSync("./data.js", "utf8");
const appCode = fs.readFileSync("./app.js", "utf8");
const studentHtml = fs.readFileSync("./student.html", "utf8");
const parentHtml = fs.readFileSync("./parent.html", "utf8");
const reportsPath = "./reports";
const protectedDataPaths = [abilityPath, videoPath, dailyHistoryPath];
const originalData = new Map(protectedDataPaths.map((path) => [path, fs.existsSync(path) ? fs.readFileSync(path) : null]));
const originalReports = new Set(fs.existsSync(reportsPath) ? fs.readdirSync(reportsPath) : []);
const context = {};
vm.runInNewContext(`${dataCode}\nglobalThis.DIAGNOSIS_DATA = DIAGNOSIS_DATA;`, context);

const student = { id: "SELFTEST", name: "自测学生" };
const paper = context.DIAGNOSIS_DATA.papers.find((item) => item.id === "PAPER-MATH-001");
const physicsPaper = context.DIAGNOSIS_DATA.papers.find((item) => item.id === "PAPER-PHY-001");

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function fullAnswer(question) {
  if (question.grading === "objective") return question.answer;
  return question.keywords?.join(" ") || question.answer;
}

function cleanSelftestRows(path) {
  if (!fs.existsSync(path)) return;
  const lines = fs.readFileSync(path, "utf8").split(/\r?\n/).filter(Boolean);
  if (!lines.length) return;
  const header = lines[0];
  const kept = lines.slice(1).filter((line) => !line.includes("自测学生") && !line.includes("SELFTEST") && !line.includes("物理边界自测"));
  fs.writeFileSync(path, [header, ...kept].join("\n") + "\n", "utf8");
}

function cleanSelftestReports() {
  if (!fs.existsSync(reportsPath)) return;
  for (const name of fs.readdirSync(reportsPath)) {
    if (!originalReports.has(name) && name.includes("自测学生") && name.endsWith(".md")) fs.rmSync(`${reportsPath}/${name}`);
  }
}

function restoreSelftestData() {
  for (const [path, content] of originalData) {
    if (content === null) {
      if (fs.existsSync(path)) fs.rmSync(path);
    } else {
      fs.writeFileSync(path, content);
    }
  }
  cleanSelftestReports();
}

process.on("exit", restoreSelftestData);

function csvRows(path) {
  if (!fs.existsSync(path)) return [];
  const lines = fs.readFileSync(path, "utf8").replace(/^\uFEFF/, "").split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return [];
  const headers = lines[0].split(",");
  return lines.slice(1).map((line) => {
    const cells = line.split(",");
    return Object.fromEntries(headers.map((header, index) => [header, cells[index] || ""]));
  });
}

function difficultyLevel(question) {
  if (Number.isFinite(Number(question.difficulty_level))) return Number(question.difficulty_level);
  if (question.difficulty === "基础") return 1;
  if (question.difficulty === "中档") return 2;
  if (question.difficulty === "综合") return 3;
  return 4;
}

function availableQuestions(paperItem) {
  return [...paperItem.questions]
    .filter((question) => question.is_available_for_grade8_summer !== false)
    .sort((a, b) => difficultyLevel(a) - difficultyLevel(b) || Number(a.no) - Number(b.no));
}

async function postJson(path, payload) {
  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    console.error("无法连接测试服务器，请先启动 python3 server.py");
    process.exit(1);
  }
  assert(response.ok, `${path}: 接口未返回 200`);
  return response.json();
}

async function getText(path) {
  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`);
  } catch {
    console.error("无法连接测试服务器，请先启动 python3 server.py");
    process.exit(1);
  }
  assert(response.ok, `${path}: 页面打不开`);
  return response.text();
}

async function grade(name, answers, expected) {
  const result = await postJson("/api/grade", { student, paper, answers, elapsedSeconds: 90 });
  assert(result.dailyReport?.path, `${name}: 未返回日报路径`);
  assert(fs.existsSync(`./${result.dailyReport.path}`), `${name}: 日报文件未落盘`);
  assert(typeof result.totalScore === "number", `${name}: 缺少总分`);
  assert(result.elapsedSeconds === 90, `${name}: 用时未写入`);
  assert(result.items.length === paper.questions.length, `${name}: 每题结果数量不一致`);
  for (const item of result.items) {
    assert("studentAnswer" in item, `${name}: 缺少学生答案`);
    assert(item.correctAnswer, `${name}: 缺少正确答案`);
    assert(item.rubric, `${name}: 缺少评分标准`);
    assert(item.explanation, `${name}: 缺少解析`);
    assert("deductionReason" in item, `${name}: 缺少AI扣分原因`);
    assert("errorType" in item, `${name}: 缺少错误类型`);
    assert(item.knowledgeId, `${name}: 缺少知识点ID`);
    assert(item.knowledgeName, `${name}: 缺少知识点名称`);
    assert(item.knowledgeExplanation && item.knowledgeExplanation.length >= 80, `${name}: 知识点讲解过短`);
    assert(item.mastery, `${name}: 缺少知识点掌握情况`);
    assert(item.suggestion, `${name}: 缺少补救建议`);
    assert(item.bilibiliLink?.startsWith("https://search.bilibili.com/all?keyword="), `${name}: B站链接缺失`);
    assert(item.publicCourseKeyword, `${name}: 公开课关键词缺失`);
    assert(item.publicCourseLink, `${name}: 公开课链接缺失`);
    assert(item.textbookVersion === "苏教版", `${name}: 教材版本不是苏教版`);
    assert(item.resourceStatus === "pending_review", `${name}: 未确认资源没有标记为pending_review`);
    assert(item.resourceTitle?.includes("苏教版八年级"), `${name}: 资源标题未适配苏教版八年级`);
  }
  expected(result);
  return result;
}

cleanSelftestRows(abilityPath);
cleanSelftestRows(videoPath);
cleanSelftestRows(dailyHistoryPath);
cleanSelftestReports();

assert(context.DIAGNOSIS_DATA.config?.learned_until === "初二下学期结束", "缺少初二下学期结束知识边界配置");
const physicsAvailable = availableQuestions(physicsPaper);
assert(!physicsAvailable.some((question) => ["P403", "P404"].includes(question.knowledgeId)), "物理可用测试仍包含初三电学内容");
assert(physicsAvailable.every((question) => question.is_available_for_grade8_summer !== false), "物理可用题包含被排除题");
assert(physicsAvailable.reduce((sum, question) => sum + Number(question.score || 0), 0) === 100, "物理初二可用试卷不是100分");
assert(physicsAvailable.every((question, index, array) => index === 0 || difficultyLevel(array[index - 1]) <= difficultyLevel(question)), "物理题目未按由浅入深排序");

const allCorrectAnswers = Object.fromEntries(paper.questions.map((question) => [question.no, fullAnswer(question)]));
const partialAnswers = { ...allCorrectAnswers, "1": "B", "4": "x=5" };
const emptyAnswers = {};

const allCorrect = await grade("全对测试", allCorrectAnswers, (result) => {
  assert(result.totalScore === paper.totalScore, "全对测试: 总分不是100");
});

const partial = await grade("部分错误测试", partialAnswers, (result) => {
  assert(result.totalScore > 0 && result.totalScore < paper.totalScore, "部分错误测试: 分数不在预期范围");
  const m001 = result.items.find((item) => item.knowledgeId === "M001");
  const m002 = result.items.find((item) => item.knowledgeId === "M002");
  assert(m001.score === 0, "M001 答错未形成扣分");
  assert(m001.knowledgeExplanation, "M001 未显示知识点讲解");
  assert(m001.bilibiliLink, "M001 未显示B站链接");
  assert(m002.score === m002.fullScore, "M002 答对未满分");
});

const abilityRowsAfterPartial = csvRows(abilityPath).filter((row) => row["学生ID"] === "SELFTEST");
const m001Ability = abilityRowsAfterPartial.find((row) => row["知识点ID"] === "M001");
const m002Ability = abilityRowsAfterPartial.find((row) => row["知识点ID"] === "M002");
assert(m001Ability?.["状态"] === "薄弱", "M001 未写入能力库为薄弱");
assert(m002Ability?.["状态"] === "已掌握", "M002 未按规则进入已掌握");

const videoRows = csvRows(videoPath).filter((row) => row["学生"] === "自测学生");
const m001Video = videoRows.find((row) => row["知识点ID"] === "M001");
assert(m001Video?.["B站搜索链接"]?.startsWith("https://search.bilibili.com/all?keyword="), "M001 视频推荐未写入B站链接");
assert(m001Video?.["教材版本"] === "苏教版", "M001 视频推荐未写入苏教版字段");
assert(m001Video?.["资源状态"] === "pending_review", "M001 视频推荐未标记pending_review");
assert(m001Video?.["公开课搜索关键词"]?.includes("苏教版 八年级 初中 数学 有理数混合运算"), "M001 公开课关键词不正确");

const dailyTasks = await postJson("/api/tasks", { studentId: "SELFTEST", subject: "数学", testType: "日常测试", paper });
assert(dailyTasks.tasks.some((task) => task["知识点ID"] === "M001"), "日常任务未优先包含薄弱 M001");
assert(!dailyTasks.tasks.some((task) => task["知识点ID"] === "M002"), "日常任务未过滤已掌握 M002");
assert(dailyTasks.tasks[0]["状态"] === "薄弱" || dailyTasks.tasks[0]["状态"] === "重点薄弱", "日常任务未按薄弱优先排序");

const mockTasks = await postJson("/api/tasks", { studentId: "SELFTEST", subject: "数学", testType: "综合模拟", paper });
assert(mockTasks.tasks.some((task) => task["知识点ID"] === "M002"), "综合模拟未允许已掌握 M002");

const empty = await grade("空题测试", emptyAnswers, (result) => {
  assert(result.totalScore === 0, "空题测试: 总分不是0");
  assert(result.items.every((item) => item.studentAnswer === "未作答"), "空题测试: 未作答字段异常");
});

const parentPage = await getText("/parent.html");
const studentPage = await getText("/student.html");
assert(parentPage.includes("进度控制台"), "家长端未进入进度控制台");
assert(parentPage.includes("progressConsole"), "家长端缺少进度控制台容器");
assert(studentPage.includes("submitBtn"), "学生端考试提交按钮丢失");

const progress = await postJson("/api/progress", { studentId: "S001", studentName: "李悦嘉" });
assert(progress.heatmap?.weeks?.length === 8, "8周知识热力图周数不正确");
assert(progress.heatmap?.subjects?.includes("数学"), "8周知识热力图缺少数学");
assert(typeof progress.mainlineCompletionRate === "number", "主线进度缺失");
assert(typeof progress.weakBacklogCount === "number", "薄弱积压量缺失");
assert(progress.target?.name === "无锡中考基础平均线目标", "基础平均线目标缺失");

const budgetResult = await postJson("/api/budget", { budgetMinutes: 120 });
assert(budgetResult.timelinePreserved === true, "预算调整破坏timeline标记");
assert(budgetResult.maxDailyMinutes <= 120, "预算调整后每日时长超过120");
const progressAfterBudget = await postJson("/api/progress", { studentId: "S001", studentName: "李悦嘉" });
assert(progressAfterBudget.budgetMinutes === 120, "预算调整后进度模型未读取新预算");
const restoredBudget = await postJson("/api/budget", { budgetMinutes: 135 });
assert(restoredBudget.budgetMinutes === 135, "自测后未恢复默认135分钟预算");

assert(studentHtml.includes('id="studentResult"'), "学生端缺少AI阅卷结果区");
assert(studentHtml.includes('id="submitBtn"'), "学生端缺少提交按钮");
assert(!studentHtml.includes("评分标准</summary>"), "学生端HTML考试中暴露评分标准");
assert(!appCode.includes("<details><summary>评分标准"), "答题渲染仍暴露评分标准");
assert(appCode.includes("知识点简明讲解"), "学生端未渲染知识点讲解");
assert(appCode.includes("推荐学习链接"), "学生端未渲染推荐学习链接");
assert(appCode.includes("zhongkao_test_history"), "学生端未使用清晰的历史记录localStorage key");
assert(studentHtml.includes("历史试卷"), "学生端缺少历史试卷入口");
assert(studentHtml.includes("查看上次测试结果"), "学生端缺少上次测试结果入口");
assert(appCode.includes("saveTestHistory"), "学生端提交后未保存历史测试记录");
assert(appCode.includes("AI阅卷失败，请检查本地服务是否启动。"), "AI失败提示文案缺失");
assert(parentHtml.includes('id="parentReport"'), "家长端缺少报告区");
assert(parentHtml.includes('id="progressConsole"'), "家长端缺少进度控制台");
assert(appCode.includes("每题AI阅卷详情"), "家长端未显示每题AI阅卷详情标题");
assert(appCode.includes("report.items.map(itemHtml)"), "家长端不是全部题目阅卷详情");
assert(appCode.includes("8周知识热力图"), "家长端未渲染8周知识热力图");
assert(appCode.includes("无锡中考基础平均线目标"), "家长端未渲染基础平均线目标");
assert(appCode.includes("/api/budget"), "家长端未接入预算调整接口");

assert(fs.existsSync(reportsPath), "reports 目录不存在");
assert(fs.readdirSync(reportsPath).some((name) => name.endsWith(".md")), "日报未正常生成");

cleanSelftestRows(abilityPath);
cleanSelftestRows(videoPath);
cleanSelftestRows(dailyHistoryPath);
cleanSelftestReports();

console.log(JSON.stringify({
  ok: true,
  allCorrect: { totalScore: allCorrect.totalScore, items: allCorrect.items.length },
  partial: { totalScore: partial.totalScore, items: partial.items.length, m001Status: m001Ability["状态"], m002Status: m002Ability["状态"] },
  empty: { totalScore: empty.totalScore, items: empty.items.length },
  knowledgeDisplay: true,
  videoLinks: true,
  abilityWrite: true,
  masteredFilter: true,
  mockAllowsMastered: true,
  parentDetails: true,
  progressConsole: true,
  heatmap: true,
  budgetAdjust: true,
  budgetRestored: true,
  studentFlowIntact: true
  ,
  gradeScope: true,
  historyStorage: true,
  sujiaoResources: true
}, null, 2));
