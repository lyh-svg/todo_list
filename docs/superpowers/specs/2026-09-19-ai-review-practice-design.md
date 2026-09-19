# AI 现场出题（复习加练）设计

- 日期：2026-09-19
- 状态：设计已确认，待实施（分两批）
- 涉及文件：`prompts.py`、`ai_service.py`、`review_storage.py`、`storage.py`（建表与迁移）、`local_server.py`、`js/app.js`、`index.html`、`css/style.css`、`tests/`、`scripts/verify-tests-catch.py`、`scripts/check.sh`

## 1. 背景与问题

复习某个知识点时，题目全部来自内容文件 `content/review/py-week*.json` 预置的四种题型（`concept` / `predict` / `debug` / `code_task`），答案是固定文本；`_question_types_by_code()` 只在四种题型之间轮换。练得多了就是同一批题反复出现，没有"针对这个点再考我一道新的"这条路径。

已有的 AI 能力只有两处：`/api/question`（给**任务验收**出 3-5 道题，不产生参考答案）与 `/api/review/ai-grade`（拿**固定参考答案**给你的作答判分）。复习知识点这条线上没有任何 AI 出题能力。

**目标**：在某个知识点上，点一个按钮让 AI 立刻现场出一道新题，当场做；满意可以收进题库，以后和固定题一起参与复习轮换。

## 2. 需求决策（逐条确认）

| # | 问题 | 决策 |
| --- | --- | --- |
| 1 | AI 题的归宿 | **默认临时**（生成→作答→批改→丢弃），**满意再「收进题库」** |
| 2 | 题型 | **AI 自动挑一种**，输出结构仍与现有四种题型一致（不引入选择题等新形式） |
| 3 | 对答案 | **不预生成参考解**：作答后交 AI 批改，AI 一次返回「判分 + 示范解法」；允许空答案/「我不会」，照样给示范解法 |
| 4 | 收藏内容 | 收藏时把这次 AI 给的**示范解法 + 考察点**存为该题的参考解；收藏后与固定题完全同构 |
| 5 | 排期影响 | 临时加练**零留痕**：不写 `review_attempts`、不改 `due`/`weak`、不影响题型轮换与"今日待复习" |
| 6 | 收藏后的位置 | 与固定题**一起参与轮换**（选到"点+题型"后，在固定题 + 已收藏 AI 题里挑最近最少用过的一道） |
| 7 | 入口与查看 | **复习会话卡片** + **知识点浏览页**两个入口；知识点页可查看/删除已收藏的 AI 题 |
| 8 | 出题上下文 | 知识点自身（标题/模块/层级/易错点 + 四种题型的**题面**作风格参考）+ 该点的**作答历史**：最近 5 条 `review_attempts`（题型/档位/日期/你答案的前 200 字）与该点的 `weak` 标记；**没有历史就退化为只用知识点自身** |

配套默认（已确认）：未配置 AI 或调用失败 → 明确提示（服务端 503 + 前端 toast），不静默失败；出题/批改/收藏都有"进行中"禁用态与防重入。

## 3. 方案选择

| 方案 | 内容 | 结论 |
| --- | --- | --- |
| 1 一次做完 | 新表 + `review_attempts` 加列 + 入轮换，一次交付 | 风险集中：AI 出题质量与数据库核心改造绑死 |
| **2 分两批（采用）** | 第一批：出题/批改/收藏 + 两个入口 + 新表（v9→v10），收藏暂不进轮换；第二批：`review_attempts.question_ref` + 轮换改造（v10→v11） | 先用最小代价验证"AI 题值不值得练"，再动复习排期这条核心链路；两批各自可回滚、可演练 |
| 3 只做临时加练 | 一个端点 + 一个按钮，不落库 | 不满足需求 1/6 |

## 4. 数据模型与迁移

### 4.1 第一批：新表（v9 → v10，纯增量 DDL，无回填）

```sql
CREATE TABLE IF NOT EXISTS review_ai_questions (
    question_id   TEXT PRIMARY KEY,          -- uuid
    code          TEXT NOT NULL,             -- 关联知识点，如 py.vars.binding
    question_type TEXT NOT NULL,             -- AI 从四种里挑的那种
    content_json  TEXT NOT NULL,             -- 题面 + 参考解 + 考察点（见 4.3）
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX idx_review_ai_questions_code ON review_ai_questions(code, question_type, created_at);
```

### 4.2 第二批：加"题身份"列（v10 → v11，纯 ADD COLUMN，无回填）

```sql
ALTER TABLE review_attempts ADD COLUMN question_ref TEXT NOT NULL DEFAULT '';
-- '' = 固定题（所有历史行天然正确）；非空 = review_ai_questions.question_id
```

### 4.3 `content_json` 结构（与固定题同构）

```json
{
  "prompt": "题面",
  "code": "要预测/排查的代码（predict/debug 才有）",
  "focus": "考察点一句话",
  "reference": {
    "answer": ["要点"],
    "expected": ["期望输出"],
    "explain": "解释",
    "rootCause": "根因（debug 型）",
    "fix": "修法（debug 型）",
    "reference": "示范解法",
    "pitfalls": ["易错点"]
  }
}
```

`reference` 的键**刻意与 `review_storage.reveal()` 现有返回字段一致**：第二批接进自动复习后，前端「看答案」面板无需改动即可渲染。收藏不保存你那次的原答案（YAGNI）。

### 4.4 轮换规则升级（第二批）

- 粒度仍是"点 + 题型"；选定后候选 = **该题型的固定题 + 该点该题型下已收藏的 AI 题**。
- 每个候选的"最近使用时间" = `review_attempts` 中 `(code, question_type, question_ref)` 的 `MAX(created_at)`；**从未用过的优先**。
- 并列时按确定性顺序（固定题优先，其次 `question_id` 升序）→ 可复现、可断言。
- 已删除的 AI 题不再作为候选；历史 attempts 行保留（统计不丢）；`reveal` 收到指向已删除题的 `questionRef` 时回退到固定题并提示一次。

## 5. 接口与 AI 层

### 5.1 第一批新增接口（进 POST/DELETE 白名单，均需 `X-Todo-Session`）

| 接口 | 入参 | 出参 | 说明 |
| --- | --- | --- | --- |
| `POST /api/review/ai-question` | `{code, questionType?}` | `{ok, question:{prompt, code, focus, questionType}}` | **不含答案**；不落库；未配置 AI → 503；`questionType` 只给测试/调试用，**前端不传**（需求 2：题型由 AI 自行挑） |
| `POST /api/review/ai-answer` | `{code, questionType, prompt, questionCode, focus, answer}` | `{ok, verdict:{correct, summary, missing, wrongAt, hint}, focus, reference:{…}}` | 服务端无状态；`answer` 允许空；不落库 |
| `POST /api/review/ai-collect` | 题面 + 上一步的 `reference` | `{ok, question:{id, code, questionType, createdAt}}` | 校验 `code` 存在于 `review_points`、题型 ∈ 四种、`reference` 的 `reference`(示范解)/`answer`/`expected`/`explain` 至少一项非空；完全相同的题复用已有行（防连点） |
| `GET /api/review/ai-questions` | `code?`（可省略） | `{items:[{id, code, questionType, prompt, code, focus, createdAt}]}` | 省略 `code` 返回全部（知识点页一次拉取渲染所有徽标）；列表**不吐 reference** |
| `DELETE /api/review/ai-question?id=…` | 题 id | `{ok, code, items}` | 与 `/api/memo`、`/api/project` 一致走 `do_DELETE`；未知名 → 404；`items` 是该题所属知识点删除后的剩余列表 |

### 5.2 第二批扩展现有接口（向后兼容）

- `POST /api/review/reveal` 加可选 `questionRef`：非空且存在 → 返回新表里的 `reference`（键与现在一致）；已删除 → 回退固定题并带标记。
- `POST /api/review/answer` 加可选 `questionRef`：写入 `review_attempts.question_ref`。
- `build_queue` 的每个 item 增加 `questionRef`，前端原样回传。

### 5.3 AI 层

- `prompts.py` 新增：
  - `REVIEW_AI_QUESTION_PROMPT`：只出题面，明确"不要给答案"；要求可运行代码/边界/陷阱、markdown 围栏 + 4 空格缩进、风格贴合现有题库；输出 `{"questionType","prompt","code","focus"}`。
  - `REVIEW_AI_ANSWER_PROMPT`：批改 + 示范解法；输入含题面、考察点、你的作答（可为空）、该知识点的固定题面作难度参照；输出 `{"verdict":{…},"focus","reference":{…}}`，要求 `expected`/`explain`/`rootCause`/`fix` 分开给。
- `ai_service.py` 新增 `generate_ai_question()` / `review_ai_answer()`，复用 `_post_json` 的超时、取消与可读错误包装；**输出结构不合格就抛可读错误，绝不返回半成品**。
- `TODO_AI_MOCK=1` 下返回固定样例：离线与 CI（e2e、真浏览器）都靠它，无 key 也能全绿。
- 两处都用 flash 档（与现有"生成复习点"同档）。

### 5.4 失败与降级

| 情况 | 表现 |
| --- | --- |
| 未配置 AI | 503 + 明确提示"未配置 AI，出题/批改不可用（复习本身不受影响）"，与现有 `ai-grade` 一致 |
| 出题超时/失败 | 500/502 + toast，按钮恢复，页面不残留半截题 |
| 批改失败 | 保留已输入的作答，可重试，绝不自动清空 |
| 收藏失败 | 提示，题面与批改结果保留在页面 |
| 防重复 | 出题/批改/收藏各有"进行中"闸门；服务端对收藏再做完全重复去重 |

## 6. 前端交互

状态机（两个入口共用）：`idle → generating → ready(题面) → grading → graded(判分+示范解法) → collected`

### 6.1 入口 1：复习会话卡片（`#reviewSessionView`）

- 「看答案」旁新增 `AI 出道新题`（secondary）。
- 进入加练模式（与当前固定题明确区分）：题面区显示 `AI 加练 · <题型中文名>` 徽标 + `focus`；作答框清空并聚焦。
- **隐藏「看答案」与五档自评**（该题无预置答案；需求 5 决定加练零留痕），换成「提交给 AI 批改」+「放弃加练」。
- 批改中：「AI 正在批改…」禁用态；结果区展示判分 + 示范解法（代码走现有 `reviewBodyBlock` 围栏渲染）+「收进题库」+「再来一题」。
- 收藏成功：按钮变「已收藏（可在知识点页管理）」。
- 「放弃加练」→ 回到当前固定题，草稿用现有 `restoreReviewDraft` 恢复。
- **加练状态不持久化**：刷新后回到当前固定题（有意为之）。

### 6.2 入口 2：知识点页（`#knowledgeView`）

- 每张知识点卡片新增 `AI 出题` 按钮 + `AI 题 N` 徽标（N 来自一次全量 `GET /api/review/ai-questions`）。
- 点 `AI 出题` → 复用现有 `showUtilityModal` 承载同一套状态机，不跳出知识点页。
- 徽标/弹窗内列出该点已收藏的 AI 题（题型 + 题面摘要 +「看参考解」+「删除」），删除后就地刷新列表与徽标。

### 6.3 共享边界

- `renderAiVerdict(container, verdict, reference)`：判分 + 示范解法渲染，两入口共用。
- 请求与状态机函数 `startAiPractice()` / `submitAiAnswer()` / `collectAiQuestion()` / `discardAiPractice()`：两入口共用；复习卡片用固定 id 内联渲染，弹窗用动态 DOM。
- 缓存号：`js/app.js?v=58→59`、`css/style.css?v=36→37`（新增 `.ai-practice-*` 与徽标样式）。

## 7. 测试与验收

| 层 | 覆盖内容 |
| --- | --- |
| 单元（`tests/`） | 收藏/列表/删除/完全重复去重；`code` 不存在、题型非法、`reference` 全空 → 可读错误；列表不吐 reference。轮换（第二批）：候选含 AI 题、从未用过优先、LRU 按 `(code, type, question_ref)`、删除后不再抽中、历史行保留、`question_ref=''` 老语义。迁移：v9→v10、v10→v11 在空库/旧库/重复跑下幂等，迁移前快照 + 失败回滚。AI 层：新 prompt 结构解析（合法/缺字段/非 JSON/超长/危险字段）、mock 样例、网络失败→可读错误，全程假 `urlopen` |
| HTTP 层 | 5 个新端点 200；非法入参 400（不是空回复）；未配置 AI → 503；DELETE 未知 id → 404；第二批 `reveal`/`answer` 带 `questionRef` 的 200 与回退分支 |
| 前端冒烟（`dom-smoke.js`） | 复习卡片全流程 + 隐藏看答案/自评 + `放弃加练` 恢复；知识点页徽标/弹窗/列表/删除；连点只发一次 |
| 端到端 | `e2e-verify.sh` 出题→批改→收藏→列表→删除（mock）；真浏览器在复习会话点一次并收藏，断言 UI 与列表 |
| 反向验证 | ①收藏不存 reference → 收藏/后续 reveal 必须红；②轮换候选不含 AI 题 → 必须红；③"从未用过优先"改成"固定题优先" → 必须红；④未配置 AI 从 503 改成静默 → e2e 必须红 |
| 性能 | 新表按 `(code, question_type, created_at)` 建索引；知识点页一次全量拉取（无 N+1）；轮换沿用批量查询。实测：500 条收藏下列表接口 < 5 ms、构建 50 题队列不慢于现状；复跑 `benchmark_scale.py` 无回归 |

**验收硬断言**

- 第一批：mock 模式离线跑通全流程；**临时加练前后 `review_attempts` / `review_states` 行数与内容逐行不变**；未配置 AI 有明确提示；`./scripts/check.sh` 9/9；真实库只读核对不受影响。
- 第二批：构造"某点只有 AI 题未被用过"的场景，断言自动复习抽中它；作答后 `question_ref` 正确落库；真实库副本上演练 v9→v10→v11（逐行比对无损）；门禁 9/9 + 反向验证全绿。

## 8. 风险与回滚

- 两次迁移都是增量（建表 / 加列 `NOT NULL DEFAULT ''`），失败自动回滚 + 迁移前自动快照（现有机制）。
- 第一批不碰任何现有表 → 出问题删表即可，旧数据零影响。
- 第二批 `question_ref` 默认 `''` → 代码回退后历史行语义仍是"固定题"，不会崩。
- AI 出题质量不可控 → 默认不落库，收藏是主动动作；结构不合格直接报可读错误，不会把烂题写进题库。

## 9. 明确不做（YAGNI）

选择题/判断题等新题型形式；一次出多题；AI 题去重与相似度检测；编辑已收藏的题；把项目里的真实代码喂给出题（需求 8 的 C 档）；临时加练的历史留痕（需求 5）。

## 10. 交付切分

| 批次 | 内容 | 迁移 | 完成标志 |
| --- | --- | --- | --- |
| 第一批 | 出题 / 批改 / 收藏 / 列表 / 删除 + 两个前端入口 | v9→v10（建表） | 零留痕硬断言通过、门禁 9/9、mock 全流程离线可跑 |
| 第二批 | `question_ref` + 轮换改造 + reveal/answer 扩展 | v10→v11（加列） | "抽中 AI 题"验收场景通过、真实库迁移演练无损、门禁 9/9 + 反向验证全绿 |

每批结束后停下来验收，再开下一批。
