# Python 复习内容与复习会话 · 规划（第 7 批）

- 状态：**待你最终确认**（确认后转实施计划）
- 日期：2026-09-16（v2：粒度合并到"半小时一个知识点"、存储改为扩展主库）
- 骨架：你的真实 8 周计划（8 周 × 5 单元 × 21 任务 = 168 个任务）

## 0. 一页结论

1. **不另起课程目录**：知识点从你现有 168 个任务里拆出来，知识点记 `taskRefs`（来自哪些任务），完成任务时按它精确生成复习项。
2. **粒度**：一个知识点 = **半小时内能拿下**（10～30 分钟），适当合并；复习时**一次只出 1 道题**（2～3 分钟），按题型轮换。
2b. **覆盖优先（你的取向：目的是学习）**：知识点与题目**宁多勿漏**——任务涉及的机制必须覆盖到，额外补一些相关知识点也没问题；五类题是**最低配置**，同一个点可以有多道变体题。
3. **规模**：第 1 周合并后 **40 个知识点 / ≥200 道题**（五类题是下限，按覆盖优先可加变体）；全 8 周约 **260～320 个知识点 / 约 1300～1600 道题**。
4. **这一批（第 7 批）**：复习引擎 + 第 1 周全部内容（含任务隐含但必需的前置）。
5. **存储**：扩展**原来的库**（`data/todo.sqlite3`，`SCHEMA_VERSION` 7 → 8，新增知识点/题目/作答/会话表），知识点与题目以数据文件随仓库发布、启动时按 `code` 幂等导入。旧的 `review_due` 数据不动。
6. **复习独立于任务完成**：任务只是触发器，掌握程度只由会话里的主动作答决定。

## 1. 粒度准则

- **R1 一道预测题只考一个机制**（超过一个机制才说得清 → 拆）。
- **R2 半小时内能拿下**：知识点本身 10～30 分钟；**复习一道题 2～3 分钟**。超过 30 分钟才拆。
- **R3 五类题都能只围绕它写**：概念 / 预测 / 排查 / 编程 / 易错点。
- **R4 答错时根因唯一**。
- **R5 命名不含"和 / 与 / 以及"**；任务文本里的并列连接词是待拆信号，但**同一机制族的并列项可以合并**（见 §5 的合并示例）。

## 2. 从任务得到知识点的规则

- **M1** 任务文本里的并列机制各取一个候选点。
- **M2** "解释 / 预测 / 排查 / 口述"类任务通常**不新增知识点**，改为**引用**它考查的知识点（见 M7）。
- **M3** 纯元任务（建立补漏队列、复盘并安排复习）**不挂知识点、不生成复习项**。
- **M4** 跨任务、跨周同名机制只保留一个知识点（例：pytest 在 1204 与 1404 都出现，只留 `py.test.pytest`）。
- **M5** 任务隐含但没点名的前置补进本批（str/bytes、JSON、递归、函数式工具等）。
- **M6** 同一机制族且各自不足 10 分钟的合并（`索引+切片+增删改+tuple` → 一点）。
- **M7（多对多）** 知识点 ↔ 任务是多对多：知识点记 `taskRefs`，并标注关系类型
  `introduces`（任务引入该点）/ `exercises`（任务考查该点）。

## 3. 完成任务 → 复习项（多对多怎么落地）

| 任务类型 | 例子 | 完成后 |
| --- | --- | --- |
| 讲解型 / 实践型 | `1201` 解释名称绑定、身份、相等、可变性、浅深拷贝 | 生成它**引入**的 5 个知识点的复习项 |
| 测试型 | `1101` 完成可变性/作用域/参数/异常/导入的预测题 | 生成它**考查**的知识点（`C3/E1/G2/H1/J1`）的复习项；答错直接进薄弱点 |
| 口述型 | `1503` 不查资料讲清绑定/传参/作用域/异常/导入 | 生成**口述题**，默认按最高档"可以讲给别人听"考，答不好降档 |
| 纯元任务 | `1104` 建立补漏队列、`1504` 复盘并安排复习 | 不生成复习项；只刷新薄弱点列表 / 生成明天的复习计划 |

**推荐理由**：如果连"复盘、建补漏队列"也生成复习项，就会出现"复习自己的复习计划"这种自我循环，而且这些点根本写不出概念/预测/排查/编程题。测试型与口述型任务则必须生成复习项——否则完成它们等于白干，而且它们答错的内容正是最该进薄弱点的。

## 4. 规模与分批

| 批次 | 内容 | 任务数 | 知识点（估） | 题量（×5） |
| --- | --- | --- | --- | --- |
| 第 7 批 | 复习引擎 + **第 1 周**（基础层） | 21 | **40** | **≥200** |
| 第 8 批 | 第 2 周 对象模型与协议 | 21 | ~35 | ~175 |
| 第 9 批 | 第 3 周 函数、闭包与装饰器 | 21 | ~32 | ~160 |
| 第 10 批 | 第 4 周 迭代器、生成器与惰性流水线 | 21 | ~32 | ~160 |
| 第 11 批 | 第 5 周 类型、测试与工程化 | 21 | ~35 | ~175 |
| 第 12 批 | 第 6–7 周 线程/进程/asyncio（进阶层，按目标） | 42 | ~60 | ~300 |
| 第 13 批 | 第 8 周 整合、质量与最终验收 | 21 | ~25（多为综合练习） | ~125 |

三层 ↔ 你的 8 周：**第一层 = 第 1 周**；**第二层 = 第 2～5 周**；**第三层 = 第 6～7 周**（按目标选做）；第 8 周出综合题，不新造知识点。

## 5. 第 1 周知识点清单（40 点 / 约 13 小时）

合并示例（81 → 40 的主要合并）：

| 合并前（点） | 合并后 |
| --- | --- |
| 索引 + 切片 + 就地增删改 + tuple | `py.list.basics` |
| dict 语义 + 顺序与哈希约束 | `py.dict.basics` |
| 分组聚合 + 词频统计 | `py.dict.aggregate` |
| set 运算 + 保序去重 | `py.set.dedupe` |
| deque 选型 + 复杂度 | `py.container.selection` |
| 嵌套转换 + 嵌套浅拷贝 | `py.nested.structures` |
| `==与is` + 驻留 + `None` 判断 | `py.identity.eq-vs-is` |
| LEGB + global/nonlocal + 变量遮蔽 | `py.scope.legb` |
| 默认参数求值时机 + 可变默认参数 | `py.mutability.default-arg` |
| 位置/关键字 + `*args/**kwargs` + 仅限参数 + 转发 | `py.func.signature` |
| 一等函数/lambda + 函数式工具 | `py.func.functional` |
| try 顺序 + 异常链 + traceback | `py.exc.flow` |
| 异常层次 + 自定义异常 | `py.exc.types` |
| 文件模式 + 文本/二进制 + with | `py.io.files` |
| venv + 依赖记录 + pyproject + src 布局 | `py.env.setup` |

| # | id | 知识点 | 分钟 | 来源任务（引入/考查） |
| --- | --- | --- | --- | --- |
| 1 | `py.vars.binding` | 变量绑定、动态类型与 `isinstance` | 15 | 1201 引入；1101 考查 |
| 2 | `py.vars.truthiness` | 真值判断、比较与短路求值 | 15 | 1301 引入 |
| 3 | `py.vars.str-bytes` | str 与 bytes、编码与解码 | 10 | 隐含补齐 |
| 4 | `py.vars.operators` | 运算符、增强赋值与解包赋值 | 15 | 1301 引入 |
| 5 | `py.list.basics` | 列表与元组：索引、切片、可变性、增删改 | 20 | 1202 引入 |
| 6 | `py.list.sort-key` | `sorted`/`sort` 与 key、稳定性 | 15 | 1202 引入 |
| 7 | `py.dict.basics` | dict 键值语义、迭代顺序与哈希约束 | 20 | 1202/1203 引入 |
| 8 | `py.dict.aggregate` | 分组聚合与词频统计 | 20 | 1102/1204 引入 |
| 9 | `py.set.dedupe` | set 运算与去重（含保序去重） | 20 | 1202/1204 引入 |
| 10 | `py.container.selection` | 容器选型与复杂度（list/tuple/dict/set/deque） | 30 | 1202 引入 |
| 11 | `py.nested.structures` | 嵌套结构转换与浅拷贝陷阱 | 25 | 1102/1201 引入 |
| 12 | `py.mutability.alias` | 可变/不可变与别名 | 20 | 1201/1203 引入 |
| 13 | `py.mutability.copy-deep` | 浅拷贝与深拷贝 | 20 | 1201 引入 |
| 14 | `py.mutability.arg-passing` | 传参是传对象引用 | 15 | 1101/1503 考查 |
| 15 | `py.mutability.default-arg` | 可变默认参数与求值时机 | 20 | 1103/1303 引入 |
| 16 | `py.identity.eq-vs-is` | `==` 与 `is`、驻留、`None` 判断 | 20 | 1201 引入 |
| 17 | `py.identity.eq-hash` | `__eq__` 与 `__hash__` 的关系 | 15 | 1203 引入 |
| 18 | `py.scope.legb` | LEGB、global/nonlocal 与变量遮蔽 | 25 | 1103/1303 引入 |
| 19 | `py.scope.closure` | 闭包与循环变量晚绑定 | 20 | 1303 引入 |
| 20 | `py.flow.iteration` | for 迭代协议、range/enumerate/zip、边遍历边改 | 20 | 1301 引入 |
| 21 | `py.flow.while-break-else` | while、break/continue 与循环 else | 15 | 1301 引入 |
| 22 | `py.comprehension.basics` | 推导式与生成器表达式（含独立作用域） | 25 | 1301 引入 |
| 23 | `py.flow.match-case` | match/case 模式匹配与守卫 | 20 | 1505 引入 |
| 24 | `py.func.basics` | 定义、调用与返回值语义 | 10 | 1102 引入 |
| 25 | `py.func.signature` | 参数全解：位置/关键字/默认/`*args`/`**kwargs`/仅限/转发 | 30 | 1302 引入；1101 考查 |
| 26 | `py.func.functional` | 一等函数、lambda 与 map/filter/sorted-key | 25 | 隐含补齐 |
| 27 | `py.func.recursion` | 递归、基准情形与递归深度 | 20 | 隐含补齐 |
| 28 | `py.func.pure-refactor` | 纯函数、副作用与重构边界 | 20 | 1304 引入 |
| 29 | `py.exc.flow` | try/except/else/finally、异常链与 traceback | 25 | 1401 引入；1101 考查 |
| 30 | `py.exc.types` | 异常层次、自定义异常与 raise | 25 | 1401 引入 |
| 31 | `py.exc.over-catch` | 捕获范围过大与异常吞噬 | 15 | 1103 引入 |
| 32 | `py.exc.eafp-assert` | EAFP vs LBYL、assert 的边界 | 15 | 1502 引入 |
| 33 | `py.io.files` | 文件读写：模式、文本/二进制与 with | 25 | 1501 引入 |
| 34 | `py.json.basics` | JSON 序列化与类型映射 | 20 | 隐含补齐 |
| 35 | `py.path.pathlib` | pathlib、目录遍历与文件元数据 | 30 | 1501 引入 |
| 36 | `py.import.basics` | import 机制、from-import 与 `__main__` | 25 | 1402 引入；1101 考查 |
| 37 | `py.import.packages` | 包、相对导入与循环导入 | 25 | 1402 引入 |
| 38 | `py.env.setup` | venv、依赖记录与 pyproject/src 布局 | 30 | 1403/1404 引入 |
| 39 | `py.test.pytest` | pytest 基础与边界用例 | 20 | 1204/1404 引入 |
| 40 | `py.quality.ruff-mypy` | ruff/mypy 静态检查 | 15 | 1404 引入 |

纯元任务（不生成复习项）：`1104`（建立补漏队列）、`1504`（复盘并安排复习）。

## 6. 一个知识点的数据结构

| 字段 | 说明 |
| --- | --- |
| `code` | 稳定 id（`py.mutability.default-arg`），导入幂等 |
| `title` / `minutes` | 名称与掌握时间（10～30） |
| `module` / `level` | Python 模块筛选用（`函数` / `基础`）与层级 |
| `taskRefs` | `[{taskId, relation: introduces\|exercises}]` |
| `concept` / `predict` / `debug` / `code_task` / `pitfalls` | 五类题：概念 / 预测（代码+期望输出+解释） / 排查（坏代码+根因+修法） / 编程（需求+验收要点+参考实现） / 易错点条目 |
| `origin` | `builtin` / `ai` |

完整示例 `py.mutability.default-arg`：

- 概念题：用自己的话说清"默认参数在**函数定义时**求值一次"，为什么会在多次调用间累积。
- 代码预测题：
  ```python
  def add_item(item, items=[]):
      items.append(item)
      return items
  print(add_item(1)); print(add_item(2)); print(add_item(3, [])); print(add_item(4))
  ```
  先写输出，再解释每行为什么是这个结果（含"第 4 行为什么不是 `[3]`"）。
- 错误排查题：一段用它当"缓存"的代码（第二次调用拿到旧数据），找根因并解释"为什么看起来默认值是空的"。
- 实际编程题：用 `None` 哨兵重写 `add_item`，并写测试证明多次调用互不影响。
- 易错点：可变默认参数 / 调用侧共享同一列表 / 把默认值当"每次新建"。

校验规则（自动化，失败即拒绝导入）：五个题槽位非空、`minutes` 在 10～30、`code` 唯一且形如 `py.<主题>.<点>`、预测题必须有期望输出与解释、编程题必须有验收要点、`taskRefs` 指向真实任务 id、`level` 属于三层之一、`relation` 只能是 `introduces`/`exercises`。

## 7. 复习会话与调度

- **状态机**：`出题 → 我写（可选）→ 揭示答案/历史 → 5 档自评 → 下一题 → 结束总结`。
- **一次一题**：一个知识点一次只出一道题，按题型轮换（概念 → 预测 → 排查 → 编程，易错点随题展示）；同一知识点不连出两题。
- **硬不变量（可自动化断言）**：自评提交前，参考答案与历史答案**不得出现在 DOM**——这是"主动回忆而不是重读"的机器判据。
- **5 档 → 下次间隔**：完全不会 → 当天/次日（记一次失误，间隔回退到 1 天）；看过但说不清 → 1～3 天；基本掌握 → 7 天；可以独立写代码 → 14 天起逐步拉长（上限 60 天）；可以讲给别人听 → 30 天起（上限 90 天）。详细规则见 §13。
- **每日限量**：默认 5～15 项（可设置），**逾期项按到期排队、绝不一次全塞**；今日必须复习 / 即将到期 / 已逾期分开显示。
- **筛选**：逾期、项目、标签、题型、Python 模块、周次、薄弱知识点。
- **AI 判分（可选按钮）**：只在点击时调用，返回"缺什么 / 错在哪 / 补漏建议"，不改变自评档位。

## 8. 复习页改版

- 主体分组：今日必须复习 / 即将到期 / 已逾期 / 薄弱知识点 / 最近答错 / 最近掌握。
- 知识点可展开：历史答案、错误记录、五档变化、下次复习日。
- **任务级到期单独成组**（保留、非主入口），旧 `review_due` 不迁移、不丢。

## 9. 存储改造（方案 B：扩展原来的库）

- `SCHEMA_VERSION` 7 → 8，`ensure_schema()` 新增表：知识点、题目、复习状态、作答历史、会话；沿用现有快照 + 迁移阶梯，**先在库副本上验证迁移**。
- 知识点与题目以数据文件随仓库发布，启动时按 `code` 幂等导入；`origin='ai'` 的补充内容单独标记。
- 备份 / 恢复 / 导出天然覆盖（不新增第 4 个库文件）。
- 已知代价（如实记录）：
  1. **旧版本程序回不去**：v8 的库会被旧代码的 schema 守卫拒绝打开（现有守卫就是为防降级损坏数据）。
  2. **答题写入与项目保存共用同一把写锁**：每答一题只写几百字节，实测影响很小；这一批会加一条基准（保存 10k 任务 + 同时答题）来验证。
  3. 迁移真实库仍有风险，靠"副本验证 + 迁移前自动快照 + v7→v8 迁移测试"三重兜底。

## 10. 验证方案

1. 内容校验器（§6 规则）+ **反向验证**：故意写坏一条知识点，校验必须失败。
2. 会话不变量断言：自评前答案不入 DOM。
3. 调度单测：五档 → 间隔、每日上限、逾期不全塞、答错回退、"一次一题/题型轮换"。
4. 生成回流测试：完成任务 → 3～5 项且来自 `taskRefs`；`introduces` 与 `exercises` 都生效；元任务不生成；验收失败 → 补漏题；多次答错 → 薄弱点。
5. 迁移测试：v7 库（含你的 223 节点形态）→ v8，数据不变、新表就位、`quick_check=ok`；在副本上跑，真实库只读。
6. 真浏览器（Playwright）：完成一道题全流程（出题 → 写 → 揭示 → 自评 → 下一题 → 总结）。
7. 备份/恢复/导出往返覆盖新增表。

## 11. 决定记录

| 事项 | 结论 |
| --- | --- |
| 内容来源 | 混合：内置课程库为主 + AI 按任务补充 |
| 作答与判定 | 自己写 + 自己评为主，AI 判分可选按钮 |
| 任务级复习 | 保留、非主入口、单独成组，旧数据不迁移 |
| 首批范围 | 引擎 + 第 1 周全部内容（含隐含补齐） |
| 粒度 | 知识点 10～30 分钟掌握；复习一道题 2～3 分钟；适当合并 |
| 测试型/口述型任务 | 引用已有点生成复习项（`exercises`），不新增点 |
| 纯元任务 | 不挂知识点、不生成复习项（`1104`、`1504`） |
| 存储 | 扩展主库（`SCHEMA_VERSION` 7 → 8）；**已确认不打算回退旧版本** |
| 内容密度 | **覆盖优先**：宁可多写知识点/题目，允许补充任务原文没点名的相关知识点；五类题是下限 |

## 12. 数据模型与接口（主库，v8）

```sql
-- 知识点（内置 + AI 补充 + 额外补充）
CREATE TABLE review_points (
  code TEXT PRIMARY KEY,                 -- py.mutability.default-arg
  title TEXT NOT NULL,
  minutes INTEGER NOT NULL DEFAULT 10,   -- 10~30
  module TEXT NOT NULL DEFAULT '',       -- Python 模块（筛选用）
  level TEXT NOT NULL DEFAULT '基础',     -- 基础/实用/进阶
  origin TEXT NOT NULL DEFAULT 'builtin',-- builtin / builtin-extra / ai
  content_json TEXT NOT NULL,            -- 五类题 + 易错点（结构见 §6）
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
-- 知识点 ↔ 任务（多对多；补充知识点可以没有 taskRef）
CREATE TABLE review_point_tasks (
  code TEXT NOT NULL, task_id TEXT NOT NULL, project_id TEXT NOT NULL,
  relation TEXT NOT NULL,                -- introduces / exercises
  PRIMARY KEY (code, task_id, project_id)
);
-- 复习状态（每个知识点一行）
CREATE TABLE review_states (
  code TEXT PRIMARY KEY,
  due TEXT NOT NULL DEFAULT '',          -- 空 = 还没学过/没排期
  interval_days INTEGER NOT NULL DEFAULT 0,
  streak INTEGER NOT NULL DEFAULT 0,     -- 连续答对
  lapses INTEGER NOT NULL DEFAULT 0,     -- 累计"完全不会"
  last_grade INTEGER NOT NULL DEFAULT 0,
  weak INTEGER NOT NULL DEFAULT 0,
  last_reviewed_at TEXT NOT NULL DEFAULT ''
);
-- 作答历史（历史答案与错误记录靠它）
CREATE TABLE review_attempts (
  id TEXT PRIMARY KEY, code TEXT NOT NULL,
  task_id TEXT NOT NULL DEFAULT '', project_id TEXT NOT NULL DEFAULT '',
  question_type TEXT NOT NULL,           -- concept / predict / debug / code
  grade INTEGER NOT NULL,                -- 5 档自评 1~5
  answer TEXT NOT NULL DEFAULT '',       -- 我写的（可为空）
  ai_verdict TEXT NOT NULL DEFAULT '',   -- 可选 AI 判分（JSON）
  reviewed_on TEXT NOT NULL,             -- 本机日期（与现有复习计数同口径）
  duration_ms INTEGER NOT NULL DEFAULT 0,
  session_id TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE review_sessions (
  id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT NOT NULL DEFAULT '',
  planned INTEGER NOT NULL DEFAULT 0, answered INTEGER NOT NULL DEFAULT 0,
  grade_counts_json TEXT NOT NULL DEFAULT '{}', duration_ms INTEGER NOT NULL DEFAULT 0
);
-- 索引：review_states(due)、review_states(weak)、review_attempts(code, created_at)、review_attempts(reviewed_on)
```

设置项（沿用 `app_state.settings`）：`reviewDailyLimit`（5～15，默认 10）、`reviewNewPerDay`（每日新知识点名额，默认 2，可关）。

接口：

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/api/review/summary?today=` | 分组计数（今日必复/即将到期/已逾期/薄弱/最近答错/最近掌握）+ 连续天数 + 今日进度 |
| GET | `/api/review/queue?today=&limit=&module=&level=&projectId=&tag=&type=&include=` | 今日题目队列（**只给题面，不含答案**） |
| POST | `/api/review/reveal` | `{code, type}` → 参考答案要点、易错点、我的历史答案（**只有调它才拿得到答案**） |
| POST | `/api/review/answer` | `{code, type, grade, answer, durationMs, sessionId}` → 记录 + 更新调度 → 返回下次复习日 |
| POST | `/api/review/ai-grade` | 可选 AI 判分：`{code, type, answer}` → 缺什么/错在哪/补漏建议 |
| POST | `/api/review/generate` | `{taskId, projectId}` → AI 补充知识点/补漏题（3～5 项，幂等入库，`origin='ai'`） |
| GET | `/api/review/points?module=&level=&query=&limit=&offset=` | 知识点库浏览（含掌握度、taskRefs），支持"立即练一次" |
| GET | `/api/review/history?code=&limit=` | 某知识点的历史答案与错误记录 |
| POST | `/api/review/plan` | 生成/刷新今日计划（默认由 queue 即算即出） |

## 13. 会话状态机与调度细节

状态机：

```
idle → loading(取队列) → asking(题面 + 输入框)
asking   --写--> drafting（本地草稿，可随时揭示）
drafting --看答案--> revealing（POST /reveal：参考答案 + 易错点 + 历史答案）
revealing --选 5 档--> recording（POST /answer）→ next
next：队列还有 → asking；没有 → summary（结束总结）
任意状态 --退出--> 存草稿并回复习页；下次进同一题恢复草稿
```

- **一次一题**：一个知识点一次只出 1 道题，题型轮换（概念 → 预测 → 排查 → 编程；易错点随题展示），同一知识点不连出两题。
- **五档 → 间隔**：完全不会(1) → 当天（当天已答过则次日）+ `lapses+1`；说不清(2) → 1～3 天；基本掌握(3) → 7 天；能独立写(4) → 14 天，之后每次 +7～×1.5，上限 60；能讲给别人(5) → 30 天，上限 90。
- **答错回退**：grade ≤ 2 时间隔退回 1 天（不归零重来）；连续答对则逐步拉长。
- **薄弱点**：`lapses ≥ 2` 或最近 3 次里 2 次 grade ≤ 2 → `weak=1`；连续 2 次 grade ≥ 4 → `weak=0`。薄弱点在队列里加权优先。
- **每日队列组装**：逾期（按 due 升序）→ 今日到期 → `weak` 补足 → 未学过的新知识点（每日最多 `reviewNewPerDay` 个）→ 即将到期（按最久未复习）。**上限硬约束，绝不把逾期一次全塞。**
- **未学过的补充知识点**：默认不进每日队列（避免塞满），但可以在知识点库页"立即练一次"；练完按五档排期。
- **结束总结**：本次题数、各档分布、用时、正确率、新进薄弱点、下次复习日、"最近答错/最近掌握"更新。

## 14. 边界与错误处理

- **没有 API key**：内置内容完全可用；`generate` / `ai-grade` 返回明确错误，前端按钮禁用并说明原因（离线也能复习）。
- **服务不可用/断网**：题目已在内存，会话可继续；`answer` 写入失败时保留输入并提示重试（不丢答案）。
- **刷新/中途退出**：草稿存本地（key 含 sessionId + code + type），回来恢复未提交答案。
- **时区**：沿用 `todayStr()` 的前端日期并随请求传给服务端（与现有复习计数、`/api/reviews` 同口径）。
- **大数据量**：`queue` 只返回限额内题目；`points` 分页；`history` 限制条数。
- **降级**：AI 生成失败不影响已完成任务产生复习项（预规划的内置知识点仍然生效）。

## 15. 设计点 → 测试映射

| 设计点 | 测试 |
| --- | --- |
| §6 内容校验 | 校验器单测 + 反向验证（写坏一条必须失败） |
| §7 答案不提前出现 | 前端脚本断言：`reveal` 之前 DOM 里没有答案文本 |
| §13 调度 | 五档→间隔、回退、薄弱点判定、每日上限、逾期不全塞、一次一题/题型轮换 |
| §3 生成回流 | 完成任务 → 3～5 项且来自 `taskRefs`；`introduces`/`exercises` 都生效；元任务不生成；验收失败 → 补漏题 |
| §9 存储 | v7→v8 迁移（副本上跑）、旧数据不变、`quick_check=ok`、备份/恢复/导出往返 |
| §9 写锁 | 基准：保存 1 万任务 + 同时答题的耗时 |
| §12 接口 | HTTP 层测试：非法参数 400、缺 key 时生成接口明确报错 |
| 全流程 | Playwright：出题 → 写 → 揭示 → 自评 → 下一题 → 总结 |
