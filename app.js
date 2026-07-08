const students = DIAGNOSIS_DATA.students;
const papers = DIAGNOSIS_DATA.papers;
const role = document.body.dataset.role || "entry";
const state = { studentId: students[0].id, paperId: papers[0].id, startedAt: null, timerId: null, elapsedSeconds: 0 };

const $ = (id) => document.getElementById(id);

function currentStudent() {
  return students.find((student) => student.id === state.studentId);
}

function currentPaper() {
  return papers.find((paper) => paper.id === state.paperId);
}

function resultKey(studentId = state.studentId, paperId = state.paperId) {
  return `diagnosis:result:${studentId}:${paperId}`;
}

function answerKey() {
  return `diagnosis:answers:${state.studentId}:${state.paperId}`;
}

function renderOptions() {
  $("studentSelect").innerHTML = students.map((student) => `<option value="${student.id}">${student.name}</option>`).join("");
  const subjects = [...new Set(papers.map((paper) => paper.subject))];
  $("subjectSelect").innerHTML = subjects.map((subject) => `<option value="${subject}">${subject}</option>`).join("");
  renderPaperOptions();
}

function renderPaperOptions() {
  const subject = $("subjectSelect").value || papers[0].subject;
  const subjectPapers = papers.filter((paper) => paper.subject === subject);
  $("paperSelect").innerHTML = subjectPapers.map((paper) => `<option value="${paper.id}">${paper.name}</option>`).join("");
  state.paperId = subjectPapers[0].id;
}

function loadAnswers() {
  try {
    return JSON.parse(localStorage.getItem(answerKey())) || {};
  } catch {
    return {};
  }
}

function saveAnswers() {
  const answers = {};
  document.querySelectorAll("[data-answer]").forEach((field) => {
    answers[field.dataset.answer] = field.value.trim();
  });
  localStorage.setItem(answerKey(), JSON.stringify(answers));
  $("storageStatus").textContent = "已保存";
  return answers;
}

function renderSummary() {
  const paper = currentPaper();
  $("paperNameText").textContent = paper.name;
  $("questionCountText").textContent = `${paper.questions.length} 题`;
  $("totalScoreText").textContent = `${paper.totalScore} 分`;
  $("manualCountText").textContent = "AI自动阅卷";
}

function renderQuestions() {
  const answers = loadAnswers();
  if (!$("questionList")) return;
  $("questionList").innerHTML = currentPaper().questions.map((question) => {
    const options = question.options ? `<div class="options">${question.options.map((option) => `<label class="option"><input type="radio" name="q${question.no}" value="${option[0]}" ${answers[question.no] === option[0] ? "checked" : ""}>${option}</label>`).join("")}</div>` : "";
    const answerBox = question.options ? "" : `<textarea data-answer="${question.no}" placeholder="在这里填写第 ${question.no} 题答案">${answers[question.no] || ""}</textarea>`;
    return `
      <article class="question-card" data-question-card="${question.no}">
        <div class="q-number"><span>题号</span><strong>${question.no}</strong></div>
        <div class="q-body">
          ${metaHtml(question)}
          <p class="prompt">${question.prompt}</p>
          ${options}
          ${answerBox}
        </div>
      </article>
    `;
  }).join("");

  document.querySelectorAll("input[type=radio]").forEach((radio) => {
    radio.addEventListener("change", () => {
      const no = radio.name.replace("q", "");
      const hidden = document.querySelector(`[data-answer="${no}"]`);
      if (hidden) hidden.value = radio.value;
    });
  });

  document.querySelectorAll(".options").forEach((group) => {
    const no = group.closest("[data-question-card]").dataset.questionCard;
    if (!document.querySelector(`[data-answer="${no}"]`)) {
      group.insertAdjacentHTML("afterend", `<input type="hidden" data-answer="${no}" value="${answers[no] || ""}">`);
      group.querySelectorAll("input").forEach((radio) => radio.addEventListener("change", () => {
        document.querySelector(`[data-answer="${no}"]`).value = radio.value;
      }));
    }
  });
}

function metaHtml(question) {
  return `<div class="q-meta"><span>${currentPaper().subject}</span><span>${question.score} 分</span><span>${question.knowledgeId}</span><span>${question.knowledge}</span><span>${question.type}</span><span>${question.difficulty}</span></div>`;
}

async function submitForGrading() {
  const answers = saveAnswers();
  stopTimer();
  $("storageStatus").textContent = "AI阅卷中";
  const resultPanel = $("studentResult");
  if (resultPanel) {
    resultPanel.classList.add("hidden");
    resultPanel.innerHTML = "";
  }
  try {
    const response = await fetch("/api/grade", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student: currentStudent(), paper: currentPaper(), answers, elapsedSeconds: state.elapsedSeconds }),
    });
    if (!response.ok) throw new Error("AI阅卷接口未启动");
    const result = await response.json();
    result.createdAt = new Date().toISOString();
    localStorage.setItem(resultKey(), JSON.stringify(result));
    $("storageStatus").textContent = "已完成阅卷";
    renderStudentResult(result);
  } catch {
    const message = "AI阅卷失败，请检查本地服务是否启动。";
    $("storageStatus").textContent = message;
    if (resultPanel) {
      resultPanel.classList.remove("hidden");
      resultPanel.innerHTML = `<div class="error-panel">${message}</div>`;
    }
    alert(message);
  }
}

function renderStudentResult(result) {
  $("studentResult").classList.remove("hidden");
  $("studentResult").innerHTML = `<h2>阅卷结果：${result.totalScore} / ${result.paperTotal}</h2><p>用时：${formatDuration(result.elapsedSeconds || 0)}</p>${result.items.map(itemHtml).join("")}`;
  $("studentResult").scrollIntoView({ behavior: "smooth", block: "start" });
}

function itemHtml(item) {
  return `<article class="result-card">
    <strong>第 ${item.no} 题：${item.score} / ${item.fullScore}</strong>
    <p><b>学生答案：</b>${item.studentAnswer || "未作答"}</p>
    <p><b>正确答案：</b>${item.correctAnswer}</p>
    <p><b>评分标准：</b>${item.rubric}</p>
    <p><b>解析：</b>${item.explanation}</p>
    <p><b>AI扣分原因：</b>${item.deductionReason}</p>
    <p><b>错误类型：</b>${item.errorType || "无"}｜<b>错误知识点：</b>${item.errorKnowledge || "无"}</p>
    <p><b>知识点ID：</b>${item.knowledgeId}｜<b>知识点名称：</b>${item.knowledgeName}</p>
    <p><b>知识点简明讲解：</b>${item.knowledgeExplanation}</p>
    <p><b>知识点掌握情况：</b>${item.mastery}</p>
    <p><b>补救建议：</b>${item.suggestion}</p>
    <p><b>推荐学习链接：</b><a href="${item.bilibiliLink}" target="_blank" rel="noreferrer">B站搜索</a>｜<a href="${item.publicCourseLink}" target="_blank" rel="noreferrer">公开课搜索</a>｜关键词：${item.publicCourseKeyword}</p>
  </article>`;
}

function renderParentReport() {
  const reports = [];
  students.forEach((student) => {
    papers.forEach((paper) => {
      const raw = localStorage.getItem(resultKey(student.id, paper.id));
      if (raw) reports.push(JSON.parse(raw));
    });
  });
  $("parentReport").innerHTML = reports.length ? reports.map(reportHtml).join("") : "<p class='empty'>暂无测试结果。</p>";
}

async function renderProgressConsole() {
  const target = $("progressConsole");
  if (!target) return;
  target.innerHTML = "<p class='empty'>正在生成进度控制台...</p>";
  try {
    const response = await fetch("/api/progress", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ studentId: state.studentId, studentName: currentStudent().name }),
    });
    if (!response.ok) throw new Error("progress failed");
    const data = await response.json();
    target.innerHTML = progressHtml(data);
    bindBudgetControl();
  } catch {
    target.innerHTML = "<p class='error-panel'>进度控制台加载失败，请检查本地服务是否启动。</p>";
  }
}

function progressHtml(data) {
  const cards = [
    ["当前阶段", `第${data.currentWeek}周｜${data.currentStage}`],
    ["主线完成率", `${data.mainlineCompletionRate}%`],
    ["薄弱积压量", `${data.weakBacklogCount} 个`],
    ["已掌握", `${data.masteredCount} 个`],
    ["未掌握", `${data.unmasteredCount} 个`],
    ["8周完成判断", data.canCompleteIn8Weeks ? "预计可完成" : "存在延期风险"],
    ["进度偏离", data.progressDeviation],
    ["目标风险", data.target.riskLevel],
  ].map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`).join("");
  const weeks = data.heatmap.weeks.map((week) => `<span>${week}</span>`).join("");
  const rows = data.heatmap.subjects.map((subject) => `
    <div class="heat-subject">${subject}</div>
    ${data.heatmap.cells[subject].map((cell) => `
      <div class="heat-cell ${cell.riskClass}">
        <b>${cell.mainlineCompletionRate}%</b>
        <span>弱${cell.weakCount}｜掌${cell.masteredCount}｜未${cell.unmasteredCount}</span>
      </div>
    `).join("")}
  `).join("");
  return `
    <section class="dashboard-cards">${cards}</section>
    <section class="target-line">
      <h3>无锡中考基础平均线目标</h3>
      <p>当前估算能力分：<b>${data.target.currentScore}</b> / 750｜目标能力线：<b>${data.target.targetScore}</b>｜差距：<b>${data.target.gap}</b>｜风险等级：<b>${data.target.riskLevel}</b></p>
    </section>
    <section class="budget-panel">
      <h3>每日学习预算</h3>
      <label>预算设置
        <select id="budgetSelect">
          ${[90, 120, 135, 180].map((minutes) => `<option value="${minutes}" ${data.budgetMinutes === minutes ? "selected" : ""}>${minutes}分钟</option>`).join("")}
        </select>
      </label>
      <button id="applyBudgetBtn" type="button">按预算重新生成后续任务</button>
      <p id="budgetStatus">当前预算：${data.budgetMinutes}分钟。预算只影响题量和复盘深度，不取消8周主线timeline。</p>
    </section>
    <section class="heatmap-panel">
      <h3>8周知识热力图</h3>
      <div class="heatmap"><div></div>${weeks}${rows}</div>
    </section>
  `;
}

function bindBudgetControl() {
  $("applyBudgetBtn")?.addEventListener("click", async () => {
    const minutes = Number($("budgetSelect").value);
    $("budgetStatus").textContent = "正在按新预算重新分配任务...";
    const response = await fetch("/api/budget", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ budgetMinutes: minutes }),
    });
    if (!response.ok) {
      $("budgetStatus").textContent = "预算调整失败，请检查本地服务。";
      return;
    }
    const data = await response.json();
    $("budgetStatus").textContent = `已重新生成任务：每日预算${data.budgetMinutes}分钟，每日最大时长${data.maxDailyMinutes}分钟，主线timeline保留。`;
    renderProgressConsole();
  });
}

function reportHtml(report) {
  const allItems = report.items.map(itemHtml).join("");
  return `<section class="report-block"><h2>${report.studentName}｜${report.subject}｜${report.totalScore}/${report.paperTotal}</h2><p>用时：${formatDuration(report.elapsedSeconds || 0)}</p><h3>每题AI阅卷详情</h3>${allItems}<h3>今日任务</h3><p>${report.todayTask}</p><h3>后续补弱建议</h3><p>${report.nextPlan}</p><h3>学习趋势</h3><p>${report.trend}</p></section>`;
}

function switchMode(mode) {
  const studentPanel = $("studentPanel");
  const reviewPanel = $("reviewPanel");
  if (studentPanel) studentPanel.classList.toggle("hidden", mode !== "student");
  if (reviewPanel) reviewPanel.classList.toggle("hidden", mode !== "review");
}

function bindEvents() {
  $("studentSelect")?.addEventListener("change", (event) => { state.studentId = event.target.value; loadCurrent(); });
  $("subjectSelect")?.addEventListener("change", () => { renderPaperOptions(); loadCurrent(); });
  $("paperSelect")?.addEventListener("change", (event) => { state.paperId = event.target.value; loadCurrent(); });
  $("startBtn")?.addEventListener("click", startTest);
  $("saveBtn")?.addEventListener("click", saveAnswers);
  $("submitBtn")?.addEventListener("click", submitForGrading);
}

function startTest() {
  state.startedAt = Date.now();
  state.elapsedSeconds = 0;
  clearInterval(state.timerId);
  renderTimer();
  state.timerId = setInterval(() => {
    state.elapsedSeconds = Math.floor((Date.now() - state.startedAt) / 1000);
    renderTimer();
  }, 1000);
  $("storageStatus").textContent = "测试中";
}

function stopTimer() {
  if (state.startedAt) {
    state.elapsedSeconds = Math.floor((Date.now() - state.startedAt) / 1000);
  }
  clearInterval(state.timerId);
  renderTimer();
}

function renderTimer() {
  if ($("timerText")) $("timerText").textContent = formatDuration(state.elapsedSeconds);
}

function formatDuration(seconds) {
  const minutes = String(Math.floor(seconds / 60)).padStart(2, "0");
  const rest = String(seconds % 60).padStart(2, "0");
  return `${minutes}:${rest}`;
}

function loadCurrent() {
  renderSummary();
  renderQuestions();
}

function initStudent() {
  renderOptions();
  bindEvents();
  loadCurrent();
}

function initParent() {
  renderOptions();
  bindEvents();
  loadCurrent();
  switchMode("review");
  renderProgressConsole();
  renderParentReport();
}

if (role === "student") initStudent();
if (role === "parent") initParent();
