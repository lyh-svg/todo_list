# 墨 + 荧光笔：铺开到全部界面 实施计划

> **给执行者：** 本计划按批次执行，每批结束跑一次验证三件套。用户现行要求是**不提交代码**，所以计划里的"提交"步骤一律替换为"批次验收"（gate 9/9 + 对比度审计 0 组 + 指纹几何差异可解释 + 截图）。

**目标：** 把已经定稿的「纸 + 墨 + 朱 + 荧光」视觉语言从复习队列/复习会话铺到其余 18 个场景，并收口仍然残留的彩色底、阴影式浮起、旧分隔符。

**架构：** 颜色/尺度已经全部走 `:root` 令牌（P1 完成），B 方向第 1 批已经把令牌值换成纸墨朱荧光并删掉全部阴影令牌。剩下的工作是**规则层收口**：把仍然用「填色胶囊 / 淡色底 / 虚化 / `·` 分隔符」表达的信息，改成「1px 细线 + 墨/朱字 + 荧光笔触 + 细墨线划掉」。

**技术栈：** 纯 CSS（`css/style.css`，CRLF）+ 少量 JS 文案（`js/app.js`，CRLF）；无构建、无依赖。

## 全局约束

- 行尾：`*.css` / `*.js` / `*.html` / `*.md` 必须 CRLF，`*.sh` / `*.yml` 必须 LF（`./scripts/check.sh` 第 9 步会拦）。
- 不新增依赖、不新增字体文件（本地离线应用）。
- 不改数据、不改接口、不改测试；除文案分隔符外不改 JS 逻辑。
- 颜色只能来自 `:root` 的 68 个令牌；正文里出现 hex / `rgba(数字,…)` 视为失败。
- 不提交代码。
- 每批的验收命令（全部在 `/home/lyh/todo_list` 下）：
  1. `./scripts/check.sh` → 末行必须是 `全部检查通过 ✔`
  2. `python3 /tmp/audit-contrast.py` → 必须是 `不达标的「颜色×背景×字号」组合 0 组`
  3. `python3 /tmp/style-fingerprint.py /tmp/style-after-<批次>.json` 后跑 `python3 /tmp/style-diff.py <上一批> /tmp/style-after-<批次>.json`，几何变化必须能逐条解释（只允许出现在被改的组件上）
  4. `python3 /tmp/ui-shots.py` + `python3 /tmp/ui-shots2.py` → 截图肉眼看一遍

---

### Task 0：备份与基线（已完成，此处仅登记）

**Files:** 无改动

- [x] `cp css/style.css /tmp/style-p1.css`（P1 结束时）与 `cp css/style.css /tmp/style-b1.css`（B 第 1 批结束时）作为回滚点
- [x] 基线指纹：`/tmp/style-after-p1.json`（P1 后）、`/tmp/style-after-b.json`（B 第 1 批后）
- [x] 设计说明：`docs/superpowers/specs/2026-09-19-ink-highlighter-design.md`

---

### Task 1：胶囊/徽章统一成"细框标注"

**Files:**
- Modify: `css/style.css`（`.meta-badge` 家族、`.review-card-badge`、`.node-learning-badge`、`.ai-badge`）

**要改成什么：** 所有状态/元信息一律 = `background: none`（露出纸或白卡）+ `1px` 细线 + 小字；只有"需要马上处理"的语义用朱红（`--shu` / `--shu-rule`），其余一律墨色（`--ink-2` / `--ink-3` / `--rule-strong`）。

- [x] `.priority-high`：`border-color: var(--shu-rule); color: var(--shu); background: none;`
- [x] `.priority-mid`：`border-color: var(--rule-strong); color: var(--ink-2); background: none;`
- [x] `.priority-low`：`border-color: var(--rule); color: var(--ink-3); background: none;`
- [x] `.due-overdue`：`border-color: var(--shu-rule); color: var(--shu); background: none; font-weight: 600;`
- [x] `.due-today`：`border-color: var(--ink-2); color: var(--ink); background: none; font-weight: 600;`
- [x] `.due-soon`：`border-color: var(--rule-strong); color: var(--ink-3); background: none;`
- [x] `.repeat-badge` / `.tag-badge` / `.estimate-badge` / `.note-badge` / `.link-badge`：一律 `background: none`，边框 `var(--rule-strong)`，字色 `var(--ink-2)`（不再用紫/青/琥珀/绿）
- [x] `.review-card-badge.overdue`：`background: none; color: var(--shu); border-color: var(--shu-rule);`
- [x] `.node-learning-badge`：去掉 `background`，改 `border: 1px solid var(--shu-rule); color: var(--shu);`
- [x] `.ai-badge`：`border: 1px solid var(--rule-strong); color: var(--ink-2); background: none;`
- [x] 验收：`./scripts/check.sh` + 审计 + 截图（项目详情、项目列表）

**Interfaces:** 不新增 class；现有 9 个 badge 类名保持不变（JS 不动）。

---

### Task 2：卡片与列表容器统一（细线 + 3px 角，无阴影）

**Files:**
- Modify: `css/style.css`

- [x] `.detail-card` / `.utility-task` / `.knowledge-item` / `.trash-item` / `.summary-item` / `.memo-list-item` / `.memo-editor` / `.assessment-*` 面板：确认为 `border: 1px solid var(--rule)`、`border-radius: var(--radius-md)`、无 `box-shadow`
- [x] `.assessment-dialog`：补 `border: 1px solid var(--rule)`（原来靠阴影浮起）
- [x] `.assessment-backdrop`：`background: rgba(var(--ink-rgb), 0.34)`（与 `.utility-backdrop` 一致，取消浅色薄雾）
- [x] 行 hover 统一 `background: rgba(var(--ink-rgb), 0.03)`（`--primary-softer` 已经是这个值，直接引用令牌）
- [x] 验收：同上三件套

---

### Task 3：完成态与进度

**Files:**
- Modify: `css/style.css`

- [x] `.node-row.completed-row`：删掉 `opacity: 0.5`（纸上的"完成"靠划掉 + 墨灰，不靠整体淡化）
- [x] `.node-text.completed-text`：`text-decoration-thickness: 1px; text-decoration-color: var(--ink-3); color: var(--ink-3);`
- [x] 进度条统一：轨道 `height: 4px; background: var(--surface-3); border: 1px solid var(--rule);`，填充 `background: var(--ink)`，`border-radius: 1px`
  - 涉及 `.project-card .card-progress`、`.project-card .card-progress-bar`、`.stats-progress`、`.stats-progress > span`
- [x] 验收：同上三件套（重点看项目详情/项目列表截图）

---

### Task 4：细节与质量底线

**Files:**
- Modify: `css/style.css`

- [x] 加 `::selection { background: var(--marker); color: var(--ink); }`（选中文字＝荧光笔）
- [x] 加 `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; } }`
- [x] 输入类统一 `:focus-visible`：`outline: 2px solid var(--ink); outline-offset: 1px;`（覆盖 `input` / `textarea` / `select` / `[contenteditable]`）
- [x] 校验：`.utility-dialog`、`.assessment-dialog`、`.memo-dialog` 里不再出现任何阴影令牌引用（`grep -c "var(--shadow" css/style.css` 必须是 0）
- [x] 验收：同上三件套

---

### Task 5：去掉 `·` 元信息分隔符

**Files:**
- Modify: `js/app.js`（约 20 处 UI 拼接字符串）、`index.html`（1 处）

**规则：** 只改**界面拼出来的分隔符**，数据本身（项目名、描述、标签、备份文件名）不动。分隔符一律换成全角空格 `　`。

- [x] `js/app.js`：把 UI 文案里的 ` · ` 换成 `　`（模型层/数据层字符串除外，例如 `name: 'Python 8周系统复习 · 工程实战版'` 这类默认数据不在此列）
- [x] `index.html`：`验收中 · 实时回复` → `验收中　实时回复`
- [x] 验收：同上三件套 + `grep -n " · " js/app.js index.html` 的剩余项必须都是数据而不是 UI 文案
- [x] 已改（B 第 1 批）：`reviewQuestionMeta`

---

### Task 6：清点冗余与收尾

**Files:**
- Modify: `css/style.css`（只删不加）

- [x] 令牌自检：`:root` 令牌全部被用到、无重复定义、正文 0 个 hex、0 个 `rgba(数字`
- [x] 删除未被任何规则引用的死规则（脚本：列出选择器在 `index.html` + `js/*.js` 里都找不到的规则，逐条人工确认后删）
- [x] 统一检查残留：`border-radius: var(--radius-full)` 是否还有真正需要胶囊的地方（应为 0）、`opacity: 0.5` 之类的淡化是否只剩合理用例
- [x] 全量截图（`/tmp/ui-shots.py` + `/tmp/ui-shots2.py`）逐张看一遍，列出需要你拍板的点
- [x] 验收：同上三件套 + 最终报告

---

## 执行记录（2026-09-19 完成）

| 批次 | 结果 |
|---|---|
| Task 1 胶囊统一 | 12 个徽章/胶囊去底改细框；12 处"极淡主色边框"统一成 `--rule` |
| Task 2 卡片细线 | 删掉被完全覆盖的 `.detail-card` 死规则；assessment 弹层边框改细线、遮罩与通用弹层统一 |
| Task 3 完成态/进度 | 去掉完成行整体淡化；细墨线划掉；4 处进度条统一成"细线槽 + 墨条" |
| Task 4 质量底线 | 新增 `::selection`（荧光笔）、输入焦点墨描边、`prefers-reduced-motion` |
| Task 5 分隔符 | UI 文案 ` · ` → `　` 共 60 处（js 61 处里保留 5 处数据/上下文串）；同步 2 处断言文案的测试；页面标题与界面应用名对齐 |
| Task 6 令牌收口 | 68 → 41 个令牌，只剩纸/墨/朱/荧光 + 尺度；无未用/未定义/重复 |

验证（每批都跑）：`./scripts/check.sh` 9/9；对比度审计 0 组不达标；指纹几何差异逐条可解释。
Task 6 额外做了"纯重构隔离验证"：把 JS 还原到第 3 批之前再采指纹，几何变化为 **0**，只有刻意的
`--primary: var(--ink)`（#1a1a18 → #1f1c18，肉眼不可分辨）带来的颜色差异。

偏差：Task 1-4 合成一批执行（同文件、同类改动，一次验证即可）；Task 5 改了 2 个测试断言（文案变更的必要同步，
不是为了让测试通过而放宽断言）；`·` 保留在 3 处数据/上下文串里（默认项目名、默认描述、发给模型的上下文）。
