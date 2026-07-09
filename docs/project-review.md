# 项目健康检查报告

## 当前状态

项目当前是一个本地运行的 AI 中考学习规划 Prototype，核心链路已经具备：入口页、学生诊断测试、自动阅卷、历史测试记录、家长进度控制台、8 周暑期任务计划、能力库 CSV、视频资源推荐 CSV、社区参与文档和 GitHub Issue / PR 模板。

整体结构适合原型阶段：HTML / CSS / JS / Python / CSV 的组合简单直接，方便家长、老师和开发者理解。但如果准备作为公开 GitHub 项目长期维护，当前仍有一些开源卫生、隐私、安全边界和可维护性问题需要处理。

本次审查只读检查了项目结构、开源文档、前端代码、数据结构、Python 服务和自测脚本；没有修改业务代码、数据文件或已有文档。

## 做得好的地方

- 项目定位清晰：README、CONTRIBUTING、ROADMAP 都强调这是面向普通家庭的开源原型，而不是成熟商业产品。
- 开源基础文件较完整：已有 LICENSE、CONTRIBUTING、ROADMAP、CHANGELOG、SECURITY、CODE_OF_CONDUCT、Issue 模板和 PR 模板。
- 主流程可读性好：`index.html`、`student.html`、`parent.html` 分工清楚，`app.js` 承担前端状态与渲染，`server.py` 承担本地 API。
- 初二下知识边界已开始显式建模：`data.js` 中有 `grade_scope`、`learned_until`、`is_available_for_grade8_summer`，物理超纲内容也保留但默认排除。
- 苏教版资源机制方向正确：资源增加了教材版本和 `pending_review` 状态，避免误导家长直接点击未经审核的链接。
- 自测覆盖了关键路径：`selftest.mjs` 覆盖阅卷、知识边界、能力库写入、视频推荐、家长端进度、预算调整、历史记录字段等。
- `.gitignore` 已包含 `__pycache__/`、`*.pyc`、`.DS_Store`、`README.old.md`，说明项目已经意识到临时文件不应提交。

## 潜在问题

### P0：必须修复

1. 公开仓库中不应包含真实学生姓名。
   - 位置：`data.js` 的 `students`、`data/学生暑期任务计划.csv`、`generate_summer_plan.py` 的 `STUDENTS`。
   - 风险：项目文档明确提醒不要提交学生隐私，但当前样例数据使用了真实中文姓名。即使只是家庭内部原型，公开 GitHub 前也应改成“学生A / 学生B”或示例 ID。
   - 建议：公开前统一脱敏，并在 README 中说明如何在本地替换为真实姓名。

2. 本地 API 缺少请求异常处理，异常输入可能导致服务直接报错。
   - 位置：`server.py` 的 `do_POST()`、`grade()`、`apply_budget()` 等入口。
   - 风险：JSON 解析失败、缺少字段、字段类型错误时可能抛异常，导致用户只看到请求失败；作为家庭本地工具可以接受原型状态，但上线测试阶段应至少返回结构化错误。
   - 建议：为 API 增加最小 try/except、400 错误响应和清晰错误文案。

### P1：建议近期修复

1. 项目目录中存在不应提交的临时或备份文件。
   - 发现：`__pycache__/`、`*.pyc`、`docs/.DS_Store`、`README.old.md`。
   - 备注：这些已被 `.gitignore` 覆盖，但仍存在于工作目录。公开前建议确认未被 Git 跟踪，并清理本地目录。

2. 前端存在未绑定或遗留按钮，容易造成用户困惑。
   - 位置：`student.html` 中 `exportBtn`、`saveReviewBtn`、`exportReviewBtn`、`exportSummaryBtn`、`clearBtn`；`parent.html` 中 `clearBtn`。
   - 现象：当前 `app.js` 未看到对应事件绑定。用户点击后可能无反应。
   - 建议：要么补齐功能和测试，要么在当前原型阶段隐藏未完成入口。

3. `innerHTML` 直接渲染题目、答案和结果，未来接入外部题库或用户生成内容时有 XSS 风险。
   - 位置：`app.js` 的 `renderQuestions()`、`renderStudentResult()`、`itemHtml()`、`renderHistoryPanel()`、`progressHtml()`。
   - 风险：当前数据主要来自本地静态文件，风险可控；一旦允许外部题库、Issue 导入或用户填写内容回显，就需要转义。
   - 建议：增加统一的 HTML escape 工具，或改用 DOM API 创建节点。

4. 家长端依赖同一浏览器 `localStorage`，跨设备无法看到学生端提交记录。
   - 位置：`app.js` 的 `renderParentReport()`。
   - 影响：如果孩子用 iPad 测试、家长用 Mac 查看，历史记录不会自动同步。
   - 建议：README 或页面中明确“同一设备/同一浏览器保存”；如果后续要跨设备，再设计同步方案。

5. `server.py` 的阅卷并不是真正 AI 阅卷，而是关键词和客观题规则评分。
   - 风险：产品文案里大量使用“AI阅卷”，但当前实现更接近本地规则阅卷。
   - 建议：文档或界面注明“当前为本地规则阅卷原型”；真正接入 AI 服务时再更新能力说明。

6. 学科和教材字段覆盖不均。
   - 位置：`data.js`。
   - 现象：物理题目已有 `difficulty_level`、`grade_scope`、`learned_until`、`is_available_for_grade8_summer`；其他学科多数字段仍缺失，依赖运行时默认值。
   - 建议：补齐四科统一 schema，减少后续扩展时的隐性规则。

7. `generate_summer_plan.py` 和 `data.js` 存在知识点重复维护。
   - 风险：试卷知识点、任务计划知识点、资源知识点分别维护，容易出现 ID 不一致、名称不一致、边界不一致。
   - 建议：中期把知识点库抽成一个单独数据源，再由试卷、计划和资源引用。

8. `apply_budget()` 会直接改写整份任务计划。
   - 位置：`server.py`。
   - 风险：每次预算调整会替换 `45分钟任务内容` 里的文字和预计时长，反复调整后不易追踪原始计划。
   - 建议：保留原始模板字段，预算调整生成派生视图或写入单独配置。

### P2：长期优化

1. README 与 ROADMAP 的未来方向存在轻微张力。
   - README 提到“教师模式”“云端同步”等较远目标；ROADMAP 又强调暂不做复杂用户系统、不包装成成熟产品。
   - 建议：后续统一表达，把远期想法放在“远期探索”，近期路线保持克制。

2. 数据目录缺少 schema 说明。
   - 位置：`data/*.csv`。
   - 建议：新增 `docs/data-schema.md` 或在 README 增加字段说明，解释能力库、任务计划、视频推荐、预算配置各字段含义。

3. 测试依赖固定局域网地址。
   - 位置：`selftest.mjs` 的 `baseUrl = "http://192.168.1.129:8080"`。
   - 影响：换机器或网络后测试可能失败。
   - 建议：支持环境变量，例如 `BASE_URL=http://localhost:8080 node selftest.mjs`。

4. 自测会写入 CSV 后再清理，仍有中途失败残留风险。
   - 位置：`selftest.mjs`。
   - 建议：测试前备份相关 CSV，测试后无论成功失败都恢复，或使用测试专用临时数据目录。

5. `server.py` 目前没有鉴权和 CSRF 防护。
   - 原型本地运行可接受，但如果暴露到局域网或公网，任何访问者都可以 POST 修改数据。
   - 建议：继续保持本地使用定位；如需局域网多人访问，至少增加简单访问控制和来源限制。

6. 页面可访问性仍可提升。
   - 例如按钮状态、错误提示、表单说明、键盘导航、提交中 loading、防重复提交等。
   - 这些不是当前原型的阻塞项，但会影响真实家庭使用体验。

7. GitHub 文档可进一步补充运行方式。
   - README 目前故事性很好，但本地启动、测试、目录说明、已知限制还可以更结构化。
   - 建议后续增加“快速开始”“如何运行自测”“隐私与本地数据说明”。

## 推荐下一步计划

1. 公开发布前先做隐私脱敏。
   - 把所有真实学生姓名替换为示例名。
   - 检查 CSV、截图、README 图片中是否包含隐私信息。

2. 清理临时文件并确认 Git 状态。
   - 确认 `__pycache__/`、`.DS_Store`、`README.old.md` 未被提交。
   - 保留 `.gitignore` 当前规则。

3. 补齐 P1 中的“无反应按钮”。
   - 最小方案：隐藏未完成按钮。
   - 更完整方案：补齐导出、清空、家长阅卷相关功能，并写入自测。

4. 统一数据 schema。
   - 先补齐四科题目的 `difficulty_level`、`grade_scope`、`learned_until`、`textbook_version`、`region` 或类似字段。
   - 再考虑把知识点库从 `data.js` 和 `generate_summer_plan.py` 中抽离。

5. 给 `server.py` 增加最小错误处理。
   - 保持本地原型简单结构，不引入框架。
   - 至少保证坏请求不会导致服务崩掉，并给前端明确错误提示。

6. 增强自测。
   - 增加无效请求测试。
   - 增加前端按钮存在但未绑定的静态检查。
   - 增加跨学生、跨学科历史记录筛选测试。
   - 让 `baseUrl` 可配置。

## 不修改原因说明

本次任务是 Senior Code Reviewer 视角的完整代码审查和项目健康检查，不是开发任务。

因此本次没有修改任何业务代码、产品逻辑、数据文件或已有文档；只新增了本报告文件：

- `docs/project-review.md`

所有发现均以审查建议形式记录，方便后续按优先级单独拆分 Issue 或 PR。
