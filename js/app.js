(function() {
    'use strict';
    const projectsView = document.getElementById('projectsView');
    const detailView = document.getElementById('detailView');
    const projectGrid = document.getElementById('projectGrid');
    const emptyProjects = document.getElementById('emptyProjects');
    const newProjectInput = document.getElementById('newProjectInput');
    const createProjectBtn = document.getElementById('createProjectBtn');
    const newProjectAiToggle = document.getElementById('newProjectAiToggle');
    const backBtn = document.getElementById('backBtn');
    const detailTitle = document.getElementById('detailTitle');
    const detailDate = document.getElementById('detailDate');
    const projectAssessmentToggle = document.getElementById('projectAssessmentToggle');
    const newNodeInput = document.getElementById('newNodeInput');
    const addWeekBtn = document.getElementById('addWeekBtn');
    const treeRoot = document.getElementById('treeRoot');
    const emptyTreeTip = document.getElementById('emptyTreeTip');
    const countDisplay = document.getElementById('countDisplay');
    const clearBtn = document.getElementById('clearBtn');
    const expandAllBtn = document.getElementById('expandAllBtn');
    const clearHistoryBtn = document.getElementById('clearHistoryBtn');
    const saveStatus = document.getElementById('saveStatus');
    const projectSearchInput = document.getElementById('projectSearchInput');
    const projectStatusFilter = document.getElementById('projectStatusFilter');
    const nodeSearchInput = document.getElementById('nodeSearchInput');
    const nodeStatusFilter = document.getElementById('nodeStatusFilter');
const reviewQueueBtn = document.getElementById('reviewQueueBtn');
const reviewQueueCount = document.getElementById('reviewQueueCount');
const reviewView = document.getElementById('reviewView');
const reviewBackBtn = document.getElementById('reviewBackBtn');
const reviewBody = document.getElementById('reviewBody');
const reviewSubline = document.getElementById('reviewSubline');
const projectReviewToggle = document.getElementById('projectReviewToggle');
    const exportBtn = document.getElementById('exportBtn');
    const importInput = document.getElementById('importInput');
    const backgroundInput = document.getElementById('backgroundInput');
    const resetBackgroundBtn = document.getElementById('resetBackgroundBtn');
    const databaseBackupSelect = document.getElementById('databaseBackupSelect');
    const backupPicker = document.getElementById('backupPicker');
    const databaseBackupPickerButton = document.getElementById('databaseBackupPickerButton');
    const databaseBackupMenu = document.getElementById('databaseBackupMenu');
    const renameDatabaseBackupBtn = document.getElementById('renameDatabaseBackupBtn');
    const createDatabaseBackupBtn = document.getElementById('createDatabaseBackupBtn');
    const restoreDatabaseBackupBtn = document.getElementById('restoreDatabaseBackupBtn');
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toastMessage');
    const toastAction = document.getElementById('toastAction');
    const assessmentModal = document.getElementById('assessmentModal');
    const assessmentTitle = document.getElementById('assessmentTitle');
    const assessmentForm = document.getElementById('assessmentForm');
    const assessmentModel = document.getElementById('assessmentModel');
    const assessmentAnswer = document.getElementById('assessmentAnswer');
    const assessmentFiles = document.getElementById('assessmentFiles');
    const assessmentFilesList = document.getElementById('assessmentFilesList');
    const assessmentStage = document.getElementById('assessmentStage');
    const assessmentQuestions = document.getElementById('assessmentQuestions');
    const assessmentQuestionProgress = document.getElementById('assessmentQuestionProgress');
    const assessmentCurrentQuestion = document.getElementById('assessmentCurrentQuestion');
    const assessmentConversation = document.getElementById('assessmentConversation');
    const assessmentAnswerLabel = document.getElementById('assessmentAnswerLabel');
    const assessmentQuestionBtn = document.getElementById('assessmentQuestionBtn');
    const assessmentResult = document.getElementById('assessmentResult');
    const assessmentCloseBtn = document.getElementById('assessmentCloseBtn');
    const assessmentCancelBtn = document.getElementById('assessmentCancelBtn');
    const assessmentSubmitBtn = document.getElementById('assessmentSubmitBtn');
    const assessmentServiceStatus = document.getElementById('assessmentServiceStatus');
    const utilityModal = document.getElementById('utilityModal');
    const utilityTitle = document.getElementById('utilityTitle');
    const utilityKicker = document.getElementById('utilityKicker');
    const utilityBody = document.getElementById('utilityBody');
    const utilityCloseBtn = document.getElementById('utilityCloseBtn');
    const openMemoBtn = document.getElementById('openMemoBtn');
    const studyTools = window.TodoStudyTools;
    const DATA_SCHEMA_VERSION = 2;
    const CONTENT_VERSION = 7;
    const MAX_BACKGROUND_FILE_SIZE = 25 * 1024 * 1024;
    const MAX_BACKGROUND_DIMENSION = 2560;
    const HEARTBEAT_INTERVAL_MS = 30 * 1000;
    const SAVE_DEBOUNCE_MS = 250;
    const MAX_CONVERSATION_MESSAGES = 12;
    const MAX_CONVERSATION_MESSAGE_CHARS = 8000;
    const MAX_ASSESSMENT_ANSWER_CHARS = 20000;
    const MAX_QUESTION_RESULTS = 20;
    const SESSION_TOKEN_KEY = 'todo_list_session_token';
    let projects = [];
    let reviewCounts = { byProject: new Map(), today: 0, overdue: 0 };
    let stateRevision = 0;
    let sessionToken = '';
    let apiClient = null;
    let savedProjectJsonById = new Map();
    let saveConflict = false;
    let currentProjectId = null;
    let saveQueue = Promise.resolve();
    let saveTimer = null;
    let saveWaiters = [];
    let toastTimer = null;
    let toastActionHandler = null;
    let backgroundObjectUrl = null;
    let assessmentNode = null;
    let assessmentSubmitting = false;
    let assessmentQuestioning = false;
    let assessmentCodeFiles = [];
    let assessmentStageName = 'questions';
    let assessmentQuestionItems = [];
    let assessmentQuestionIndex = 0;
    let assessmentQuestionAnswers = [];
    let assessmentQuestionConversations = [];
    let assessmentDraftTimer = null;
    let memoState = { memos: [], selectedId: null, query: '', saveTimer: null, pendingMemoId: null,
        saveQueue: Promise.resolve() };
    const projectFilters = { query: '', status: 'all' };
    const nodeFilters = { query: '', status: 'all' };

    function initializeSessionToken() {
        const tokenFromUrl = new URLSearchParams(window.location.search).get('token') || '';
        try {
            sessionToken = tokenFromUrl || window.sessionStorage.getItem(SESSION_TOKEN_KEY) || '';
            if (tokenFromUrl) window.sessionStorage.setItem(SESSION_TOKEN_KEY, tokenFromUrl);
        } catch (error) {
            sessionToken = tokenFromUrl;
        }
        if (tokenFromUrl && window.history.replaceState) {
            window.history.replaceState(null, '', `${window.location.pathname}${window.location.hash}`);
        }
    }

    initializeSessionToken();
    apiClient = window.TodoApiClient.createClient(() => sessionToken);

    function generateId() {
        if (window.crypto && typeof window.crypto.randomUUID === 'function') {
            return window.crypto.randomUUID();
        }
        const random = Math.random().toString(36).slice(2);
        return `${Date.now()}-${random}`;
    }

    function todayStr() {
        const now = new Date();
        const pad = value => String(value).padStart(2, '0');
        return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    }

    function setNodeCompleted(node, completed) {
        node.completed = Boolean(completed);
        node.completedAt = node.completed ? new Date().toISOString() : null;
        if (!node || node.type !== 'item') return;
        if (node.completed) {
            const project = getCurrentProject();
            if (project && projectAutoReview(project) && !node.optional && !node.review) {
                node.review = { due: addDaysToIso(todayStr(), 1), learning: false,
                    log: (node.review && Array.isArray(node.review.log)) ? node.review.log : [] };
            }
        } else if (node.review) {
            delete node.review;
        }
    }

    function addDaysToIso(baseIso, days) {
        const parts = String(baseIso).split('-').map(Number);
        const dt = new Date(parts[0], (parts[1] || 1) - 1, parts[2] || 1);
        dt.setDate(dt.getDate() + Number(days));
        const pad = value => String(value).padStart(2, '0');
        return dt.getFullYear() + '-' + pad(dt.getMonth() + 1) + '-' + pad(dt.getDate());
    }

    function normalizeNodeReview(value) {
        if (!value || typeof value !== 'object') return undefined;
        const due = typeof value.due === 'string' ? value.due.slice(0, 10) : '';
        const learning = Boolean(value.learning);
        const rawLog = Array.isArray(value.log) ? value.log : [];
        const log = [];
        for (const entry of rawLog.slice(-50)) {
            if (!entry || typeof entry !== 'object') continue;
            const at = typeof entry.at === 'string' ? entry.at.slice(0, 10) : '';
            const result = typeof entry.result === 'string' ? entry.result.slice(0, 10) : '';
            if (at && result) log.push({ at: at, result: result });
        }
        if (!due && !learning && log.length === 0) return undefined;
        return { due: due, learning: learning, log: log };
    }

    function projectAutoReview(project) {
        if (!project) return false;
        if (typeof project.reviewEnabled === 'boolean') return project.reviewEnabled;
        return Boolean(project.assessmentEnabled);
    }

    function reviewLogPush(node, result) {
        const existing = (node.review && Array.isArray(node.review.log)) ? node.review.log : [];
        existing.push({ at: todayStr(), result: String(result).slice(0, 10) });
        return existing.slice(-50);
    }

    function applyReviewResult(node, result) {
        const days = result === 'easy' ? 7 : result === 'hard' ? 3 : 1;
        node.review = {
            due: addDaysToIso(todayStr(), days),
            learning: result === 'again',
            log: reviewLogPush(node, result)
        };
    }

    function scheduleReview(node, dueIso) {
        if (!node || node.type !== 'item') return;
        if (!String(dueIso || '').trim()) return;
        node.review = {
            due: String(dueIso).slice(0, 10),
            learning: false,
            log: (node.review && Array.isArray(node.review.log)) ? node.review.log.slice(-50) : []
        };
    }

    function clearReview(node) {
        if (!node) return;
        delete node.review;
    }

    function getCurrentProject() {
        return projects.find(p => p.id === currentProjectId) || null;
    }

    function createDefaultTree() {
        const createdAt = todayStr();
        const wk = (id, text, children) => ({ id, type: 'week', text, completed: false, expanded: false,
            createdAt, children: children || [] });
        const unit = (id, text, children) => ({ id, type: 'day', text, completed: false, expanded: false,
            createdAt, children: children || [] });
        const task = (id, text, optional = false) => ({ id, type: 'item', text, completed: false, optional,
            assessmentRequired: true, assessment: null, assessmentHistory: 0, createdAt, children: [] });
        return [
            wk(1000, '第1周：基线诊断与基础语义', [
                unit(1100, '单元1：能力基线测试', [
                    task(1101, '不运行代码，完成可变性、作用域、参数、异常和导入机制的预测题，并逐题解释'),
                    task(1102, '从零实现分组统计、稳定去重和嵌套数据转换三个小函数'),
                    task(1103, '排查一段包含可变默认参数、变量遮蔽和异常吞噬问题的代码'),
                    task(1104, '将结果归类为熟练、模糊、未掌握，建立补漏队列')
                ]),
                unit(1200, '单元2：对象、绑定与内置容器', [
                    task(1201, '解释名称绑定、对象身份、相等性、可变性，以及浅拷贝和深拷贝的边界'),
                    task(1202, '比较 list、tuple、dict、set、deque 的语义、复杂度和工程选型'),
                    task(1203, '用最小实验验证别名修改、哈希约束、字典顺序和集合去重行为'),
                    task(1204, '实现稳定去重与词频统计，并为边界输入编写 pytest 测试')
                ]),
                unit(1300, '单元3：控制流、函数参数与作用域', [
                    task(1301, '掌握解包、推导式、生成器表达式、条件和循环的清晰写法'),
                    task(1302, '解释位置参数、关键字参数、仅限位置参数、仅限关键字参数和参数转发'),
                    task(1303, '预测 LEGB、global、nonlocal、晚绑定和可变默认参数的运行结果'),
                    task(1304, '将一段长流程重构为职责清晰的纯函数，并用测试固定行为')
                ]),
                unit(1400, '单元4：异常、模块与工程初始化', [
                    task(1401, '解释 try/except/else/finally、异常链和自定义异常的适用边界'),
                    task(1402, '验证模块缓存、绝对/相对导入、__name__ 和循环导入问题'),
                    task(1403, '使用 Python 3.12 或 3.13 创建 venv，并记录解释器与依赖版本'),
                    task(1404, '亲手创建 pyproject.toml、src/taskrunner、tests，并配置 pytest、ruff、mypy')
                ]),
                unit(1500, '单元5：首周项目与无资料验收', [
                    task(1501, '实现只读 scanner v0：接收目录并用 pathlib 输出文件路径和基础元数据'),
                    task(1502, '覆盖空目录、无效路径和权限错误，并补充行为测试'),
                    task(1503, '不查资料讲清对象绑定、参数传递、作用域、异常传播和导入流程'),
                    task(1504, '复盘本周错误假设，并安排下一次和一周后的回忆练习'),
                    task(1505, '探索 match/case 的模式、守卫和常见误用', true)
                ]),
                unit(1600, '补漏队列：基线测试薄弱点', [
                    task(1601, '修复可变默认参数：解释默认对象的创建时机，并用 None 哨兵重写 collect'),
                    task(1602, '修复局部作用域误判：解释函数内赋值为何遮蔽全局名称，并比较 global 与更好的参数传递'),
                    task(1603, '修复 nonlocal 闭包计数器：从零实现可连续调用的 counter，并解释变量单元'),
                    task(1604, '修复循环闭包晚绑定：分别用默认参数和工厂函数保存每轮值，并写预测题'),
                    task(1605, '重做异常流程题：画出 try、except、else、finally、return 和异常传播的执行顺序'),
                    task(1606, '重做导入机制题：用两个文件验证 sys.modules、from import 名称绑定和 __name__')
                ])
            ]),
            wk(2000, '第2周：对象模型与 Python 协议', [
                unit(2100, '单元1：类、实例与方法绑定', [
                    task(2101, '解释类对象、实例、命名空间、MRO，以及实例方法绑定过程'),
                    task(2102, '预测实例属性、类属性、继承覆盖、classmethod 和 staticmethod 的行为'),
                    task(2103, '实现一个小型配置对象，对比组合与继承两种设计'),
                    task(2104, '用测试验证初始化、继承和方法绑定边界')
                ]),
                unit(2200, '单元2：属性查找与描述符', [
                    task(2201, '画出 obj.attr 从 __getattribute__、描述符、实例字典到 __getattr__ 的查找顺序'),
                    task(2202, '从零实现支持校验的描述符，并解释数据描述符和非数据描述符'),
                    task(2203, '对比 property、cached_property 与自定义描述符的适用场景'),
                    task(2204, '排查递归触发 __getattribute__ 或 __setattr__ 的错误实现')
                ]),
                unit(2300, '单元3：特殊方法与值对象', [
                    task(2301, '解释 __repr__、__str__、__eq__、__hash__、__bool__ 的协议和不变量'),
                    task(2302, '实现不可变 FileRecord 值对象，并保持相等性与哈希一致'),
                    task(2303, '实现一个最小容器的 len、contains、getitem 协议并验证回退行为'),
                    task(2304, '为相等、哈希、格式化和非法状态补充测试')
                ]),
                unit(2400, '单元4：上下文管理与数据建模', [
                    task(2401, '解释 with 的进入、退出、异常抑制和资源释放流程'),
                    task(2402, '分别用类和 contextlib.contextmanager 实现计时上下文管理器'),
                    task(2403, '掌握 dataclass 的 field、frozen、slots、默认工厂和派生字段'),
                    task(2404, '用 Enum 表达有限状态，并说明何时不该使用 Enum')
                ]),
                unit(2500, '单元5：项目模型与协议验收', [
                    task(2501, '为 FileRecord、TaskResult、RunConfig 建模并写清不变量'),
                    task(2502, '用上下文管理器封装一次扫描运行的计时和资源清理'),
                    task(2503, '针对无效配置、读取失败和资源释放编写测试'),
                    task(2504, '不查资料解释方法绑定、属性查找、描述符和上下文管理协议'),
                    task(2505, '探索 type 创建类、__init_subclass__ 与元类的职责边界', true)
                ])
            ]),
            wk(3000, '第3周：函数、闭包与装饰器', [
                unit(3100, '单元1：一等函数与调用接口', [
                    task(3101, '把函数作为值传递、存储和返回，并解释可调用对象协议'),
                    task(3102, '使用 inspect.signature 检查参数绑定和包装前后的函数签名'),
                    task(3103, '用 Callable 和 Protocol 描述处理函数接口'),
                    task(3104, '将文件处理步骤重构为可组合的函数序列')
                ]),
                unit(3200, '单元2：作用域与闭包', [
                    task(3201, '解释自由变量、闭包单元、nonlocal 和函数生命周期'),
                    task(3202, '预测循环闭包、晚绑定和共享状态示例的输出'),
                    task(3203, '从零实现计数器、配置捕获器和带状态重试策略'),
                    task(3204, '用默认参数、工厂函数和 functools.partial 分别修复晚绑定问题')
                ]),
                unit(3300, '单元3：装饰器机制', [
                    task(3301, '手动展开 @decorator 语法，解释导入时装饰和调用时执行的区别'),
                    task(3302, '实现透明转发参数与返回值的装饰器，并使用 functools.wraps'),
                    task(3303, '实现带参数装饰器并验证多层装饰顺序'),
                    task(3304, '排查元数据丢失、共享状态和异常处理不当的装饰器')
                ]),
                unit(3400, '单元4：可维护的装饰器设计', [
                    task(3401, '实现耗时、日志和有限重试装饰器，明确每个装饰器的职责'),
                    task(3402, '让装饰器正确支持实例方法，并解释描述符绑定带来的影响'),
                    task(3403, '为返回值、异常、重试次数、元数据和叠加顺序编写测试'),
                    task(3404, '判断何时应改用上下文管理器、高阶函数或显式调用')
                ]),
                unit(3500, '单元5：任务注册器与专题验收', [
                    task(3501, '实现 @register(name) 装饰器，将文件处理器注册到只读任务表'),
                    task(3502, '为重复名称、未知任务和错误签名设计异常及测试'),
                    task(3503, '接入耗时与重试装饰器，并保持核心处理函数可独立测试'),
                    task(3504, '从空文件重写注册装饰器，并口头解释闭包、绑定和装饰顺序'),
                    task(3505, '探索 singledispatch 与类装饰器，比较它们和普通装饰器', true)
                ])
            ]),
            wk(4000, '第4周：迭代器、生成器与惰性流水线', [
                unit(4100, '单元1：迭代协议', [
                    task(4101, '解释 iterable、iterator、iter、next、StopIteration 之间的关系'),
                    task(4102, '预测一次性迭代器、可重复迭代对象和迭代中修改容器的行为'),
                    task(4103, '分别实现一个可重复范围对象和一个一次性范围迭代器'),
                    task(4104, '验证 for、in、解包和 list 如何消费迭代协议')
                ]),
                unit(4200, '单元2：生成器状态与惰性求值', [
                    task(4201, '解释生成器创建、挂起、恢复、结束和异常状态'),
                    task(4202, '将读取全部文件的实现改成逐个 yield 的惰性扫描器'),
                    task(4203, '比较列表推导式和生成器表达式的求值时机与内存占用'),
                    task(4204, '测试生成器未启动、部分消费、完全消费和提前关闭的行为')
                ]),
                unit(4300, '单元3：yield from 与生成器控制', [
                    task(4301, '实现递归目录遍历，并用 yield from 委托子迭代器'),
                    task(4302, '实验 send、throw、close 和 GeneratorExit，记录状态变化'),
                    task(4303, '说明生成器协作与 async/await 协程不是同一个抽象'),
                    task(4304, '确保提前停止扫描时文件句柄和其他资源被正确释放')
                ]),
                unit(4400, '单元4：itertools 与流水线组合', [
                    task(4401, '掌握 chain、islice、takewhile、dropwhile、groupby 和 tee 的语义'),
                    task(4402, '识别 groupby 相邻分组、tee 缓存和无限迭代器的常见陷阱'),
                    task(4403, '组合发现、过滤、转换、汇总四段惰性流水线'),
                    task(4404, '用有限样本测试每一段，并验证不必要工作没有提前执行')
                ]),
                unit(4500, '单元5：项目惰性流水线验收', [
                    task(4501, '实现按扩展名、大小和修改时间组合过滤的文件扫描流水线'),
                    task(4502, '生成 FileRecord 时保持惰性，并允许调用方提前停止'),
                    task(4503, '用大量临时文件比较惰性与一次性加载的内存和首条结果时间'),
                    task(4504, '不查资料实现一个迭代器和一个生成器，并解释各自状态模型'),
                    task(4505, '探索 async generator、aiter 和 anext 的协议外形', true)
                ])
            ]),
            wk(5000, '第5周：类型、测试与工程化基础', [
                unit(5100, '单元1：模块、包与项目边界', [
                    task(5101, '解释模块搜索、sys.modules、包初始化、相对导入和 __main__'),
                    task(5102, '整理 src 布局，确保测试针对已安装包而不是偶然路径'),
                    task(5103, '拆分 models、pipeline、registry、errors、runners、cli 的职责'),
                    task(5104, '制造并修复一次循环导入，记录可复用的拆分原则')
                ]),
                unit(5200, '单元2：类型标注作为设计工具', [
                    task(5201, '掌握内置泛型、联合类型、TypeAlias、Literal、TypedDict 和 Callable'),
                    task(5202, '用 Protocol 描述处理器接口，用 TypeVar 编写保持类型的组合函数'),
                    task(5203, '为公共 API 完成类型标注，并逐条理解 mypy 报错'),
                    task(5204, '通过一次接口重构验证类型检查能提前暴露哪些错误')
                ]),
                unit(5300, '单元3：pytest 与测试设计', [
                    task(5301, '使用 fixture、parametrize、raises 和 tmp_path 表达测试意图'),
                    task(5302, '区分单元、集成和端到端测试，避免只追求覆盖率数字'),
                    task(5303, '只在系统边界使用 mock，并识别过度 mock 导致的脆弱测试'),
                    task(5304, '为扫描、过滤、注册和异常路径建立稳定测试套件')
                ]),
                unit(5400, '单元4：异常、日志与调试', [
                    task(5401, '设计 TaskRunnerError 异常层级，并用 raise from 保留根因'),
                    task(5402, '配置结构化且可测试的日志，避免库代码擅自配置根 logger'),
                    task(5403, '使用 breakpoint、traceback 和调用栈定位一个跨模块故障'),
                    task(5404, '写一份现象、假设、证据、根因、修复和回归测试组成的排错记录')
                ]),
                unit(5500, '单元5：CLI、报告与中期验收', [
                    task(5501, '使用 argparse 实现 scan 命令、筛选参数、执行模式和输出路径'),
                    task(5502, '将结果流式写入 JSONL，并处理编码、路径和序列化错误'),
                    task(5503, '运行 pytest、ruff、mypy，并修复问题而非关闭检查'),
                    task(5504, '完成中期无资料演示，重新评估补漏队列和后四周负荷'),
                    task(5505, '探索 inspect、dis 与 ast 在理解和排错中的有限用途', true)
                ])
            ]),
            wk(6000, '第6周：线程、进程与并发边界', [
                unit(6100, '单元1：并发模型与 GIL', [
                    task(6101, '区分并发、并行、异步、I/O 密集和 CPU 密集任务'),
                    task(6102, '解释 GIL 能保证什么、不能保证什么，以及何时影响吞吐'),
                    task(6103, '用计时实验比较串行 I/O、串行 CPU 和不同并发方案'),
                    task(6104, '识别共享可变状态、竞态、死锁和线程泄漏风险')
                ]),
                unit(6200, '单元2：线程与 Executor', [
                    task(6201, '掌握 Thread、Future、ThreadPoolExecutor 和 as_completed 生命周期'),
                    task(6202, '实现线程池文件摘要计算，并保持结果和输入可关联'),
                    task(6203, '处理 worker 异常、超时和 Executor 关闭流程'),
                    task(6204, '验证增加线程数并不必然提高性能，并记录瓶颈证据')
                ]),
                unit(6300, '单元3：同步、队列与资源控制', [
                    task(6301, '用最小实验复现竞态，再分别用 Lock 和消息传递修复'),
                    task(6302, '使用 queue.Queue 构建有界生产者消费者流程'),
                    task(6303, '设计停止信号、错误传播和 join 规则，确保程序能够退出'),
                    task(6304, '测试队列满、worker 失败和中途停止等边界')
                ]),
                unit(6400, '单元4：多进程实验与选型', [
                    task(6401, '使用 ProcessPoolExecutor 运行 CPU 密集摘要实验'),
                    task(6402, '验证可序列化约束、进程启动成本和 __main__ 保护'),
                    task(6403, '比较线程与进程的吞吐、内存和错误处理成本'),
                    task(6404, '写出项目不把多进程作为常驻模式的技术理由')
                ]),
                unit(6500, '单元5：线程执行器项目验收', [
                    task(6501, '实现统一 Runner 接口下的同步和线程池执行器'),
                    task(6502, '加入并发上限、失败结果收集和有序/无序输出策略'),
                    task(6503, '让同一输入在两种模式下生成语义一致的报告'),
                    task(6504, '为异常、关闭、线程数和结果一致性编写测试并完成无资料讲解'),
                    task(6505, '探索 Condition、Event、Barrier 的适用场景和误用风险', true)
                ])
            ]),
            wk(7000, '第7周：asyncio 与结构化并发', [
                unit(7100, '单元1：事件循环、协程与 Task', [
                    task(7101, '解释协程对象、await、Task、Future 和事件循环的关系'),
                    task(7102, '预测直接调用 async 函数、create_task 和顺序 await 的执行时机'),
                    task(7103, '用最小实验观察任务状态、调度交替和阻塞事件循环的后果'),
                    task(7104, '识别把同步阻塞函数简单包进 async def 的伪异步')
                ]),
                unit(7200, '单元2：任务编排与结构化并发', [
                    task(7201, '比较 gather、wait、as_completed 和 TaskGroup 的语义与适用场景'),
                    task(7202, '使用 TaskGroup 组织相关任务，并处理 ExceptionGroup'),
                    task(7203, '验证子任务失败时兄弟任务和父协程的状态变化'),
                    task(7204, '避免遗失后台任务、未获取异常和生命周期超出调用方')
                ]),
                unit(7300, '单元3：取消、超时与清理', [
                    task(7301, '解释 CancelledError 在 await 点传播以及取消是协作式的含义'),
                    task(7302, '使用 asyncio.timeout 设计分层超时，并区分超时与业务失败'),
                    task(7303, '在 try/finally 和异步上下文管理器中保证资源清理'),
                    task(7304, '测试取消被吞掉、清理再次失败和超时嵌套等困难路径')
                ]),
                unit(7400, '单元4：队列、限流与背压', [
                    task(7401, '使用 asyncio.Queue 构建有界生产者消费者流水线'),
                    task(7402, '使用 Semaphore 限制并发，并解释它与任务数量的区别'),
                    task(7403, '设计 queue.join、task_done、停止信号和 worker 回收流程'),
                    task(7404, '通过慢消费者实验观察背压，并避免无限创建 Task')
                ]),
                unit(7500, '单元5：异步执行器项目验收', [
                    task(7501, '用 asyncio.to_thread 隔离 pathlib、摘要计算和 JSONL 写入等阻塞操作'),
                    task(7502, '实现异步 Runner，支持并发上限、超时、取消和失败汇总'),
                    task(7503, '验证同步、线程池、asyncio 三种模式结果一致并记录性能差异'),
                    task(7504, '不查资料排查一次任务泄漏或取消失败，并讲清完整生命周期'),
                    task(7505, '探索 contextvars、异步生成器和异步上下文管理器', true)
                ])
            ]),
            wk(8000, '第8周：整合、质量与最终验收', [
                unit(8100, '单元1：架构复盘与重构', [
                    task(8101, '画出数据流和依赖方向，说明 models、pipeline、registry、runners、cli 的边界'),
                    task(8102, '删除重复抽象和不必要设计模式，让核心流程可以独立测试'),
                    task(8103, '统一同步、线程和异步执行器接口，同时保留各自真实语义'),
                    task(8104, '用类型检查和测试保护一次跨模块重构')
                ]),
                unit(8200, '单元2：可靠性与边界测试', [
                    task(8201, '覆盖空目录、坏路径、权限错误、文件消失和输出失败'),
                    task(8202, '覆盖处理器异常、重试耗尽、超时、取消和部分成功报告'),
                    task(8203, '验证资源关闭、线程退出、任务回收和临时文件清理'),
                    task(8204, '完成关键 CLI 流程的集成测试，不用覆盖率数字替代行为判断')
                ]),
                unit(8300, '单元3：性能测量与选型结论', [
                    task(8301, '设计可重复基准，分离磁盘缓存、文件大小和并发数等变量'),
                    task(8302, '使用 timeit、cProfile 或 pstats 找到证据充分的瓶颈'),
                    task(8303, '比较三种执行模式的吞吐、延迟、内存和实现复杂度'),
                    task(8304, '写出基于任务性质选择同步、线程、进程或 asyncio 的决策表')
                ]),
                unit(8400, '单元4：打包与全新环境验证', [
                    task(8401, '完善 pyproject.toml 元数据、依赖、Python 版本和 CLI entry point'),
                    task(8402, '运行 pytest、ruff、mypy，修复根因并保留干净结果'),
                    task(8403, '使用 python -m build 构建 wheel 和 sdist'),
                    task(8404, '在全新虚拟环境安装产物并完成一次真实目录扫描')
                ]),
                unit(8500, '单元5：最终无资料综合验收', [
                    task(8501, '从架构到运行时完整讲解项目，并解释关键设计取舍'),
                    task(8502, '现场实现一个新处理器并通过装饰器注册、类型检查和测试'),
                    task(8503, '现场定位一个迭代状态或 asyncio 取消故障并补回归测试'),
                    task(8504, '复测基线题，整理仍薄弱主题及 30 天间隔复习计划'),
                    task(8505, '探索用 entry points 发现第三方处理器的最小插件机制', true)
                ])
            ])
        ];
    }

    function createDefaultProjects() {
        return [{
            id: generateId(),
            name: 'Python 8周系统复习 · 工程实战版',
            description: '理解原理 · 手写机制 · 工程应用 · 排错验收',
            createdAt: todayStr(),
            assessmentEnabled: true,
            tree: createDefaultTree()
        }];
    }

    function treeHasAssessment(nodes) {
        return (nodes || []).some(node => node.type === 'item'
            ? Boolean(node.assessmentRequired)
            : treeHasAssessment(node.children));
    }

    function setProjectAssessmentEnabled(project, enabled) {
        project.assessmentEnabled = Boolean(enabled);
        function walk(nodes) {
            for (const node of nodes || []) {
                if (node.type === 'item') {
                    node.assessmentRequired = project.assessmentEnabled;
                    if (project.assessmentEnabled && !node.assessment?.passed) setNodeCompleted(node, false);
                } else {
                    walk(node.children);
                }
            }
        }
        walk(project.tree);
    }

    function ensureRemedialQueueAtBottom(projectList) {
        if (!Array.isArray(projectList) || projectList.length === 0) return;
        const firstProject = projectList[0];
        let queue = null;
        function takeQueue(nodes) {
            for (let index = nodes.length - 1; index >= 0; index--) {
                const node = nodes[index];
                if (node.id === 1600) {
                    if (!queue) queue = node;
                    nodes.splice(index, 1);
                    continue;
                }
                if (node.children && node.children.length > 0) takeQueue(node.children);
            }
        }
        takeQueue(firstProject.tree || []);
        if (!queue) {
            queue = createDefaultTree()[0].children.find(node => node.id === 1600);
            queue = queue ? cloneData(queue) : null;
        }
        if (queue) {
            queue.expanded = false;
            firstProject.tree.push(queue);
        }
    }

    function markCurriculumAssessments(projectList) {
        function walk(nodes) {
            for (const node of nodes || []) {
                if (node.type === 'item' && Number.isInteger(node.id) && node.id >= 1000 && node.id < 9000) {
                    node.assessmentRequired = true;
                }
                if (node.children && node.children.length > 0) walk(node.children);
            }
        }
        for (const project of projectList || []) walk(project.tree);
    }

    function cloneData(value) {
        return JSON.parse(JSON.stringify(value));
    }

    function readStoredState() {
        return apiFetch('/api/projects', { cache: 'no-store' })
            .then(response => {
                if (!response.ok) throw new Error('SQLite 服务不可用');
                return response.json();
            })
            .then(payload => payload || null);
    }

    function serializeProject(project) {
        const stored = cloneData(project);
        delete stored._revision;
        delete stored.stats;
        return stored;
    }

    function writeStoredProject(project, expectedRevision) {
        return apiFetch('/api/project', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project: serializeProject(project),
                expectedRevision
            })
        }).then(response => {
            return response.json().catch(() => ({})).then(payload => {
                if (!response.ok) {
                    const error = new Error(payload.error || 'SQLite 写入失败');
                    error.status = response.status;
                    throw error;
                }
                return payload;
            });
        });
    }

    function readStoredProject(projectId) {
        return apiFetch(`/api/project?id=${encodeURIComponent(projectId)}`, { cache: 'no-store' })
            .then(async response => {
                const payload = await response.json().catch(() => ({}));
                if (!response.ok || !payload.project) throw new Error(payload.error || '读取项目失败');
                return payload;
            });
    }

    function deleteStoredProject(projectId, revision) {
        return apiFetch(`/api/project?id=${encodeURIComponent(projectId)}&revision=${encodeURIComponent(revision)}`, {
            method: 'DELETE'
        }).then(async response => {
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                const error = new Error(payload.error || '删除项目失败');
                error.status = response.status;
                throw error;
            }
        });
    }

    async function readStoredBackground() {
        const response = await apiFetch('/api/background', { cache: 'no-store' });
        if (response.status === 404) return null;
        if (!response.ok) throw new Error('读取背景图片失败');
        return {
            blob: await response.blob(),
            fileName: decodeURIComponent(response.headers.get('X-File-Name') || 'background')
        };
    }

    async function writeStoredBackground(blob, fileName) {
        const response = await apiFetch(
            `/api/background?name=${encodeURIComponent(fileName)}&type=${encodeURIComponent(blob.type || 'application/octet-stream')}`,
            { method: 'POST', body: blob }
        );
        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new Error(payload.error || '保存背景图片失败');
        }
    }

    async function deleteStoredBackground() {
        const response = await apiFetch('/api/background', { method: 'DELETE' });
        if (!response.ok) throw new Error('删除背景图片失败');
    }

    function normalizeAssessment(value) {
        if (!value || typeof value !== 'object') return null;
        const assessment = { ...value };
        const shortText = (text, limit) => String(text || '').slice(0, limit);
        if ('answer' in assessment) assessment.answer = shortText(assessment.answer, MAX_ASSESSMENT_ANSWER_CHARS);
        if ('implementationDraft' in assessment) {
            assessment.implementationDraft = shortText(assessment.implementationDraft, MAX_ASSESSMENT_ANSWER_CHARS);
        }
        assessment.questionSet = Array.isArray(assessment.questionSet)
            ? assessment.questionSet.slice(0, 3).map(text => shortText(text, 5000)) : [];
        assessment.questionAnswers = Array.isArray(assessment.questionAnswers)
            ? assessment.questionAnswers.slice(0, 3).map(text => shortText(text, MAX_CONVERSATION_MESSAGE_CHARS)) : [];
        assessment.questionConversations = Array.isArray(assessment.questionConversations)
            ? assessment.questionConversations.slice(0, 3).map(messages => Array.isArray(messages)
                ? messages.filter(message => message && (message.role === 'user' || message.role === 'assistant'))
                    .slice(-MAX_CONVERSATION_MESSAGES)
                    .map(message => ({
                        role: message.role,
                        content: shortText(message.content, MAX_CONVERSATION_MESSAGE_CHARS)
                    }))
                : [])
            : [];
        assessment.questionResults = Array.isArray(assessment.questionResults)
            ? assessment.questionResults.slice(-MAX_QUESTION_RESULTS) : [];
        return assessment;
    }

    function normalizeNode(node, fallbackType) {
        if (!node || typeof node !== 'object') return null;
        const type = ['week', 'day', 'item'].includes(node.type) ? node.type : fallbackType;
        const children = type === 'item' ? [] : (Array.isArray(node.children) ? node.children : [])
            .map(child => normalizeNode(child, type === 'week' ? 'day' : 'item'))
            .filter(Boolean);
        return {
            id: node.id ?? generateId(),
            type,
            text: String(node.text ?? '').trim() || '未命名内容',
            completed: Boolean(node.completed),
            completedAt: type === 'item' && node.completed && typeof node.completedAt === 'string' && node.completedAt
                ? node.completedAt
                : null,
            optional: type === 'item' && Boolean(node.optional),
            assessmentRequired: type === 'item' && Boolean(node.assessmentRequired),
            assessment: type === 'item' && node.assessment && typeof node.assessment === 'object'
                ? normalizeAssessment(node.assessment)
                : null,
            assessmentHistory: type === 'item' ? Math.max(0, Number(node.assessmentHistory) || 0) : 0,
            expanded: type === 'item' ? false : node.expanded !== false,
            createdAt: String(node.createdAt || todayStr()),
            review: type === 'item' ? normalizeNodeReview(node.review) : undefined,
            children
        };
    }

    function normalizeProjects(list) {
        if (!Array.isArray(list)) return [];
        const usedIds = new Set();
        function ensureUniqueIds(nodes) {
            for (const node of nodes || []) {
                let id = node.id;
                if (usedIds.has(id)) {
                    do { id = generateId(); } while (usedIds.has(id));
                    node.id = id;
                }
                usedIds.add(id);
                ensureUniqueIds(node.children);
            }
        }
        return list.map(project => {
            if (!project || typeof project !== 'object') return null;
            let projectId = project.id ?? generateId();
            if (usedIds.has(projectId)) {
                do { projectId = generateId(); } while (usedIds.has(projectId));
            }
            usedIds.add(projectId);
            const tree = (Array.isArray(project.tree) ? project.tree : [])
                .map(node => normalizeNode(node, 'week'))
                .filter(Boolean);
            ensureUniqueIds(tree);
            const normalized = {
                id: projectId ?? generateId(),
                name: String(project.name ?? '').trim() || '未命名项目',
                description: String(project.description ?? ''),
                createdAt: String(project.createdAt || todayStr()),
                assessmentEnabled: typeof project.assessmentEnabled === 'boolean'
                    ? project.assessmentEnabled
                    : treeHasAssessment(tree),
                reviewEnabled: typeof project.reviewEnabled === 'boolean'
                    ? project.reviewEnabled
                    : undefined,
                tree
            };
            setProjectAssessmentEnabled(normalized, normalized.assessmentEnabled);
            return normalized;
        }).filter(Boolean);
    }

    function normalizeProjectSummary(project) {
        const stats = project && typeof project.stats === 'object' ? project.stats : {};
        return {
            id: project.id,
            name: String(project.name || '未命名项目'),
            description: String(project.description || ''),
            createdAt: String(project.createdAt || todayStr()),
            assessmentEnabled: Boolean(project.assessmentEnabled),
            stats: {
                total: Math.max(0, Number(stats.total) || 0),
                remaining: Math.max(0, Number(stats.remaining) || 0),
                optionalTotal: Math.max(0, Number(stats.optionalTotal) || 0),
                optionalCompleted: Math.max(0, Number(stats.optionalCompleted) || 0)
            },
            tree: null,
            _revision: Math.max(0, Number(project._revision) || 0)
        };
    }

    function extractProjects(payload) {
        if (Array.isArray(payload)) return payload;
        if (payload && Array.isArray(payload.projects)) {
            if (payload.schemaVersion && payload.schemaVersion > DATA_SCHEMA_VERSION) {
                throw new Error('备份文件版本较新，请先升级程序');
            }
            return payload.projects;
        }
        return null;
    }

    async function loadProjects() {
        let storedPayload = null;
        try {
            storedPayload = await readStoredState();
        } catch (error) {
            console.error('SQLite 读取失败', error);
            projects = [];
            showToast('无法连接 SQLite，请先启动本地服务');
            return;
        }
        const storedProjects = storedPayload && Array.isArray(storedPayload.projects)
            ? storedPayload.projects : [];
        projects = storedProjects.map(normalizeProjectSummary);
        if (projects.length === 0) {
            projects = createDefaultProjects();
            await saveProjects();
        }
    }

    async function ensureProjectLoaded(projectId) {
        const index = projects.findIndex(project => String(project.id) === String(projectId));
        if (index < 0) throw new Error('项目不存在');
        if (Array.isArray(projects[index].tree)) return projects[index];
        const payload = await readStoredProject(projectId);
        const project = normalizeProjects([payload.project])[0];
        if (!project) throw new Error('项目数据格式不正确');
        project._revision = Math.max(0, Number(payload.revision) || 0);
        project.stats = projects[index].stats;
        if (index === 0) ensureRemedialQueueAtBottom([project]);
        expandAllNodes(project.tree || [], false);
        projects[index] = project;
        savedProjectJsonById.set(String(project.id), JSON.stringify(serializeProject(project)));
        return project;
    }

    function flushProjectsSave() {
        if (saveTimer) {
            clearTimeout(saveTimer);
            saveTimer = null;
        }
        const waiters = saveWaiters.splice(0);
        const operation = saveQueue.catch(() => undefined).then(async () => {
            if (saveConflict) throw new Error('存在未解决的版本冲突，请先刷新页面');
            // Recompute after earlier queued saves finish so this operation never submits a stale snapshot.
            const snapshot = projects.filter(project => Array.isArray(project.tree)).map(project => cloneData(project));
            const currentProjectJsonById = new Map(
                snapshot.map(project => [String(project.id), JSON.stringify(serializeProject(project))])
            );
            const changedProjects = snapshot.filter(project =>
                savedProjectJsonById.get(String(project.id)) !== currentProjectJsonById.get(String(project.id))
            );
            if (changedProjects.length === 0) return;
            setSaveStatus('保存中…', 'saving');
            for (const project of changedProjects) {
                const current = projects.find(item => String(item.id) === String(project.id));
                const expectedRevision = current ? current._revision : project._revision;
                const payload = await writeStoredProject(project, expectedRevision);
                const savedJson = currentProjectJsonById.get(String(project.id));
                savedProjectJsonById.set(String(project.id), savedJson);
                if (current) {
                    current._revision = Number(payload.revision) || expectedRevision + 1;
                    if (payload.summary) current.stats = payload.summary.stats;
                }
            }
            setSaveStatus('已保存');
        });
        saveQueue = operation.catch(() => undefined);
        operation.catch(error => {
            console.error('保存项目失败', error);
            if (error.status === 409) {
                saveConflict = true;
                setSaveStatus('版本冲突', 'error');
                showToast('检测到其他页面已修改数据，请刷新页面后重试');
            } else {
                setSaveStatus('保存失败', 'error');
                showToast('SQLite 保存失败，请确认本地服务正在运行');
            }
        });
        operation.then(
            () => waiters.forEach(waiter => waiter.resolve()),
            error => waiters.forEach(waiter => waiter.reject(error))
        );
        return operation;
    }

    function saveProjects() {
        const completion = new Promise((resolve, reject) => saveWaiters.push({ resolve, reject }));
        completion.catch(() => undefined);
        if (!saveTimer) saveTimer = setTimeout(flushProjectsSave, SAVE_DEBOUNCE_MS);
        return completion;
    }

    function setSaveStatus(text, state = '') {
        saveStatus.textContent = text;
        saveStatus.classList.toggle('saving', state === 'saving');
        saveStatus.classList.toggle('error', state === 'error');
    }

    function loadImageFromBlob(blob) {
        return new Promise((resolve, reject) => {
            const url = URL.createObjectURL(blob);
            const image = new Image();
            image.onload = () => {
                URL.revokeObjectURL(url);
                resolve(image);
            };
            image.onerror = () => {
                URL.revokeObjectURL(url);
                reject(new Error('无法识别这张图片'));
            };
            image.src = url;
        });
    }

    function canvasToBlob(canvas, type, quality) {
        return new Promise(resolve => canvas.toBlob(resolve, type, quality));
    }

    async function prepareBackgroundImage(file) {
        if (!file.type.startsWith('image/')) throw new Error('请选择图片文件');
        if (file.size > MAX_BACKGROUND_FILE_SIZE) {
            throw new Error('图片过大，请选择 25 MB 以内的图片');
        }
        const image = await loadImageFromBlob(file);
        const longestSide = Math.max(image.naturalWidth, image.naturalHeight);
        const scale = Math.min(1, MAX_BACKGROUND_DIMENSION / longestSide);
        const needsCompression = file.size > 2 * 1024 * 1024 || scale < 1;
        if (!needsCompression) return file;

        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
        canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
        const context = canvas.getContext('2d');
        if (!context) throw new Error('浏览器无法压缩这张图片');
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        const compressed = await canvasToBlob(canvas, 'image/webp', 0.86);
        if (!compressed) throw new Error('图片压缩失败');
        return compressed.size < file.size ? compressed : file;
    }

    function applyBackground(blob) {
        if (backgroundObjectUrl) URL.revokeObjectURL(backgroundObjectUrl);
        backgroundObjectUrl = URL.createObjectURL(blob);
        document.body.style.backgroundImage = `url("${backgroundObjectUrl}")`;
        document.body.classList.add('custom-background');
        resetBackgroundBtn.disabled = false;
    }

    function applyDefaultBackground() {
        if (backgroundObjectUrl) {
            URL.revokeObjectURL(backgroundObjectUrl);
            backgroundObjectUrl = null;
        }
        document.body.style.removeProperty('background-image');
        document.body.classList.remove('custom-background');
        resetBackgroundBtn.disabled = true;
    }

    async function loadSavedBackground() {
        resetBackgroundBtn.disabled = true;
        try {
            const saved = await readStoredBackground();
            if (saved && saved.blob instanceof Blob) applyBackground(saved.blob);
        } catch (error) {
            console.warn('背景图片读取失败', error);
            showToast('背景图片读取失败，可重新上传');
        }
    }

    async function handleBackgroundUpload(file) {
        if (!file) return;
        try {
            showToast('正在处理背景图片...');
            const prepared = await prepareBackgroundImage(file);
            await writeStoredBackground(prepared, file.name);
            applyBackground(prepared);
            const size = (prepared.size / 1024 / 1024).toFixed(1);
            showToast(`背景已保存（${size} MB）`);
        } catch (error) {
            console.error('背景图片处理失败', error);
            showToast(`背景设置失败：${error.message || '图片无法读取'}`);
        } finally {
            backgroundInput.value = '';
        }
    }

    async function resetBackground() {
        try {
            await deleteStoredBackground();
            applyDefaultBackground();
            showToast('已恢复默认背景');
        } catch (error) {
            console.error('恢复默认背景失败', error);
            showToast('恢复默认背景失败');
        }
    }

    function countRemainingInTree(nodes) {
        let count = 0;
        for (const node of nodes) {
            if (node.type === 'item') {
                if (!node.optional && !node.completed) count++;
            } else if (node.children && node.children.length > 0) {
                count += countRemainingInTree(node.children);
            }
        }
        return count;
    }

    function getProjectRemaining(project) {
        if (!Array.isArray(project.tree)) return Math.max(0, Number(project.stats?.remaining) || 0);
        return countRemainingInTree(project.tree || []);
    }

    function getProjectTotal(project) {
        if (!Array.isArray(project.tree)) return Math.max(0, Number(project.stats?.total) || 0);
        let total = 0;

        function walk(nodes) {
            for (const node of nodes) {
                if (node.type === 'item' && !node.optional) total++;
                if (node.children && node.children.length > 0) walk(node.children);
            }
        }
        walk(project.tree || []);
        return total;
    }

    function getProjectOptionalStats(project) {
        if (!Array.isArray(project.tree)) {
            return {
                total: Math.max(0, Number(project.stats?.optionalTotal) || 0),
                completed: Math.max(0, Number(project.stats?.optionalCompleted) || 0)
            };
        }
        const stats = { total: 0, completed: 0 };
        function walk(nodes) {
            for (const node of nodes) {
                if (node.type === 'item' && node.optional) {
                    stats.total++;
                    if (node.completed) stats.completed++;
                }
                if (node.children && node.children.length > 0) walk(node.children);
            }
        }
        walk(project.tree || []);
        return stats;
    }

    function findNodeById(nodes, id) {
        for (const node of nodes) {
            if (node.id === id) return node;
            if (node.children && node.children.length > 0) {
                const found = findNodeById(node.children, id);
                if (found) return found;
            }
        }
        return null;
    }

    function removeNodeById(nodes, id) {
        for (let i = 0; i < nodes.length; i++) {
            if (nodes[i].id === id) {
                nodes.splice(i, 1);
                return true;
            }
            if (nodes[i].children && nodes[i].children.length > 0) {
                if (removeNodeById(nodes[i].children, id)) return true;
            }
        }
        return false;
    }

    function toggleAllChildren(node, completed) {
        if (node.type === 'item' && node.optional) return;
        setNodeCompleted(node, completed);
        if (node.children && node.children.length > 0) {
            node.children.forEach(child => toggleAllChildren(child, completed));
        }
    }

    function expandAllNodes(nodes, expanded) {
        for (const node of nodes) {
            if (node.type !== 'item') node.expanded = expanded;
            if (node.children && node.children.length > 0) expandAllNodes(node.children, expanded);
        }
    }

    function collectCompletedItemIds(nodes, result = []) {
        for (const node of nodes) {
            if (node.type === 'item' && node.completed && !node.assessmentRequired) result.push(node.id);
            if (node.children && node.children.length > 0) collectCompletedItemIds(node.children, result);
        }
        return result;
    }

    function cleanupEmptyNodes(nodes) {
        for (let i = nodes.length - 1; i >= 0; i--) {
            const node = nodes[i];
            if (node.children && node.children.length > 0) cleanupEmptyNodes(node.children);
            if (node.type !== 'item' && (!node.children || node.children.length === 0)) {
                nodes.splice(i, 1);
            }
        }
    }

    function hideToast() {
        clearTimeout(toastTimer);
        toast.classList.remove('visible');
        toastAction.hidden = true;
        if (toastActionHandler) {
            toastAction.removeEventListener('click', toastActionHandler);
            toastActionHandler = null;
        }
    }

    function showToast(message, action = null) {
        if (!toast) return;
        hideToast();
        toastMessage.textContent = message;
        if (action && typeof action.onClick === 'function') {
            toastAction.textContent = action.label || '撤销';
            toastAction.hidden = false;
            toastActionHandler = () => {
                const callback = action.onClick;
                hideToast();
                callback();
            };
            toastAction.addEventListener('click', toastActionHandler);
        }
        toast.classList.add('visible');
        toastTimer = setTimeout(hideToast, action ? 6000 : 2800);
    }

    function getAssessmentApiUrl(path) {
        const base = window.location.protocol === 'file:' ? 'http://127.0.0.1:8765' : '';
        return `${base}${path}`;
    }

    function apiFetch(path, options = {}) {
        return apiClient.request(getAssessmentApiUrl(path), options);
    }

    function startServiceHeartbeat() {
        const sendHeartbeat = () => {
            apiFetch('/api/heartbeat', {
                method: 'GET',
                cache: 'no-store',
                keepalive: true
            }).catch(() => undefined);
        };
        sendHeartbeat();
        window.setInterval(sendHeartbeat, HEARTBEAT_INTERVAL_MS);
    }

    async function checkStorageHealth() {
        try {
            const response = await apiFetch('/api/storage', { cache: 'no-store' });
            if (!response.ok) return;
            const info = await response.json();
            const limit = Number(info.projectLimitBytes || info.stateLimitBytes) || 0;
            const used = Number(info.largestProjectBytes || info.stateBytes) || 0;
            if (limit > 0 && used >= limit * 0.75) {
                showToast(`最大的项目已使用 ${(used / limit * 100).toFixed(0)}%，建议导出备份并清理该项目的旧验收记录`);
            }
        } catch (error) {
            console.warn('SQLite 存储检查失败', error);
        }
    }

    async function loadDatabaseBackups() {
        try {
            const response = await apiFetch('/api/backups', { cache: 'no-store' });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.error || '读取备份失败');
            databaseBackupSelect.replaceChildren();
            databaseBackupMenu.replaceChildren();
            for (const backup of payload.backups || []) {
                const option = document.createElement('option');
                option.value = backup.name;
                option.textContent = `${backup.name} · ${formatBytes(backup.bytes)}${backup.valid ? '' : ' · 损坏'}`;
                option.disabled = !backup.valid;
                databaseBackupSelect.appendChild(option);
                const row = document.createElement('div');
                row.className = 'backup-picker-row';
                const choose = document.createElement('button');
                choose.type = 'button';
                choose.className = 'backup-picker-option';
                choose.textContent = option.textContent;
                choose.disabled = !backup.valid;
                choose.addEventListener('click', () => {
                    databaseBackupSelect.value = backup.name;
                    updateBackupPickerLabel();
                    databaseBackupMenu.hidden = true;
                    databaseBackupPickerButton.setAttribute('aria-expanded', 'false');
                });
                const remove = document.createElement('button');
                remove.type = 'button';
                remove.className = 'backup-picker-delete';
                remove.textContent = '×';
                remove.title = `删除 ${backup.name}`;
                remove.setAttribute('aria-label', `删除 ${backup.name}`);
                remove.addEventListener('click', event => {
                    event.stopPropagation();
                    deleteDatabaseBackupByName(backup.name);
                });
                row.append(choose, remove);
                databaseBackupMenu.appendChild(row);
            }
            if (databaseBackupSelect.options.length === 0) {
                const option = document.createElement('option');
                option.textContent = '暂无数据库备份';
                option.value = '';
                databaseBackupSelect.appendChild(option);
            }
            updateBackupPickerLabel();
        } catch (error) {
            showToast(error.message || '读取数据库备份失败');
        }
    }

    function updateBackupPickerLabel() {
        const selected = databaseBackupSelect.options[databaseBackupSelect.selectedIndex];
        databaseBackupPickerButton.textContent = selected ? selected.textContent : '暂无数据库备份';
        const hasSelection = Boolean(databaseBackupSelect.value);
        renameDatabaseBackupBtn.disabled = !hasSelection;
        restoreDatabaseBackupBtn.disabled = !hasSelection;
    }

    async function createDatabaseBackupFromUi() {
        try {
            const response = await apiFetch('/api/backup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'create' })
            });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.error || '创建备份失败');
            await loadDatabaseBackups();
            databaseBackupSelect.value = payload.name;
            updateBackupPickerLabel();
            showToast(`数据库备份已创建：${payload.name}`);
        } catch (error) {
            showToast(error.message || '创建数据库备份失败');
        }
    }

    async function renameDatabaseBackupFromUi() {
        const name = databaseBackupSelect.value;
        if (!name) return;
        const suggested = name.replace(/\.sqlite3$/, '');
        const newName = window.prompt('请输入新的备份名称（可不写 .sqlite3）：', suggested);
        if (newName === null || !newName.trim()) return;
        try {
            const response = await apiFetch('/api/backup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'rename', name, newName: newName.trim() })
            });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.error || '重命名备份失败');
            await loadDatabaseBackups();
            databaseBackupSelect.value = payload.name;
            updateBackupPickerLabel();
            showToast(`备份已重命名：${payload.name}`);
        } catch (error) {
            showToast(error.message || '重命名备份失败');
        }
    }

    async function deleteDatabaseBackupByName(name) {
        if (!name) return;
        if (!window.confirm(`确认删除备份“${name}”？删除后无法从程序中恢复。`)) return;
        try {
            const response = await apiFetch('/api/backup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'delete', name })
            });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.error || '删除备份失败');
            await loadDatabaseBackups();
            showToast(`已删除备份：${name}`);
        } catch (error) {
            showToast(error.message || '删除备份失败');
        }
    }

    async function restoreDatabaseBackupFromUi() {
        const name = databaseBackupSelect.value;
        if (!name) return;
        if (!window.confirm(`确认恢复数据库备份“${name}”？当前数据库会先自动备份，恢复后页面将重新加载。`)) return;
        try {
            const response = await apiFetch('/api/backup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'restore', name })
            });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.error || '恢复备份失败');
            window.location.reload();
        } catch (error) {
            showToast(error.message || '恢复数据库备份失败');
        }
    }

    function getAssessmentContext(targetNode) {
        const project = getCurrentProject();
        const context = { project: project ? project.name : '', week: '', unit: '' };
        function walk(nodes, week, unit) {
            for (const node of nodes || []) {
                const nextWeek = node.type === 'week' ? node.text : week;
                const nextUnit = node.type === 'day' ? node.text : unit;
                if (node === targetNode || node.id === targetNode.id) {
                    context.week = nextWeek || '';
                    context.unit = nextUnit || '';
                    return true;
                }
                if (walk(node.children, nextWeek, nextUnit)) return true;
            }
            return false;
        }
        if (project) walk(project.tree, '', '');
        return context;
    }

    function formatAssessmentResult(result) {
        const lines = [
            result.passed ? '通过' : '未通过',
            result.reply || '',
            result.summary || ''
        ];
        if (Array.isArray(result.strengths) && result.strengths.length > 0) {
            lines.push(`做得好的地方：${result.strengths.join('；')}`);
        }
        if (Array.isArray(result.problems) && result.problems.length > 0) {
            lines.push(`需要修正：${result.problems.join('；')}`);
        }
        if (Array.isArray(result.missingEvidence) && result.missingEvidence.length > 0) {
            lines.push(`还需补充：${result.missingEvidence.join('；')}`);
        }
        if (result.nextAction) lines.push(`下一步：${result.nextAction}`);
        return lines.filter(Boolean).join('\n');
    }

    function showAssessmentResult(result) {
        assessmentResult.hidden = false;
        assessmentResult.classList.toggle('failed', !result.passed);
        assessmentResult.textContent = formatAssessmentResult(result);
    }

    function formatBytes(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    }

    function renderAssessmentFiles() {
        assessmentFilesList.replaceChildren();
        if (assessmentCodeFiles.length === 0) {
            assessmentFilesList.hidden = true;
            return;
        }
        assessmentFilesList.hidden = false;
        assessmentCodeFiles.forEach((file, index) => {
            const row = document.createElement('div');
            row.className = 'assessment-file-row';
            const name = document.createElement('span');
            name.textContent = `${file.name} · ${formatBytes(file.size)}`;
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.textContent = '移除';
            remove.addEventListener('click', () => {
                assessmentCodeFiles.splice(index, 1);
                renderAssessmentFiles();
            });
            row.append(name, remove);
            assessmentFilesList.appendChild(row);
        });
    }

    async function readAssessmentFiles(fileList) {
        const selected = Array.from(fileList || []);
        if (selected.length === 0) return;
        if (selected.some(file => file.size > 512 * 1024)) {
            showToast('单个代码文件不能超过 512 KB');
            assessmentFiles.value = '';
            return;
        }
        if (assessmentCodeFiles.length + selected.length > 10) {
            showToast('最多上传 10 个代码文件');
            assessmentFiles.value = '';
            return;
        }
        const existing = new Set(assessmentCodeFiles.map(file => file.name));
        for (const file of selected) {
            if (!existing.has(file.name)) assessmentCodeFiles.push(file);
        }
        assessmentFiles.value = '';
        renderAssessmentFiles();
    }

    async function getAssessmentFilePayload() {
        return Promise.all(assessmentCodeFiles.map(async file => ({
            name: file.name,
            content: (await file.text()).slice(0, 120000)
        })));
    }

    function renderAssessmentQuestions() {
        const total = assessmentQuestionItems.length;
        assessmentQuestions.hidden = assessmentStageName !== 'questions' || total < 3;
        assessmentQuestionProgress.textContent = total >= 3
            ? `第 ${assessmentQuestionIndex + 1} / ${total} 题`
            : '正在准备题目…';
        assessmentCurrentQuestion.textContent = assessmentQuestionItems[assessmentQuestionIndex] || '';
        assessmentQuestionBtn.textContent = total >= 3 ? '重新开始三题' : 'AI 出三道题';
        renderAssessmentConversation();
    }

    function renderAssessmentConversation() {
        if (!assessmentConversation) return;
        assessmentConversation.replaceChildren();
        const messages = assessmentQuestionConversations[assessmentQuestionIndex] || [];
        assessmentConversation.hidden = assessmentStageName !== 'questions' || messages.length === 0;
        messages.forEach(message => {
            const bubble = document.createElement('div');
            bubble.className = `assessment-message ${message.role === 'user' ? 'user' : 'assistant'}`;
            const label = document.createElement('span');
            label.className = 'assessment-message-label';
            label.textContent = message.role === 'user' ? '你的回答' : 'AI';
            const content = document.createElement('span');
            content.textContent = message.content;
            bubble.append(label, content);
            assessmentConversation.appendChild(bubble);
        });
        if (!assessmentConversation.hidden) assessmentConversation.scrollTop = assessmentConversation.scrollHeight;
    }

    function setAssessmentStage(stage) {
        assessmentStageName = stage;
        const questions = stage === 'questions';
        assessmentStage.textContent = questions ? '第一阶段：AI 三题验收' : '第二阶段：代码实践（可选）';
        assessmentAnswerLabel.textContent = questions ? '当前题回答（写结论和解释）' : '实现代码或说明（可选）';
        assessmentAnswer.required = questions;
        assessmentAnswer.placeholder = questions
            ? '写出当前题的答案、预测结果和原因。按 Tab 插入 4 个空格。'
            : '可以留空直接提交；如果填写代码或说明，AI 会继续验收。';
        renderAssessmentQuestions();
        assessmentFiles.closest('.assessment-code-tools').hidden = questions;
        assessmentFilesList.hidden = questions || assessmentCodeFiles.length === 0;
        document.querySelector('.assessment-consent').textContent = questions
            ? '每次只回答当前题；当前题通过后自动进入下一题。至少三题全部通过后，再上传自己的实现代码。'
            : '第二阶段可不做：留空提交会直接完成；填写内容或上传文件后，将由 AI 验收，通过后完成。';
        assessmentSubmitBtn.textContent = questions ? '提交本题' : '提交';
    }

    async function requestAssessmentQuestion() {
        if (!assessmentNode || assessmentQuestioning) return;
        assessmentQuestioning = true;
        assessmentQuestionBtn.disabled = true;
        assessmentQuestionBtn.textContent = '出题中…';
        assessmentServiceStatus.textContent = '正在生成针对题…';
        try {
            const response = await apiFetch('/api/question', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    taskId: assessmentNode.id,
                    task: assessmentNode.text,
                    context: getAssessmentContext(assessmentNode),
                    model: assessmentModel.value,
                    files: await getAssessmentFilePayload()
                })
            });
            const payload = await response.json();
            if (!response.ok || !Array.isArray(payload.questions) || payload.questions.length < 3) {
                throw new Error(payload.error || 'AI 未生成至少三道题');
            }
            // The API may return more than three, but the lightweight flow uses exactly three.
            assessmentQuestionItems = payload.questions.slice(0, 3).map(String);
            assessmentQuestionIndex = 0;
            assessmentQuestionAnswers = [];
            assessmentQuestionConversations = [];
            renderAssessmentQuestions();
            assessmentAnswer.value = '';
            assessmentNode.assessment = {
                ...(assessmentNode.assessment || {}),
                questionSet: assessmentQuestionItems,
                questionIndex: 0,
                questionAnswers: [],
                questionConversations: [],
                model: assessmentModel.value
            };
            await saveProjects();
            assessmentServiceStatus.textContent = '题目已生成，请回答当前题';
        } catch (error) {
            assessmentServiceStatus.textContent = error.message || 'AI 出题失败';
        } finally {
            assessmentQuestioning = false;
            assessmentQuestionBtn.disabled = false;
        assessmentQuestionBtn.textContent = '重新出三道题';
        }
    }

    async function checkAssessmentService() {
        assessmentServiceStatus.textContent = '正在检查本地 AI 服务…';
        assessmentSubmitBtn.disabled = true;
        try {
            const response = await apiFetch('/api/config', { cache: 'no-store' });
            const payload = await response.json();
            if (!response.ok || !payload.ready) {
                throw new Error(payload.error || '未配置 DEEPSEEK_API_KEY');
            }
            const flashOption = assessmentModel.querySelector('option[value="flash"]');
            const proOption = assessmentModel.querySelector('option[value="pro"]');
            if (flashOption && payload.models && payload.models.flash) flashOption.textContent = payload.models.flash;
            if (proOption && payload.models && payload.models.pro) proOption.textContent = payload.models.pro;
            assessmentServiceStatus.textContent = '本地 AI 服务已就绪';
            assessmentSubmitBtn.disabled = false;
        } catch (error) {
            if (assessmentStageName === 'implementation') {
                assessmentServiceStatus.textContent = 'AI 服务不可用；仍可留空提交';
                assessmentSubmitBtn.disabled = false;
            } else {
                assessmentServiceStatus.textContent = 'AI 服务未启动或未配置 Key';
                assessmentSubmitBtn.disabled = true;
            }
        }
    }

    function openAssessment(node) {
        assessmentNode = node;
        assessmentTitle.textContent = node.text;
        assessmentAnswer.value = node.assessment && (node.assessment.implementationDraft || node.assessment.answer) || '';
        assessmentModel.value = node.assessment && node.assessment.model || 'flash';
        assessmentResult.hidden = true;
        assessmentCodeFiles = [];
        assessmentQuestionItems = Array.isArray(node.assessment?.questionSet)
            ? node.assessment.questionSet.map(String) : [];
        assessmentQuestionIndex = Math.max(0, Number(node.assessment?.questionIndex) || 0);
        assessmentQuestionAnswers = Array.isArray(node.assessment?.questionAnswers)
            ? node.assessment.questionAnswers.map(String) : [];
        assessmentQuestionConversations = Array.isArray(node.assessment?.questionConversations)
            ? node.assessment.questionConversations.map(messages => Array.isArray(messages)
                ? messages.filter(message => message && (message.role === 'user' || message.role === 'assistant'))
                    .map(message => ({
                        role: message.role,
                        content: String(message.content || '').slice(0, MAX_CONVERSATION_MESSAGE_CHARS)
                    })).slice(-MAX_CONVERSATION_MESSAGES)
                : [])
            : [];
        setAssessmentStage(node.assessment && node.assessment.questionPassed && !node.completed
            ? 'implementation' : 'questions');
        if (assessmentStageName === 'implementation') {
            assessmentServiceStatus.textContent = '第一阶段已通过；第二阶段可留空提交';
        }
        renderAssessmentFiles();
        assessmentModal.removeAttribute('hidden');
        document.body.classList.add('assessment-open');
        checkAssessmentService().then(() => {
            if (assessmentStageName === 'questions' && assessmentNode && assessmentQuestionItems.length < 3) requestAssessmentQuestion();
            if (assessmentStageName === 'questions' && assessmentQuestionAnswers[assessmentQuestionIndex]) {
                assessmentAnswer.value = assessmentQuestionAnswers[assessmentQuestionIndex];
            }
            renderAssessmentConversation();
        });
        setTimeout(() => assessmentAnswer.focus(), 0);
    }

    function closeAssessment() {
        if (assessmentSubmitting) return;
        persistAssessmentDraft();
        assessmentModal.setAttribute('hidden', '');
        document.body.classList.remove('assessment-open');
        assessmentNode = null;
    }

    function saveAssessmentDraft() {
        if (!assessmentNode) return;
        const draft = assessmentAnswer.value;
        clearTimeout(assessmentDraftTimer);
        assessmentDraftTimer = setTimeout(persistAssessmentDraft, 600);
    }

    function persistAssessmentDraft() {
        clearTimeout(assessmentDraftTimer);
        assessmentDraftTimer = null;
        if (!assessmentNode) return;
        if (assessmentStageName === 'questions') {
            assessmentQuestionAnswers[assessmentQuestionIndex] = assessmentAnswer.value;
            assessmentNode.assessment = {
                ...(assessmentNode.assessment || {}),
                questionSet: assessmentQuestionItems,
                questionIndex: assessmentQuestionIndex,
                questionAnswers: assessmentQuestionAnswers,
                questionConversations: assessmentQuestionConversations,
                model: assessmentModel.value
            };
        } else {
            assessmentNode.assessment = {
                ...(assessmentNode.assessment || {}),
                implementationDraft: assessmentAnswer.value.slice(0, MAX_ASSESSMENT_ANSWER_CHARS),
                model: assessmentModel.value
            };
        }
        saveProjects();
    }

    function handleAssessmentEditorTab(event) {
        if (event.key !== 'Tab') return;
        event.preventDefault();
        const start = assessmentAnswer.selectionStart;
        const end = assessmentAnswer.selectionEnd;
        const value = assessmentAnswer.value;
        if (!event.shiftKey) {
            assessmentAnswer.value = value.slice(0, start) + '    ' + value.slice(end);
            assessmentAnswer.selectionStart = assessmentAnswer.selectionEnd = start + 4;
            return;
        }
        const lineStart = value.lastIndexOf('\n', start - 1) + 1;
        const removeCount = value.slice(lineStart, start).startsWith('    ') ? 4
            : value.slice(lineStart, start).match(/^\s*/)?.[0].length || 0;
        if (removeCount > 0) {
            assessmentAnswer.value = value.slice(0, lineStart) + value.slice(lineStart + removeCount);
            assessmentAnswer.selectionStart = assessmentAnswer.selectionEnd = Math.max(lineStart, start - removeCount);
        }
    }

    async function submitAssessment(event) {
        event.preventDefault();
        if (!assessmentNode || assessmentSubmitting) return;
        const answer = assessmentAnswer.value.trim();
        if (assessmentStageName === 'questions' && assessmentQuestionItems.length < 3) {
            assessmentServiceStatus.textContent = '请等待 AI 生成三道题';
            return;
        }
        const skipsImplementation = assessmentStageName === 'implementation'
            && assessmentCodeFiles.length === 0 && !answer;
        if (!answer && assessmentCodeFiles.length === 0) {
            if (!skipsImplementation) {
                assessmentAnswer.focus();
                return;
            }
        }
        assessmentSubmitting = true;
        assessmentSubmitBtn.disabled = true;
        assessmentSubmitBtn.textContent = skipsImplementation ? '提交中…' : '验收中…';
        assessmentServiceStatus.textContent = skipsImplementation ? '正在完成任务…' : '正在发送给 DeepSeek…';
        assessmentResult.hidden = true;
        if (skipsImplementation) {
            try {
                const completedNode = assessmentNode;
                completedNode.assessment = {
                    ...(completedNode.assessment || {}),
                    passed: true,
                    score: Number(completedNode.assessment?.questionScore) || 100,
                    stage: 'implementation',
                    implementationSkipped: true,
                    implementationDraft: '',
                    answer: '',
                    evaluatedAt: new Date().toISOString()
                };
                setNodeCompleted(completedNode, true);
                await saveProjects();
                assessmentModal.setAttribute('hidden', '');
                document.body.classList.remove('assessment-open');
                assessmentNode = null;
                await showProjectsView();
                showToast('已通过');
            } catch (error) {
                assessmentResult.hidden = false;
                assessmentResult.classList.add('failed');
                assessmentResult.textContent = error.message || '提交失败';
                assessmentServiceStatus.textContent = '提交失败';
            } finally {
                assessmentSubmitting = false;
                assessmentSubmitBtn.disabled = false;
                assessmentSubmitBtn.textContent = '提交';
            }
            return;
        }
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 90000);
        try {
            const response = await apiFetch('/api/evaluate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    taskId: assessmentNode.id,
                    task: assessmentNode.text,
                    context: getAssessmentContext(assessmentNode),
                    answer,
                    model: assessmentModel.value,
                    files: await getAssessmentFilePayload(),
                    stage: assessmentStageName,
                    conversation: assessmentStageName === 'questions'
                        ? (assessmentQuestionConversations[assessmentQuestionIndex] || []) : [],
                    questions: assessmentStageName === 'questions'
                        ? [assessmentQuestionItems[assessmentQuestionIndex]] : [],
                    questionIndex: assessmentQuestionIndex,
                    totalQuestions: assessmentQuestionItems.length
                }),
                signal: controller.signal
            });
            const payload = await response.json();
            if (!response.ok || !payload.result) {
                throw new Error(payload.error || 'AI 验收失败');
            }
            const result = {
                passed: payload.result.passed === true && Number(payload.result.score) >= 80,
                score: Math.max(0, Math.min(100, Number(payload.result.score) || 0)),
                summary: String(payload.result.summary || ''),
                strengths: Array.isArray(payload.result.strengths) ? payload.result.strengths.map(String) : [],
                problems: Array.isArray(payload.result.problems) ? payload.result.problems.map(String) : [],
                missingEvidence: Array.isArray(payload.result.missingEvidence)
                    ? payload.result.missingEvidence.map(String)
                    : [],
                nextAction: String(payload.result.nextAction || ''),
                reply: String(payload.result.reply || ''),
                answer: answer.slice(0, MAX_CONVERSATION_MESSAGE_CHARS),
                model: assessmentModel.value,
                evaluatedAt: new Date().toISOString()
            };
            if (assessmentStageName === 'questions') {
                assessmentQuestionAnswers[assessmentQuestionIndex] = answer;
                const conversation = assessmentQuestionConversations[assessmentQuestionIndex] || [];
                conversation.push({ role: 'user', content: answer.slice(0, MAX_CONVERSATION_MESSAGE_CHARS) });
                conversation.push({
                    role: 'assistant',
                    content: (result.reply || formatAssessmentResult(result)).slice(0, MAX_CONVERSATION_MESSAGE_CHARS)
                });
                assessmentQuestionConversations[assessmentQuestionIndex] = conversation.slice(-MAX_CONVERSATION_MESSAGES);
                assessmentNode.assessment = {
                    ...(assessmentNode.assessment || {}),
                    questionSet: assessmentQuestionItems,
                    questionIndex: assessmentQuestionIndex,
                    questionAnswers: assessmentQuestionAnswers,
                    questionConversations: assessmentQuestionConversations,
                    questionResults: [...(assessmentNode.assessment?.questionResults || []), result]
                        .slice(-MAX_QUESTION_RESULTS),
                    model: assessmentModel.value
                };
                if (!result.passed) {
                    await saveProjects();
                    showAssessmentResult(result);
                    renderAssessmentConversation();
                    assessmentAnswer.value = '';
                    assessmentServiceStatus.textContent = '本题未通过，请根据反馈修改后再次提交';
                    return;
                }
                if (assessmentQuestionIndex + 1 < assessmentQuestionItems.length) {
                    assessmentQuestionIndex += 1;
                    assessmentNode.assessment.questionIndex = assessmentQuestionIndex;
                    await saveProjects();
                    assessmentAnswer.value = '';
                    renderAssessmentQuestions();
                    showAssessmentResult(result);
                    assessmentServiceStatus.textContent = `第 ${assessmentQuestionIndex} 题已通过，请回答下一题`;
                    return;
                }
                assessmentStageName = 'implementation';
                assessmentNode.assessment.questionPassed = true;
                assessmentNode.assessment.questionScore = result.score;
                setAssessmentStage('implementation');
                assessmentAnswer.value = '';
                assessmentCodeFiles = [];
                renderAssessmentFiles();
                await saveProjects();
                showAssessmentResult({ ...result, summary: '三道题全部通过。第二阶段可留空提交；填写内容则继续由 AI 验收。' });
                assessmentServiceStatus.textContent = '第一阶段已通过；第二阶段可留空提交';
                return;
            }
            assessmentNode.assessment = { ...(assessmentNode.assessment || {}), ...result,
                stage: assessmentStageName,
                answer: answer.slice(0, MAX_ASSESSMENT_ANSWER_CHARS),
                implementationDraft: '' };
            setNodeCompleted(assessmentNode, assessmentStageName === 'implementation' && result.passed);
            await saveProjects();
            if (result.passed) {
                assessmentModal.setAttribute('hidden', '');
                document.body.classList.remove('assessment-open');
                assessmentNode = null;
                await showProjectsView();
                showToast('已通过');
            } else {
                renderDetail();
                showAssessmentResult(result);
                assessmentServiceStatus.textContent = '尚未通过，请按反馈补漏';
            }
        } catch (error) {
            const message = error.name === 'AbortError' ? '请求超时，请重试' : error.message || 'AI 验收失败';
            assessmentResult.hidden = false;
            assessmentResult.classList.add('failed');
            assessmentResult.textContent = message;
            assessmentServiceStatus.textContent = '验收请求失败';
        } finally {
            clearTimeout(timeout);
            assessmentSubmitting = false;
            assessmentSubmitBtn.disabled = false;
            assessmentSubmitBtn.textContent = assessmentStageName === 'questions' ? '提交本题' : '提交';
        }
    }

    function subtreeRequiresAssessment(node) {
        if (node.type === 'item') return Boolean(node.assessmentRequired);
        return (node.children || []).some(child => subtreeRequiresAssessment(child));
    }

    function getNodeStats(node) {
        if (node.type === 'item') {
            if (node.optional) return { total: 0, remaining: 0 };
            return { total: 1, remaining: node.completed ? 0 : 1 };
        }
        return (node.children || []).reduce((stats, child) => {
            const childStats = getNodeStats(child);
            return {
                total: stats.total + childStats.total,
                remaining: stats.remaining + childStats.remaining
            };
        }, { total: 0, remaining: 0 });
    }

    function getNodeCompletionState(node) {
        if (node.type === 'item') return node.completed ? 'completed' : 'active';
        const stats = getNodeStats(node);
        if (stats.total === 0) return node.completed ? 'completed' : 'active';
        if (stats.remaining === 0) return 'completed';
        if (stats.remaining === stats.total) return 'active';
        return 'partial';
    }

    function nodeMatchesStatus(node, status) {
        if (status === 'all') return true;
        const stats = getNodeStats(node);
        if (status === 'completed') return stats.total > 0 && stats.remaining === 0;
        return stats.remaining > 0;
    }

    function nodeMatchesOwnFilter(node) {
        const query = nodeFilters.query.trim().toLowerCase();
        const textMatches = !query || node.text.toLowerCase().includes(query);
        return textMatches && nodeMatchesStatus(node, nodeFilters.status);
    }

    function nodeHasVisibleMatch(node) {
        if (nodeMatchesOwnFilter(node)) return true;
        return (node.children || []).some(child => nodeHasVisibleMatch(child));
    }

    function isNodeFiltering() {
        return Boolean(nodeFilters.query.trim()) || nodeFilters.status !== 'all';
    }

    function projectMatchesFilter(project) {
        const query = projectFilters.query.trim().toLowerCase();
        const textMatches = !query || `${project.name} ${project.description || ''}`.toLowerCase().includes(query);
        if (!textMatches) return false;
        const total = getProjectTotal(project);
        const remaining = getProjectRemaining(project);
        if (projectFilters.status === 'active') return remaining > 0;
        if (projectFilters.status === 'completed') return total > 0 && remaining === 0;
        if (projectFilters.status === 'empty') return total === 0;
        return true;
    }

    function getVisibleProjects() {
        return projects.filter(projectMatchesFilter);
    }

    async function exportBackup() {
        await createDatabaseBackupFromUi();
        const name = databaseBackupSelect.value;
        if (!name) return;
        const link = document.createElement('a');
        link.href = `${getAssessmentApiUrl('/api/backup/download')}?name=${encodeURIComponent(name)}&token=${encodeURIComponent(sessionToken)}`;
        link.download = name;
        document.body.appendChild(link);
        link.click();
        link.remove();
        showToast(`正在下载完整数据库备份：${name}`);
    }

    function clearAssessmentHistoryInDetail() {
        const project = getCurrentProject();
        if (!project) return;
        const removableKeys = new Set([
            'questionSet', 'questionIndex', 'questionAnswers', 'questionConversations',
            'questionResults', 'answer', 'implementationDraft', 'reply'
        ]);
        const candidates = [];
        function walk(nodes) {
            for (const node of nodes || []) {
                if (node.type === 'item' && node.assessment && typeof node.assessment === 'object') {
                    const assessment = node.assessment;
                    const hasHistory = Array.from(removableKeys).some(key => {
                        const value = assessment[key];
                        return Array.isArray(value) ? value.length > 0 : Boolean(value);
                    });
                    if (hasHistory) {
                        candidates.push(node);
                    }
                }
                walk(node.children);
            }
        }
        walk(project.tree);
        if (candidates.length === 0) {
            showToast('当前项目没有可清理的验收记录');
            return;
        }
        if (!window.confirm(`确认清理 ${candidates.length} 个任务的 AI 对话、题目历史和草稿？已通过状态与评分会保留。`)) return;
        candidates.forEach(node => {
            const preserved = Object.fromEntries(
                Object.entries(node.assessment).filter(([key]) => !removableKeys.has(key))
            );
            node.assessment = Object.keys(preserved).length > 0 ? preserved : null;
        });
        saveProjects();
        renderDetail();
        showToast(`已清理 ${candidates.length} 个任务的验收记录`);
    }

    async function importBackup(file) {
        if (!file) return;
        try {
            const payload = JSON.parse(await file.text());
            const imported = extractProjects(payload);
            if (!imported) throw new Error('备份文件格式不正确');
            const nextProjects = normalizeProjects(imported);
            if (!window.confirm(`确认导入 ${nextProjects.length} 个项目？当前数据将被替换。`)) return;
            ensureRemedialQueueAtBottom(nextProjects);
            nextProjects.forEach(project => expandAllNodes(project.tree || [], false));
            if (saveTimer) await flushProjectsSave();
            await saveQueue;
            const response = await apiFetch('/api/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ projects: nextProjects.map(serializeProject) })
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok || !Array.isArray(result.projects)) {
                throw new Error(result.error || 'SQLite 导入失败');
            }
            projects = result.projects.map(normalizeProjectSummary);
            savedProjectJsonById.clear();
            saveConflict = false;
            currentProjectId = null;
            renderProjects();
            showToast(`已导入 ${projects.length} 个项目`);
        } catch (error) {
            console.error('导入备份失败', error);
            showToast(`导入失败：${error.message || '文件无法读取'}`);
        } finally {
            importInput.value = '';
        }
    }

    const studyActionNames = {
        focus: '今日聚焦',
        random: '随机复习',
        stats: '进度统计'
    };

    function showUtilityModal(title, kicker = '学习工具') {
        utilityTitle.textContent = title;
        utilityKicker.textContent = kicker;
        utilityModal.hidden = false;
        document.body.classList.add('modal-open');
        utilityModal.querySelector('.utility-dialog').classList.toggle('memo-dialog', kicker === '个人记录');
    }

    function closeUtilityModal() {
        if (memoState.saveTimer) {
            clearTimeout(memoState.saveTimer);
            memoState.saveTimer = null;
            const memo = memoState.memos.find(item => item.id === memoState.pendingMemoId) || currentMemo();
            memoState.pendingMemoId = null;
            if (memo) {
                persistMemo(memo).catch(error => console.error('关闭备忘录时保存失败', error));
            }
        }
        utilityModal.hidden = true;
        utilityBody.innerHTML = '';
        document.body.classList.remove('modal-open');
    }

    async function loadMemos() {
        const response = await apiFetch('/api/memos', { cache: 'no-store' });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !Array.isArray(payload.memos)) throw new Error(payload.error || '读取备忘录失败');
        memoState.memos = payload.memos;
        if (!memoState.memos.some(memo => memo.id === memoState.selectedId)) {
            memoState.selectedId = memoState.memos[0]?.id || null;
        }
    }

    function currentMemo() {
        return memoState.memos.find(memo => memo.id === memoState.selectedId) || null;
    }

    function persistMemo(memo) {
        if (!memo) return Promise.resolve(null);
        const snapshot = { id: memo.id, title: memo.title, content: memo.content, pinned: memo.pinned };
        const operation = memoState.saveQueue.catch(() => undefined).then(async () => {
            const current = memoState.memos.find(item => item.id === snapshot.id);
            if (!current) return null;
            const response = await apiFetch('/api/memo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...snapshot, expectedRevision: current.revision })
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || !payload.memo) throw new Error(payload.error || '保存备忘录失败');
            Object.assign(current, payload.memo);
            if (memo !== current) Object.assign(memo, payload.memo);
            return payload.memo;
        });
        memoState.saveQueue = operation.catch(() => undefined);
        return operation;
    }

    function setMemoSaveStatus(text, state = '') {
        const status = utilityBody.querySelector('.memo-save-status');
        if (status) {
            status.textContent = text;
            status.classList.toggle('error', state === 'error');
        }
    }

    async function saveMemoNow(memo = currentMemo()) {
        if (!memo) return;
        if (memoState.saveTimer && memoState.pendingMemoId === memo.id) {
            clearTimeout(memoState.saveTimer);
            memoState.saveTimer = null;
            memoState.pendingMemoId = null;
        }
        const button = utilityBody.querySelector('.memo-save-btn');
        if (button) {
            button.disabled = true;
            button.textContent = '保存中…';
        }
        setMemoSaveStatus('正在写入 SQLite…');
        try {
            const saved = await persistMemo(memo);
            if (saved) setMemoSaveStatus(`已保存 · ${saved.updatedAt}`);
            setSaveStatus('已保存');
            return saved;
        } catch (error) {
            setMemoSaveStatus(error.message || '保存失败', 'error');
            setSaveStatus('保存失败', 'error');
            throw error;
        } finally {
            if (button) {
                button.disabled = false;
                button.textContent = '保存';
            }
        }
    }

    function scheduleMemoSave() {
        const target = currentMemo();
        if (!target) return;
        setMemoSaveStatus('尚未保存');
        memoState.pendingMemoId = target.id;
        if (memoState.saveTimer) clearTimeout(memoState.saveTimer);
        memoState.saveTimer = window.setTimeout(async () => {
            memoState.saveTimer = null;
            memoState.pendingMemoId = null;
            const memo = memoState.memos.find(item => item.id === target.id);
            try {
                await saveMemoNow(memo);
            } catch (error) {
                showToast(error.message || '备忘录保存失败');
            }
        }, 450);
    }

    function renderMemoList(container, editor) {
        container.innerHTML = '';
        const query = memoState.query.trim().toLowerCase();
        const visible = memoState.memos.filter(memo => !query
            || `${memo.title} ${memo.content}`.toLowerCase().includes(query));
        if (visible.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'memo-empty';
            empty.textContent = query ? '没有匹配的备忘录' : '还没有备忘录';
            container.appendChild(empty);
            return;
        }
        visible.forEach(memo => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = `memo-list-item${memo.id === memoState.selectedId ? ' selected' : ''}`;
            const title = document.createElement('strong');
            title.textContent = memo.title || '未命名备忘录';
            const preview = document.createElement('small');
            preview.textContent = memo.content.replace(/\s+/g, ' ').trim() || '暂无内容';
            const meta = document.createElement('span');
            meta.textContent = memo.pinned ? '置顶 · ' + memo.updatedAt.slice(0, 10) : memo.updatedAt.slice(0, 10);
            button.append(title, preview, meta);
            button.addEventListener('click', async () => {
                const previous = currentMemo();
                if (previous && memoState.saveTimer) {
                    try {
                        await saveMemoNow(previous);
                    } catch (error) {
                        showToast('当前备忘录尚未保存，暂不能切换');
                        return;
                    }
                }
                memoState.selectedId = memo.id;
                renderMemoPanel();
            });
            container.appendChild(button);
        });
    }

    function renderMemoPanel() {
        showUtilityModal('备忘录', '个人记录');
        utilityBody.innerHTML = '';
        const toolbar = document.createElement('div');
        toolbar.className = 'memo-toolbar';
        const search = document.createElement('input');
        search.type = 'search';
        search.className = 'memo-search';
        search.placeholder = '搜索备忘录';
        search.value = memoState.query;
        search.addEventListener('input', () => {
            memoState.query = search.value;
            renderMemoList(list, editor);
        });
        const newButton = document.createElement('button');
        newButton.type = 'button';
        newButton.className = 'utility-primary-btn';
        newButton.textContent = '＋ 新建';
        newButton.addEventListener('click', async () => {
            try {
                if (currentMemo() && memoState.saveTimer) await saveMemoNow(currentMemo());
                const response = await apiFetch('/api/memo', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: '未命名备忘录', content: '', pinned: false })
                });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok || !payload.memo) throw new Error(payload.error || '新建备忘录失败');
                memoState.memos.unshift(payload.memo);
                memoState.selectedId = payload.memo.id;
                memoState.query = '';
                renderMemoPanel();
                editorFocusTitle();
            } catch (error) {
                showToast(error.message || '新建备忘录失败');
            }
        });
        toolbar.append(search, newButton);
        utilityBody.appendChild(toolbar);
        const layout = document.createElement('div');
        layout.className = 'memo-layout';
        const list = document.createElement('div');
        list.className = 'memo-list';
        const editor = document.createElement('div');
        editor.className = 'memo-editor';
        layout.append(list, editor);
        utilityBody.appendChild(layout);
        const memo = currentMemo();
        if (memo) {
            const titleInput = document.createElement('input');
            titleInput.type = 'text';
            titleInput.className = 'memo-title-input';
            titleInput.value = memo.title;
            titleInput.placeholder = '备忘录标题';
            titleInput.addEventListener('input', () => {
                memo.title = titleInput.value || '未命名备忘录';
                scheduleMemoSave();
                renderMemoList(list, editor);
            });
            const contentInput = document.createElement('textarea');
            contentInput.className = 'memo-content-input';
            contentInput.value = memo.content;
            contentInput.placeholder = '记录想法、命令、代码片段或待办事项…';
            contentInput.addEventListener('input', () => {
                memo.content = contentInput.value;
                scheduleMemoSave();
                renderMemoList(list, editor);
            });
            const editorToolbar = document.createElement('div');
            editorToolbar.className = 'memo-editor-toolbar';
            const pinButton = document.createElement('button');
            pinButton.type = 'button';
            pinButton.className = 'utility-secondary-btn';
            pinButton.textContent = memo.pinned ? '★ 已置顶' : '☆ 置顶';
            pinButton.addEventListener('click', async () => {
                if (memoState.saveTimer) {
                    try { await saveMemoNow(memo); } catch (error) { showToast('请先解决保存失败'); return; }
                }
                memo.pinned = !memo.pinned;
                pinButton.textContent = memo.pinned ? '★ 已置顶' : '☆ 置顶';
                try {
                    await persistMemo(memo);
                    renderMemoList(list, editor);
                } catch (error) {
                    showToast(error.message || '保存置顶状态失败');
                }
            });
            const deleteButton = document.createElement('button');
            deleteButton.type = 'button';
            deleteButton.className = 'utility-secondary-btn memo-delete-btn';
            deleteButton.textContent = '删除';
            deleteButton.addEventListener('click', async () => {
                if (!window.confirm(`确认删除“${memo.title}”？`)) return;
                if (memoState.saveTimer) {
                    clearTimeout(memoState.saveTimer);
                    memoState.saveTimer = null;
                    memoState.pendingMemoId = null;
                }
                try {
                    await memoState.saveQueue;
                    const response = await apiFetch(`/api/memo?id=${encodeURIComponent(memo.id)}&revision=${encodeURIComponent(memo.revision)}`, { method: 'DELETE' });
                    const payload = await response.json().catch(() => ({}));
                    if (!response.ok) throw new Error(payload.error || '删除备忘录失败');
                    memoState.memos = payload.memos || memoState.memos.filter(item => item.id !== memo.id);
                    memoState.selectedId = memoState.memos[0]?.id || null;
                    renderMemoPanel();
                } catch (error) {
                    showToast(error.message || '删除备忘录失败');
                }
            });
            const saveGroup = document.createElement('div');
            saveGroup.className = 'memo-save-group';
            const saveStatus = document.createElement('span');
            saveStatus.className = 'memo-save-status';
            saveStatus.textContent = `已保存 · ${memo.updatedAt}`;
            const saveButton = document.createElement('button');
            saveButton.type = 'button';
            saveButton.className = 'utility-primary-btn memo-save-btn';
            saveButton.textContent = '保存';
            saveButton.addEventListener('click', async () => {
                try {
                    await saveMemoNow(memo);
                    renderMemoList(list, editor);
                } catch (error) {
                    showToast(error.message || '备忘录保存失败');
                }
            });
            saveGroup.append(saveStatus, saveButton, deleteButton);
            editorToolbar.append(pinButton, saveGroup);
            const updated = document.createElement('small');
            updated.className = 'memo-updated';
            updated.textContent = `最近修改：${memo.updatedAt}`;
            editor.append(titleInput, contentInput, editorToolbar, updated);
            editorFocusTitle = () => titleInput.focus();
        } else {
            const empty = document.createElement('p');
            empty.className = 'memo-empty';
            empty.textContent = '新建一条备忘录开始记录';
            editor.appendChild(empty);
        }
        renderMemoList(list, editor);
        const databaseTools = document.createElement('div');
        databaseTools.className = 'memo-database-tools';
        const exportButton = document.createElement('button');
        exportButton.type = 'button';
        exportButton.className = 'utility-secondary-btn';
        exportButton.textContent = '↓ 导出备忘录数据库';
        exportButton.addEventListener('click', downloadMemoDatabase);
        const importLabel = document.createElement('label');
        importLabel.className = 'utility-secondary-btn memo-import-label';
        importLabel.textContent = '↑ 导入备忘录数据库';
        const importInput = document.createElement('input');
        importInput.type = 'file';
        importInput.accept = '.sqlite3,.db,application/vnd.sqlite3';
        importInput.addEventListener('change', () => importMemoDatabase(importInput.files?.[0]));
        importLabel.appendChild(importInput);
        databaseTools.append(exportButton, importLabel);
        utilityBody.appendChild(databaseTools);
    }

    let editorFocusTitle = () => undefined;

    async function openMemoTool() {
        showUtilityModal('备忘录', '个人记录');
        utilityBody.innerHTML = '<p class="utility-empty">正在读取备忘录…</p>';
        try {
            await loadMemos();
            renderMemoPanel();
        } catch (error) {
            utilityBody.innerHTML = `<p class="utility-empty">${error.message || '读取备忘录失败'}</p>`;
        }
    }

    async function downloadMemoDatabase() {
        try {
            const response = await apiFetch('/api/memos/database-download', { cache: 'no-store' });
            if (!response.ok) throw new Error('导出备忘录数据库失败');
            const blob = await response.blob();
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = 'memo.sqlite3';
            link.click();
            URL.revokeObjectURL(link.href);
            showToast('已导出独立备忘录数据库');
        } catch (error) {
            showToast(error.message || '导出备忘录数据库失败');
        }
    }

    async function importMemoDatabase(file) {
        if (!file) return;
        if (!window.confirm('导入会替换当前全部备忘录，项目数据库不会改变。确认继续？')) return;
        try {
            const response = await apiFetch('/api/memos/database-import', { method: 'POST', body: await file.arrayBuffer() });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || !Array.isArray(payload.memos)) throw new Error(payload.error || '导入备忘录数据库失败');
            memoState.memos = payload.memos;
            memoState.selectedId = memoState.memos[0]?.id || null;
            memoState.query = '';
            renderMemoPanel();
            showToast('已导入独立备忘录数据库');
        } catch (error) {
            showToast(error.message || '导入备忘录数据库失败');
        }
    }

    function createOptionalToggle(checked, onChange) {
        const label = document.createElement('label');
        label.className = 'utility-option-toggle';
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.checked = checked;
        const text = document.createElement('span');
        text.textContent = '包含选做任务';
        input.addEventListener('change', () => onChange(input.checked));
        label.append(input, text);
        return label;
    }

    function createTaskButton(entry, projectId) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'utility-task';
        const content = document.createElement('span');
        content.className = 'utility-task-content';
        const name = document.createElement('strong');
        name.textContent = entry.text;
        const path = document.createElement('small');
        path.textContent = entry.path || '项目任务';
        content.append(name, path);
        if (entry.optional) {
            const badge = document.createElement('span');
            badge.className = 'utility-task-badge';
            badge.textContent = '选做';
            content.appendChild(badge);
        }
        const arrow = document.createElement('span');
        arrow.className = 'utility-task-arrow';
        arrow.textContent = '→';
        button.append(content, arrow);
        button.addEventListener('click', () => locateStudyTask(projectId, entry));
        return button;
    }

    async function locateStudyTask(projectId, entry) {
        closeUtilityModal();
        try {
            const project = await ensureProjectLoaded(projectId);
            expandAllNodes(project.tree || [], false);
            for (const ancestorId of entry.ancestorIds || []) {
                const ancestor = findNodeById(project.tree || [], ancestorId);
                if (ancestor && ancestor.type !== 'item') ancestor.expanded = true;
            }
            nodeFilters.query = '';
            nodeFilters.status = 'all';
            nodeSearchInput.value = '';
            nodeStatusFilter.value = 'all';
            showDetailView(project.id);
            requestAnimationFrame(() => requestAnimationFrame(() => {
                const nodeElement = [...treeRoot.querySelectorAll('.tree-node')]
                    .find(element => element.dataset.id === String(entry.id));
                if (!nodeElement) return;
                const row = nodeElement.querySelector(':scope > .node-row');
                row?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                row?.classList.add('located-row');
                window.setTimeout(() => row?.classList.remove('located-row'), 1800);
            }));
        } catch (error) {
            showToast(error.message || '任务定位失败');
        }
    }

    function renderProjectPicker(action) {
        showUtilityModal(`选择项目 · ${studyActionNames[action]}`, '选择范围');
        utilityBody.innerHTML = '';
        const hint = document.createElement('p');
        hint.className = 'utility-hint';
        hint.textContent = '选择一个项目后继续，不会自动修改任何任务。';
        utilityBody.appendChild(hint);
        const list = document.createElement('div');
        list.className = 'project-choice-list';
        for (const project of projects) {
            const total = getProjectTotal(project);
            const completed = total - getProjectRemaining(project);
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'project-choice';
            const text = document.createElement('span');
            const name = document.createElement('strong');
            name.textContent = project.name;
            const progress = document.createElement('small');
            progress.textContent = total > 0 ? `主线 ${completed}/${total}` : '暂无主线任务';
            text.append(name, progress);
            const arrow = document.createElement('span');
            arrow.textContent = '→';
            button.append(text, arrow);
            button.addEventListener('click', async () => {
                button.disabled = true;
                try {
                    const loaded = await ensureProjectLoaded(project.id);
                    renderStudyTool(action, loaded);
                } catch (error) {
                    showToast(error.message || '项目加载失败');
                    button.disabled = false;
                }
            });
            list.appendChild(button);
        }
        if (projects.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'utility-empty';
            empty.textContent = '还没有可选择的项目';
            utilityBody.appendChild(empty);
        } else {
            utilityBody.appendChild(list);
        }
    }

    function renderFocusTool(project) {
        let includeOptional = false;
        let visibleCount = 10;
        showUtilityModal(project.name, '今日聚焦');
        const draw = () => {
            utilityBody.innerHTML = '';
            const toolbar = document.createElement('div');
            toolbar.className = 'utility-toolbar';
            const summary = document.createElement('span');
            const entries = studyTools.collectTaskEntries(project.tree || [], includeOptional);
            summary.textContent = entries.length > 0 ? `${entries.length} 项待完成` : '当前范围已完成';
            toolbar.append(summary, createOptionalToggle(includeOptional, value => {
                includeOptional = value;
                visibleCount = 10;
                draw();
            }));
            utilityBody.appendChild(toolbar);
            if (entries.length === 0) {
                const empty = document.createElement('p');
                empty.className = 'utility-empty';
                empty.textContent = includeOptional ? '主线和选做任务都已完成。' : '主线任务已全部完成，可选择包含选做任务。';
                utilityBody.appendChild(empty);
                return;
            }
            const list = document.createElement('div');
            list.className = 'utility-task-list';
            entries.slice(0, visibleCount).forEach(entry => list.appendChild(createTaskButton(entry, project.id)));
            utilityBody.appendChild(list);
            if (visibleCount < entries.length) {
                const more = document.createElement('button');
                more.type = 'button';
                more.className = 'utility-more-btn';
                more.textContent = `再显示 ${Math.min(10, entries.length - visibleCount)} 项`;
                more.addEventListener('click', () => {
                    visibleCount += 10;
                    draw();
                });
                utilityBody.appendChild(more);
            }
        };
        draw();
    }

    function renderRandomTool(project) {
        let includeOptional = false;
        let currentEntry = null;
        showUtilityModal(project.name, '随机复习');
        const draw = (chooseNew = false) => {
            utilityBody.innerHTML = '';
            const entries = studyTools.collectTaskEntries(project.tree || [], includeOptional);
            if (chooseNew || !currentEntry || !entries.some(entry => String(entry.id) === String(currentEntry.id))) {
                const candidates = currentEntry && entries.length > 1
                    ? entries.filter(entry => String(entry.id) !== String(currentEntry.id))
                    : entries;
                currentEntry = studyTools.chooseRandomTask(candidates);
            }
            const toolbar = document.createElement('div');
            toolbar.className = 'utility-toolbar';
            const summary = document.createElement('span');
            summary.textContent = entries.length > 0 ? `从 ${entries.length} 项中抽取` : '当前范围已完成';
            toolbar.append(summary, createOptionalToggle(includeOptional, value => {
                includeOptional = value;
                currentEntry = null;
                draw(true);
            }));
            utilityBody.appendChild(toolbar);
            if (!currentEntry) {
                const optionalEntries = studyTools.collectTaskEntries(project.tree || [], true)
                    .filter(entry => entry.optional);
                const empty = document.createElement('p');
                empty.className = 'utility-empty';
                empty.textContent = optionalEntries.length > 0 && !includeOptional
                    ? '主线任务已全部完成，可以抽取一道选做任务。'
                    : '当前范围没有未完成任务。';
                utilityBody.appendChild(empty);
                if (optionalEntries.length > 0 && !includeOptional) {
                    const optionalButton = document.createElement('button');
                    optionalButton.type = 'button';
                    optionalButton.className = 'utility-primary-btn';
                    optionalButton.textContent = '抽一个选做任务';
                    optionalButton.addEventListener('click', () => {
                        includeOptional = true;
                        draw(true);
                    });
                    utilityBody.appendChild(optionalButton);
                }
                return;
            }
            const result = document.createElement('div');
            result.className = 'random-result';
            const label = document.createElement('span');
            label.textContent = currentEntry.optional ? '本次抽到 · 选做' : '本次抽到';
            const name = document.createElement('strong');
            name.textContent = currentEntry.text;
            const path = document.createElement('small');
            path.textContent = currentEntry.path || '项目任务';
            result.append(label, name, path);
            utilityBody.appendChild(result);
            const actions = document.createElement('div');
            actions.className = 'utility-actions';
            const again = document.createElement('button');
            again.type = 'button';
            again.className = 'utility-secondary-btn';
            again.textContent = '⌁ 再抽一个';
            again.addEventListener('click', () => draw(true));
            const go = document.createElement('button');
            go.type = 'button';
            go.className = 'utility-primary-btn';
            go.textContent = '去复习 →';
            go.addEventListener('click', () => locateStudyTask(project.id, currentEntry));
            actions.append(again, go);
            utilityBody.appendChild(actions);
        };
        draw(true);
    }

    function renderStatsTool(project) {
        const stats = studyTools.calculateProgressStats(project.tree || []);
        showUtilityModal(project.name, '进度统计');
        utilityBody.innerHTML = '';
        const overview = document.createElement('div');
        overview.className = 'stats-overview';
        const rate = document.createElement('strong');
        rate.textContent = `${stats.completionRate}%`;
        const label = document.createElement('span');
        label.textContent = `总进度 · ${stats.completed}/${stats.total}`;
        const track = document.createElement('div');
        track.className = 'stats-progress';
        const fill = document.createElement('span');
        fill.style.width = `${stats.completionRate}%`;
        track.appendChild(fill);
        overview.append(rate, label, track);
        utilityBody.appendChild(overview);
        const grid = document.createElement('div');
        grid.className = 'stats-grid';
        const facts = [
            ['主线任务', `${stats.mainCompleted}/${stats.mainTotal}`],
            ['选做任务', `${stats.optionalCompleted}/${stats.optionalTotal}`],
            ['完成最多的一周', stats.busiestWeek
                ? `${stats.busiestWeek.year} 年第 ${stats.busiestWeek.week} 周 · ${stats.busiestWeek.count} 项`
                : '暂无时间记录'],
            ['最近完成', stats.latestCompletion
                ? `${new Date(stats.latestCompletion.completedAt).toLocaleString('zh-CN', { hour12: false })} · ${stats.latestCompletion.text}`
                : '暂无时间记录']
        ];
        facts.forEach(([name, value]) => {
            const item = document.createElement('div');
            item.className = 'stats-item';
            const itemLabel = document.createElement('span');
            itemLabel.textContent = name;
            const itemValue = document.createElement('strong');
            itemValue.textContent = value;
            item.append(itemLabel, itemValue);
            grid.appendChild(item);
        });
        utilityBody.appendChild(grid);
        const reviewStats = collectReviewStats(project.tree || []);
        if (reviewStats.count > 0) {
            const reviewHeading = document.createElement('div');
            reviewHeading.className = 'stats-group-heading';
            reviewHeading.textContent = '间隔复习';
            utilityBody.appendChild(reviewHeading);
            const grid2 = document.createElement('div');
            grid2.className = 'stats-grid';
            const rows2 = [
                ['近 7 天复习', String(reviewStats.last7) + ' 次'],
                ['连续复习', String(reviewStats.streak) + ' 天'],
                ['待复习(含逾期)', String(reviewStats.due) + ' 项'],
                ['需重学', String(reviewStats.learning) + ' 项']
            ];
            rows2.forEach((pair) => {
                const cell = document.createElement('div');
                cell.className = 'stats-item';
                const cellLabel = document.createElement('span');
                cellLabel.textContent = pair[0];
                const cellValue = document.createElement('strong');
                cellValue.textContent = pair[1];
                cell.append(cellLabel, cellValue);
                grid2.appendChild(cell);
            });
            utilityBody.appendChild(grid2);
        }
    }

    function renderStudyTool(action, project) {
        if (!studyTools) {
            showToast('学习工具加载失败，请刷新页面');
            return;
        }
        if (action === 'focus') renderFocusTool(project);
        else if (action === 'random') renderRandomTool(project);
        else renderStatsTool(project);
    }

    function openStudyTool(action) {
        const project = getCurrentProject();
        if (project) renderStudyTool(action, project);
        else renderProjectPicker(action);
    }

    function renderProjects() {
        projectGrid.innerHTML = '';
        const reviewTotal = reviewCounts.today + reviewCounts.overdue;
        if (reviewQueueCount) {
            reviewQueueCount.textContent = String(reviewTotal);
            reviewQueueBtn.classList.toggle('empty', reviewTotal === 0);
        }
        const visibleProjects = getVisibleProjects();
        if (projects.length === 0) {
            emptyProjects.style.display = 'block';
            emptyProjects.textContent = '还没有项目，创建一个开始学习吧 ✨';
            return;
        }
        if (visibleProjects.length === 0) {
            emptyProjects.style.display = 'block';
            emptyProjects.textContent = '没有符合筛选条件的项目';
            return;
        }
        emptyProjects.style.display = 'none';
        visibleProjects.forEach(project => {
            const card = document.createElement('div');
            card.className = 'project-card';
            card.dataset.id = project.id;
            const total = getProjectTotal(project);
            const completed = total - getProjectRemaining(project);
            const optional = getProjectOptionalStats(project);
            const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
            const top = document.createElement('div');
            top.className = 'card-top';
            const icon = document.createElement('span');
            icon.className = 'card-icon';
            icon.textContent = '▱';
            const info = document.createElement('div');
            info.className = 'card-info';
            const nameDiv = document.createElement('div');
            nameDiv.className = 'card-name';
            nameDiv.textContent = project.name;
            const metaDiv = document.createElement('div');
            metaDiv.className = 'card-meta';
            const createdSpan = document.createElement('span');
            createdSpan.textContent = '创建于 ' + (project.createdAt || '未知');
            metaDiv.appendChild(createdSpan);
            info.appendChild(nameDiv);
            if (project.description) {
                const description = document.createElement('div');
                description.className = 'card-description';
                description.textContent = project.description;
                info.appendChild(description);
            }
            const projectCounts = reviewCounts.byProject.get(String(project.id));
            if (projectCounts && (projectCounts.today > 0 || projectCounts.overdue > 0)) {
                const reviewBadge = document.createElement('span');
                reviewBadge.className = 'review-card-badge' + (projectCounts.overdue > 0 ? ' overdue' : '');
                reviewBadge.textContent = projectCounts.overdue > 0
                    ? '待复习 ' + projectCounts.today + ' · 逾期 ' + projectCounts.overdue
                    : '待复习 ' + projectCounts.today;
                metaDiv.appendChild(reviewBadge);
            }
            info.appendChild(metaDiv);
            const actions = document.createElement('div');
            actions.className = 'card-actions';
            const editBtn = document.createElement('button');
            editBtn.innerHTML = '✎';
            editBtn.title = '编辑项目名称';
            editBtn.setAttribute('aria-label', '编辑项目名称');
            editBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                try {
                    const loadedProject = await ensureProjectLoaded(project.id);
                    startEditProjectName(loadedProject, nameDiv, card);
                } catch (error) {
                    showToast(error.message || '项目加载失败');
                }
            });
            const delBtn = document.createElement('button');
            delBtn.innerHTML = '✕';
            delBtn.title = '删除项目';
            delBtn.setAttribute('aria-label', '删除项目');
            delBtn.classList.add('delete-proj-btn');
            delBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteProject(project.id, card);
            });
            actions.appendChild(editBtn);
            actions.appendChild(delBtn);
            top.appendChild(icon);
            top.appendChild(info);
            top.appendChild(actions);
            const progressBar = document.createElement('div');
            progressBar.className = 'card-progress';
            const progressBarInner = document.createElement('div');
            progressBarInner.className = 'card-progress-bar';
            progressBarInner.style.width = pct + '%';
            progressBar.appendChild(progressBarInner);
            const metrics = document.createElement('div');
            metrics.className = 'card-metrics';
            const percentage = document.createElement('strong');
            percentage.textContent = `${pct}%`;
            const metricText = document.createElement('span');
            metricText.textContent = `主线 ${completed}/${total}`;
            const optionalText = document.createElement('small');
            optionalText.textContent = `选做 ${optional.completed}/${optional.total}`;
            metrics.append(percentage, metricText, optionalText, progressBar);
            card.appendChild(top);
            card.appendChild(metrics);
            card.addEventListener('click', async () => {
                try {
                    await openProjectDetail(project.id);
                } catch (error) {
                    showToast(error.message || '项目加载失败');
                }
            });
            nameDiv.addEventListener('dblclick', async (e) => {
                e.stopPropagation();
                try {
                    const loadedProject = await ensureProjectLoaded(project.id);
                    startEditProjectName(loadedProject, nameDiv, card);
                } catch (error) {
                    showToast(error.message || '项目加载失败');
                }
            });
            projectGrid.appendChild(card);
        });
    }

    function startEditProjectName(project, nameDiv, card) {
        const input = document.createElement('input');
        input.type = 'text';
        input.value = project.name;
        input.style.width = '100%';
        input.style.padding = '6px 10px';
        input.style.fontSize = '15px';
        input.style.fontWeight = '600';
        input.style.border = '2px solid var(--primary)';
        input.style.borderRadius = '6px';
        input.style.outline = 'none';
        input.style.boxShadow = '0 0 0 3px var(--primary-soft)';
        nameDiv.replaceWith(input);
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
        const save = () => {
            const newName = input.value.trim();
            if (newName) {
                project.name = newName;
                saveProjects();
            }
            renderProjects();
        };
        input.addEventListener('blur', save);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') input.blur();
            if (e.key === 'Escape') {
                input.removeEventListener('blur', save);
                renderProjects();
            }
        });
    }

    async function deleteProject(projectId, card) {
        const projectIndex = projects.findIndex(project => project.id === projectId);
        if (projectIndex < 0) return;
        const removedProject = projects[projectIndex];
        if (!window.confirm(`确认删除项目“${removedProject.name}”？删除前会保留数据库备份。`)) return;
        try {
            setSaveStatus('保存中…', 'saving');
            await deleteStoredProject(projectId, removedProject._revision);
        } catch (error) {
            setSaveStatus(error.status === 409 ? '版本冲突' : '保存失败', 'error');
            showToast(error.message || '删除项目失败');
            return;
        }
        card.style.transition = 'all 0.35s ease';
        card.style.opacity = '0';
        card.style.transform = 'translateX(30px)';
        card.style.maxHeight = card.offsetHeight + 'px';
        setTimeout(() => {
            card.style.maxHeight = '0';
            card.style.padding = '0 20px';
            card.style.marginBottom = '-12px';
        }, 50);
        setTimeout(() => {
            projects.splice(projectIndex, 1);
            if (currentProjectId === projectId) currentProjectId = null;
            renderProjects();
            setSaveStatus('已保存');
            showToast(`已删除项目：${removedProject.name}`);
        }, 400);
    }

    function renderDetail() {
        const project = getCurrentProject();
        if (!project) {
            showProjectsView();
            return;
        }
        detailTitle.textContent = project.name;
        detailDate.textContent = '创建于 ' + (project.createdAt || '未知');
        projectAssessmentToggle.checked = Boolean(project.assessmentEnabled);
        projectAssessmentToggle.parentElement.classList.toggle('enabled', project.assessmentEnabled);
        if (projectReviewToggle) {
            projectReviewToggle.checked = Boolean(
                typeof project.reviewEnabled === 'boolean' ? project.reviewEnabled : project.assessmentEnabled
            );
            projectReviewToggle.parentElement.classList.toggle('enabled', projectReviewToggle.checked);
        }
        const remaining = getProjectRemaining(project);
        const optional = getProjectOptionalStats(project);
        countDisplay.textContent = `主线剩余 ${remaining} 项 · 选做 ${optional.completed}/${optional.total}`;
        treeRoot.innerHTML = '';
        if (!project.tree || project.tree.length === 0) {
            emptyTreeTip.textContent = '还没有内容，添加第一周开始吧 ✨';
            emptyTreeTip.classList.remove('hidden');
            return;
        }
        const filtering = isNodeFiltering();
        const visibleTree = filtering ? project.tree.filter(nodeHasVisibleMatch) : project.tree;
        if (visibleTree.length === 0) {
            emptyTreeTip.textContent = '没有符合筛选条件的内容';
            emptyTreeTip.classList.remove('hidden');
            return;
        }
        emptyTreeTip.textContent = '还没有内容，添加第一周开始吧 ✨';
        emptyTreeTip.classList.add('hidden');
        const projectCreatedAt = project.createdAt || '';
        visibleTree.forEach(week => {
            treeRoot.appendChild(renderNode(week, projectCreatedAt, filtering));
        });
        const allExpanded = (project.tree || []).every(w => w.expanded);
        expandAllBtn.textContent = allExpanded ? '收起全部' : '展开全部';
    }

    function renderNode(node, projectCreatedAt, filtering = false) {
        const li = document.createElement('li');
        li.className = 'tree-node';
        li.dataset.id = node.id;
        li.dataset.type = node.type;
        const row = document.createElement('div');
        row.className = 'node-row';
        if (node.optional) row.classList.add('optional-row');
        const completionState = getNodeCompletionState(node);
        if (completionState === 'completed') row.classList.add('completed-row');
        const arrow = document.createElement('span');
        arrow.className = 'arrow';
        if (node.type === 'item') {
            arrow.classList.add('leaf');
        } else {
            arrow.textContent = '▶';
            if (node.expanded) arrow.classList.add('expanded');
        }
        const checkbox = document.createElement('span');
        checkbox.className = 'checkbox';
        if (completionState === 'completed') checkbox.classList.add('checked');
        if (completionState === 'partial') checkbox.classList.add('indeterminate');
        checkbox.setAttribute('role', 'checkbox');
        checkbox.setAttribute('aria-checked', completionState === 'partial' ? 'mixed' : completionState === 'completed');
        if (node.type === 'item' && node.completedAt) {
            const completedDate = new Date(node.completedAt);
            if (!Number.isNaN(completedDate.getTime())) {
                checkbox.title = `完成于 ${completedDate.toLocaleString('zh-CN', { hour12: false })}`;
            }
        }
        checkbox.tabIndex = 0;
        const textSpan = document.createElement('span');
        textSpan.className = 'node-text' + (completionState === 'completed' ? ' completed-text' : '');
        textSpan.textContent = node.text;
        const optionalBadge = node.optional ? document.createElement('span') : null;
        if (optionalBadge) {
            optionalBadge.className = 'optional-badge';
            optionalBadge.textContent = '选做';
        }
        const assessmentBadge = node.assessmentRequired ? document.createElement('span') : null;
        if (assessmentBadge) {
            const assessed = node.assessment && Number.isFinite(node.assessment.score);
            const questionPassed = node.assessment && node.assessment.questionPassed && !node.completed;
            assessmentBadge.className = 'assessment-badge' + (assessed ? '' : ' pending');
            assessmentBadge.textContent = assessed
                ? (node.assessment.passed ? '通过' : '补漏')
                : questionPassed
                    ? '题目通过 · 待写代码'
                    : (node.assessmentHistory > 0 ? `曾通过 ${node.assessmentHistory} 次 · 待验收` : '待验收');
        }
        const dateSpan = document.createElement('span');
        dateSpan.className = 'node-date';
        dateSpan.textContent = node.createdAt || projectCreatedAt;
        const actions = document.createElement('span');
        actions.className = 'node-actions';
        if (node.type === 'week' || node.type === 'day') {
            const addBtn = document.createElement('button');
            addBtn.className = 'add-btn';
            addBtn.innerHTML = '+';
            addBtn.title = node.type === 'week' ? '添加学习单元' : '添加任务';
            addBtn.setAttribute('aria-label', '添加子项');
            addBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                startAddChild(node, li);
            });
            actions.appendChild(addBtn);
        }
        if (node.type === 'item' && node.assessmentRequired) {
            const assessBtn = document.createElement('button');
            assessBtn.className = 'assess-btn';
            assessBtn.textContent = 'AI';
            assessBtn.title = node.completed ? '查看或重新验收' : '提交 AI 验收';
            assessBtn.setAttribute('aria-label', assessBtn.title);
            assessBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                openAssessment(node);
            });
            actions.appendChild(assessBtn);
        }
        if (node.type === 'item') {
            const reviewBtn = document.createElement('button');
            reviewBtn.className = 'review-node-btn';
            reviewBtn.innerHTML = '&#9675;';
            reviewBtn.title = '安排复习';
            reviewBtn.setAttribute('aria-label', '安排复习');
            reviewBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                openScheduleReview(node);
            });
            actions.appendChild(reviewBtn);
        }
        const editBtn = document.createElement('button');
        editBtn.className = 'edit-btn';
        editBtn.innerHTML = '✎';
        editBtn.title = '编辑';
        editBtn.setAttribute('aria-label', '编辑');
        editBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            startEditNode(node, textSpan, row);
        });
        actions.appendChild(editBtn);
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'delete-btn';
        deleteBtn.innerHTML = '✕';
        deleteBtn.title = '删除';
        deleteBtn.setAttribute('aria-label', '删除');
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteNode(node, row);
        });
        actions.appendChild(deleteBtn);
        row.appendChild(arrow);
        row.appendChild(checkbox);
        row.appendChild(textSpan);
        if (optionalBadge) row.appendChild(optionalBadge);
        if (assessmentBadge) row.appendChild(assessmentBadge);
        if (node.type === 'item' && node.review && node.review.due) {
            if (node.review.learning) {
                const learningBadge = document.createElement('span');
                learningBadge.className = 'node-learning-badge';
                learningBadge.textContent = '⚠ 需重学';
                row.appendChild(learningBadge);
            } else {
                const dueBadge = document.createElement('span');
                dueBadge.className = 'node-review-date';
                dueBadge.textContent = '复习 ' + node.review.due.slice(5);
                row.appendChild(dueBadge);
            }
        }
        row.appendChild(dateSpan);
        row.appendChild(actions);
        li.appendChild(row);
        if (node.type !== 'item') {
            const childrenUl = document.createElement('ul');
            childrenUl.className = 'children';
            if (node.expanded || filtering) childrenUl.classList.add('expanded');
            const visibleChildren = filtering
                ? (node.children || []).filter(nodeHasVisibleMatch)
                : (node.children || []);
            if ((node.expanded || filtering) && visibleChildren.length > 0) {
                visibleChildren.forEach(child => {
                    childrenUl.appendChild(renderNode(child, projectCreatedAt, filtering));
                });
            }
            li.appendChild(childrenUl);
            row.addEventListener('click', (e) => {
                if (e.target.closest('.node-actions') || e.target.closest('.checkbox')) return;
                node.expanded = !node.expanded;
                renderDetail();
            });
        } else {
            row.addEventListener('click', (e) => {
                if (e.target.closest('.node-actions') || e.target.closest('.checkbox')) return;
                toggleNodeCompleted(node);
            });
        }
        checkbox.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleNodeCompleted(node);
        });
        checkbox.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                e.stopPropagation();
                toggleNodeCompleted(node);
            }
        });
        textSpan.addEventListener('dblclick', (e) => {
            e.stopPropagation();
            startEditNode(node, textSpan, row);
        });
        return li;
    }

    function toggleNodeCompleted(node) {
        if (node.type === 'item') {
            if (node.assessmentRequired && !node.completed) {
                openAssessment(node);
                return;
            }
            setNodeCompleted(node, !node.completed);
            if (node.assessmentRequired && !node.completed) {
                // Canceling a passed task invalidates both stages; it must be earned again.
                if (node.assessment && node.assessment.passed) {
                    node.assessmentHistory = (Number(node.assessmentHistory) || 0) + 1;
                }
                node.assessment = null;
            }
        } else {
            if (subtreeRequiresAssessment(node)) {
                showToast('课程任务需逐项验收，不能批量完成');
                return;
            }
            toggleAllChildren(node, getNodeCompletionState(node) !== 'completed');
        }
        saveProjects();
        renderDetail();
    }

    function startEditNode(node, textSpan, row) {
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'edit-input';
        input.value = node.text;
        row.replaceChild(input, textSpan);
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
        const save = () => {
            const newText = input.value.trim();
            if (newText) {
                node.text = newText;
                saveProjects();
            }
            renderDetail();
        };
        input.addEventListener('blur', save);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') input.blur();
            if (e.key === 'Escape') {
                input.removeEventListener('blur', save);
                renderDetail();
            }
        });
    }

    function startAddChild(parentNode, parentLi) {
        const childrenUl = parentLi.querySelector('.children');
        if (!childrenUl) return;
        if (!childrenUl.classList.contains('expanded')) {
            parentNode.expanded = true;
            childrenUl.classList.add('expanded');
        }
        const wrapper = document.createElement('div');
        wrapper.style.paddingLeft = parentNode.type === 'week' ? '30px' : '56px';
        wrapper.style.paddingTop = '4px';
        wrapper.style.paddingBottom = '4px';
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'edit-input';
        input.placeholder = parentNode.type === 'week' ? '输入学习单元名称...' : '输入验收任务...';
        input.style.width = 'calc(100% - 10px)';
        input.style.padding = '6px 10px';
        input.style.fontSize = '13px';
        input.style.border = '2px solid var(--primary)';
        input.style.borderRadius = '6px';
        input.style.outline = 'none';
        input.style.boxShadow = '0 0 0 3px var(--primary-soft)';
        wrapper.appendChild(input);
        childrenUl.appendChild(wrapper);
        input.focus();
        const createChild = () => {
            const text = input.value.trim();
            if (text) {
                const childType = parentNode.type === 'week' ? 'day' : 'item';
                const child = {
                    id: generateId(),
                    type: childType,
                    text: text,
                    completed: false,
                    expanded: false,
                    createdAt: todayStr(),
                    children: []
                };
                if (childType === 'item') {
                    child.assessmentRequired = Boolean(getCurrentProject()?.assessmentEnabled);
                    child.assessment = null;
                    child.assessmentHistory = 0;
                }
                if (!parentNode.children) parentNode.children = [];
                parentNode.children.push(child);
                saveProjects();
            }
            renderDetail();
        };
        input.addEventListener('blur', createChild);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') input.blur();
            if (e.key === 'Escape') {
                input.removeEventListener('blur', createChild);
                renderDetail();
            }
        });
    }

    function deleteNode(node, row) {
        const project = getCurrentProject();
        if (!project) return;
        if (node.id === 1600) {
            showToast('补漏队列是固定入口，不能删除；可以继续添加或删除其中的具体任务');
            return;
        }
        const treeBeforeDelete = cloneData(project.tree);
        let finalized = false;
        const finalizeDelete = () => {
            if (finalized) return;
            finalized = true;
            removeNodeById(project.tree, node.id);
            cleanupEmptyNodes(project.tree);
            saveProjects();
            renderDetail();
            showToast(`已删除：${node.text}`, {
                label: '撤销',
                onClick: () => {
                    if (!projects.includes(project)) return;
                    project.tree = treeBeforeDelete;
                    saveProjects();
                    renderDetail();
                }
            });
        };
        row.classList.add('removing');
        row.addEventListener('transitionend', finalizeDelete, { once: true });
        setTimeout(finalizeDelete, 400);
    }

    function clearCompletedInDetail() {
        const project = getCurrentProject();
        if (!project) return;
        const completedIds = collectCompletedItemIds(project.tree);
        if (completedIds.length === 0) return;
        const treeBeforeClear = cloneData(project.tree);
        let delay = 0;
        completedIds.forEach(id => {
            const el = document.querySelector(`#detailView [data-id="${id}"] .node-row`);
            if (el) {
                setTimeout(() => el.classList.add('removing'), delay);
                delay += 40;
            }
        });
        const totalDelay = delay + 350;
        setTimeout(() => {
            completedIds.forEach(id => removeNodeById(project.tree, id));
            cleanupEmptyNodes(project.tree);
            saveProjects();
            renderDetail();
            showToast(`已清空 ${completedIds.length} 项`, {
                label: '撤销',
                onClick: () => {
                    if (!projects.includes(project)) return;
                    project.tree = treeBeforeClear;
                    saveProjects();
                    renderDetail();
                }
            });
        }, totalDelay);
    }

    async function showProjectsView() {
        if (saveTimer) {
            try {
                await flushProjectsSave();
            } catch (error) {
                showToast('当前修改尚未保存，请处理保存错误后再返回');
                return;
            }
        }
        const current = getCurrentProject();
        if (current && Array.isArray(current.tree)) {
            const index = projects.indexOf(current);
            const optional = getProjectOptionalStats(current);
            const total = getProjectTotal(current);
            projects[index] = normalizeProjectSummary({
                ...current,
                _revision: current._revision,
                stats: {
                    total,
                    remaining: getProjectRemaining(current),
                    optionalTotal: optional.total,
                    optionalCompleted: optional.completed
                }
            });
            savedProjectJsonById.delete(String(current.id));
        }
        projectsView.classList.add('active');
        detailView.classList.remove('active');
        reviewView.classList.remove('active');
        currentProjectId = null;
        renderProjects();
        loadReviewCounts();
    }

    function showDetailView(projectId) {
        currentProjectId = projectId;
        projectsView.classList.remove('active');
        reviewView.classList.remove('active');
        detailView.classList.add('active');
        renderDetail();
    }

    async function openProjectDetail(projectId) {
        await ensureProjectLoaded(projectId);
        showDetailView(projectId);
    }

    function startEditProjectNameInDetail() {
        const project = getCurrentProject();
        if (!project) return;
        const input = document.createElement('input');
        input.type = 'text';
        input.value = project.name;
        input.style.width = '100%';
        input.style.padding = '6px 10px';
        input.style.fontSize = '16px';
        input.style.fontWeight = '600';
        input.style.border = '2px solid var(--primary)';
        input.style.borderRadius = '6px';
        input.style.outline = 'none';
        input.style.boxShadow = '0 0 0 3px var(--primary-soft)';
        detailTitle.replaceWith(input);
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
        const save = () => {
            const newName = input.value.trim();
            if (newName) {
                project.name = newName;
                saveProjects();
            }
            renderDetail();
        };
        input.addEventListener('blur', save);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') input.blur();
            if (e.key === 'Escape') {
                input.removeEventListener('blur', save);
                renderDetail();
            }
        });
    }

    function walkItems(nodes, callback) {
        for (const node of nodes || []) {
            if (node.type === 'item') callback(node);
            else walkItems(node.children || [], callback);
        }
    }

    function collectReviewStats(tree) {
        const stats = { last7: 0, streak: 0, due: 0, learning: 0, count: 0 };
        const today = todayStr();
        const days = new Set();
        walkItems(tree, (node) => {
            if (!node.review || !node.completed) return;
            stats.count += 1;
            if (node.review.due && node.review.due <= today) stats.due += 1;
            if (node.review.learning) stats.learning += 1;
            for (const entry of node.review.log || []) {
                if (entry && entry.at && entry.at >= addDaysToIso(today, -6) && entry.at <= today) {
                    stats.last7 += 1;
                    days.add(entry.at);
                }
            }
        });
        const sorted = Array.from(days).sort();
        let cursor = sorted.includes(today) ? today : addDaysToIso(today, -1);
        let run = 0;
        while (sorted.includes(cursor)) {
            run += 1;
            cursor = addDaysToIso(cursor, -1);
        }
        stats.streak = run;
        return stats;
    }

    function walkTreeEntries(nodes, ancestors, labels, callback) {
        for (const node of nodes || []) {
            if (node.type === 'item') {
                callback({
                    node: node,
                    ancestorIds: ancestors.map(entry => entry.id),
                    path: labels.join(' / ')
                });
                continue;
            }
            walkTreeEntries(node.children || [], ancestors.concat(node),
                labels.concat(String(node.text || '')), callback);
        }
    }

    function isValidIsoDate(value) {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value))) return false;
        const parts = String(value).split('-').map(Number);
        const probe = new Date(parts[0], parts[1] - 1, parts[2]);
        return probe.getFullYear() === parts[0] && probe.getMonth() === parts[1] - 1
            && probe.getDate() === parts[2];
    }

    let reviewQueueState = { dueItems: [], futureItems: [] };

    async function showReviewQueue() {
        if (saveTimer) {
            try { await flushProjectsSave(); } catch (error) {
                showToast('当前修改尚未保存，请处理保存错误后再返回');
                return;
            }
        }
        try {
            await Promise.all(projects.map(project => ensureProjectLoaded(project.id)));
        } catch (error) {
            showToast(error.message || '复习队列加载失败');
            return;
        }
        const today = todayStr();
        const dueItems = [];
        const futureItems = [];
        for (const project of projects) {
            if (!Array.isArray(project.tree)) continue;
            walkTreeEntries(project.tree, [], [], (entry) => {
                const node = entry.node;
                if (!node.completed || !node.review || !node.review.due) return;
                const item = {
                    projectId: project.id,
                    projectName: project.name,
                    node: node,
                    ancestorIds: entry.ancestorIds,
                    path: entry.path,
                    due: node.review.due,
                    learning: Boolean(node.review.learning)
                };
                if (item.due <= today) dueItems.push(item);
                else futureItems.push(item);
            });
        }
        dueItems.sort((a, b) => a.due.localeCompare(b.due) || a.projectName.localeCompare(b.projectName));
        futureItems.sort((a, b) => a.due.localeCompare(b.due) || a.projectName.localeCompare(b.projectName));
        reviewQueueState = { dueItems: dueItems, futureItems: futureItems };
        projectsView.classList.remove('active');
        detailView.classList.remove('active');
        reviewView.classList.add('active');
        renderReviewQueue();
        loadReviewCounts();
    }

    function renderReviewQueue() {
        const body = reviewBody;
        body.innerHTML = '';
        const due = reviewQueueState.dueItems || [];
        const future = reviewQueueState.futureItems || [];
        const total = due.length + future.length;
        reviewSubline.textContent = total > 0
            ? '待复习 ' + due.length + ' 项 · 已安排 ' + future.length + ' 项'
            : '暂无到期复习';
        if (total === 0) {
            const empty = document.createElement('p');
            empty.className = 'review-empty';
            empty.textContent = '还没有排入复习的内容。✓ 完成任务后会自动排到明天；也可在项目里点任务旁的 ◷ 手动安排。';
            body.appendChild(empty);
            return;
        }
        if (due.length > 0) {
            body.appendChild(renderReviewGroup('待复习 · 今天到期与逾期', due));
        }
        if (future.length > 0) {
            body.appendChild(renderReviewGroup('已安排 · 未来', future));
        }
    }

    function renderReviewGroup(title, items) {
        const group = document.createElement('div');
        group.className = 'review-group';
        const head = document.createElement('div');
        head.className = 'review-group-title';
        const label = document.createElement('span');
        label.textContent = title;
        const count = document.createElement('span');
        count.className = 'gcount';
        count.textContent = String(items.length);
        head.append(label, count);
        group.appendChild(head);
        const byProject = new Map();
        for (const item of items) {
            if (!byProject.has(item.projectId)) byProject.set(item.projectId, []);
            byProject.get(item.projectId).push(item);
        }
        for (const entry of byProject.entries()) {
            const projectBlock = document.createElement('div');
            projectBlock.className = 'review-project-block';
            const nameRow = document.createElement('div');
            nameRow.className = 'review-project-name';
            nameRow.textContent = entry[1][0].projectName;
            projectBlock.appendChild(nameRow);
            for (const item of entry[1]) {
                projectBlock.appendChild(createReviewItemElement(item));
            }
            group.appendChild(projectBlock);
        }
        return group;
    }

    function createReviewItemElement(item) {
        const row = document.createElement('div');
        row.className = 'review-item';
        const main = document.createElement('div');
        main.className = 'review-item-main';
        const pathSpan = document.createElement('span');
        pathSpan.className = 'review-item-path';
        pathSpan.textContent = item.path || '项目任务';
        const text = document.createElement('div');
        text.className = 'review-item-text';
        text.textContent = item.node.text || '未命名任务';
        text.title = item.node.text || '';
        text.addEventListener('click', () => row.classList.toggle('expanded'));
        main.append(pathSpan, text);
        if (item.learning) {
            const tag = document.createElement('span');
            tag.className = 'review-tag learning';
            tag.textContent = '需重学';
            text.appendChild(tag);
        }
        if (item.due < todayStr()) {
            const days = Math.max(1, daysBetween(item.due, todayStr()));
            const tag = document.createElement('span');
            tag.className = 'review-tag overdue';
            tag.textContent = '逾期 ' + days + ' 天';
            main.appendChild(tag);
        } else {
            const tag = document.createElement('span');
            tag.className = 'review-tag today';
            tag.textContent = '今天';
            main.appendChild(tag);
        }
        const actions = document.createElement('div');
        actions.className = 'review-actions';
        const btnEasy = document.createElement('button');
        btnEasy.type = 'button';
        btnEasy.className = 'review-btn easy';
        btnEasy.textContent = '记住了 +7';
        btnEasy.title = '顺延 7 天';
        btnEasy.addEventListener('click', () => runQueueAction(item, 'easy'));
        const btnHard = document.createElement('button');
        btnHard.type = 'button';
        btnHard.className = 'review-btn hard';
        btnHard.textContent = '模糊 +3';
        btnHard.title = '顺延 3 天';
        btnHard.addEventListener('click', () => runQueueAction(item, 'hard'));
        const btnAgain = document.createElement('button');
        btnAgain.type = 'button';
        btnAgain.className = 'review-btn again';
        btnAgain.textContent = '忘了';
        btnAgain.title = '明天重学（需重学标记）';
        btnAgain.addEventListener('click', () => runQueueAction(item, 'again'));
        const more = document.createElement('select');
        more.className = 'review-btn';
        more.setAttribute('aria-label', '更多复习操作');
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = '⋯ 更多';
        more.appendChild(placeholder);
        const choices = [
            ['d1', '顺延到明天'],
            ['d3', '顺延 3 天'],
            ['d7', '顺延 7 天'],
            ['d30', '顺延 30 天'],
            ['custom', '自定义日期…'],
            ['locate', '在项目中定位'],
            ['clear', '清除复习安排']
        ];
        for (const choice of choices) {
            const option = document.createElement('option');
            option.value = choice[0];
            option.textContent = choice[1];
            more.appendChild(option);
        }
        more.addEventListener('change', () => {
            const value = more.value;
            more.value = '';
            runQueueAction(item, value);
        });
        actions.append(btnEasy, btnHard, btnAgain, more);
        row.append(main, actions);
        return row;
    }

    function daysBetween(fromIso, toIso) {
        const a = fromIso.split('-').map(Number);
        const b = toIso.split('-').map(Number);
        const start = new Date(a[0], a[1] - 1, a[2]);
        const end = new Date(b[0], b[1] - 1, b[2]);
        return Math.round((end - start) / 86400000);
    }

    function runQueueAction(item, action) {
        if (!item || !item.node) return;
        if (action === 'easy' || action === 'hard' || action === 'again') {
            applyReviewResult(item.node, action);
            finishQueueAction();
        } else if (action === 'd1' || action === 'd3' || action === 'd7' || action === 'd30') {
            const days = action === 'd1' ? 1 : action === 'd3' ? 3 : action === 'd7' ? 7 : 30;
            scheduleReview(item.node, addDaysToIso(todayStr(), days));
            finishQueueAction();
        } else if (action === 'clear') {
            if (!window.confirm('清除该任务的复习安排？')) return;
            clearReview(item.node);
            finishQueueAction();
        } else if (action === 'custom') {
            const chosen = window.prompt('自定义复习日期（YYYY-MM-DD）：', addDaysToIso(todayStr(), 7));
            if (chosen === null) return;
            const date = String(chosen).trim();
            if (!isValidIsoDate(date)) { showToast('日期格式不正确（应为 YYYY-MM-DD）'); return; }
            scheduleReview(item.node, date);
            finishQueueAction();
        } else if (action === 'locate') {
            locateStudyTask(item.projectId, {
                id: item.node.id,
                text: item.node.text || '',
                ancestorIds: item.ancestorIds || [],
                path: item.path || '',
                optional: Boolean(item.node.optional)
            });
        }
    }

    async function finishQueueAction() {
        try {
            await saveProjects();
        } catch (error) {
            showToast(error.message || '保存失败');
            return;
        }
        loadReviewCounts();
        showReviewQueue();
    }

    function openScheduleReview(node) {
        if (!node) return;
        if (!node.completed) {
            showToast('请先完成任务，再安排复习');
            return;
        }
        const project = getCurrentProject();
        if (!project) return;
        showUtilityModal('安排复习', '间隔复习');
        utilityBody.innerHTML = '';
        const hint = document.createElement('p');
        hint.className = 'utility-hint';
        hint.textContent = '任务：' + (node.text || '');
        utilityBody.appendChild(hint);
        const list = document.createElement('div');
        list.className = 'utility-task-list';
        const choices = [
            ['明天', addDaysToIso(todayStr(), 1)],
            ['3 天后', addDaysToIso(todayStr(), 3)],
            ['7 天后', addDaysToIso(todayStr(), 7)],
            ['30 天后', addDaysToIso(todayStr(), 30)]
        ];
        for (const choice of choices) {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'utility-task';
            const content = document.createElement('span');
            content.className = 'utility-task-content';
            const name = document.createElement('strong');
            name.textContent = choice[0];
            const path = document.createElement('small');
            path.textContent = '到期：' + choice[1];
            content.append(name, path);
            button.append(content);
            button.addEventListener('click', () => {
                scheduleReview(node, choice[1]);
                finishScheduleModal();
            });
            list.appendChild(button);
        }
        const customButton = document.createElement('button');
        customButton.type = 'button';
        customButton.className = 'utility-task';
        customButton.textContent = '自定义日期…';
        customButton.addEventListener('click', () => {
            const chosen = window.prompt('自定义复习日期（YYYY-MM-DD）：', addDaysToIso(todayStr(), 7));
            if (chosen === null) return;
            const date = String(chosen).trim();
            if (!isValidIsoDate(date)) { showToast('日期格式不正确（应为 YYYY-MM-DD）'); return; }
            scheduleReview(node, date);
            finishScheduleModal();
        });
        list.appendChild(customButton);
        const clearButton = document.createElement('button');
        clearButton.type = 'button';
        clearButton.className = 'utility-task delete-proj-btn';
        clearButton.textContent = '清除复习安排';
        clearButton.addEventListener('click', () => {
            if (!window.confirm('清除该任务的复习安排？')) return;
            clearReview(node);
            finishScheduleModal();
        });
        list.appendChild(clearButton);
        utilityBody.appendChild(list);
    }

    function finishScheduleModal() {
        closeUtilityModal();
        renderDetail();
        saveProjects();
        loadReviewCounts();
    }

    async function loadReviewCounts() {
        try {
            const stored = await readStoredState();
            const totals = (stored && stored.reviewTotals) || { today: 0, overdue: 0 };
            const byProject = new Map();
            const list = (stored && Array.isArray(stored.projects)) ? stored.projects : [];
            for (const summary of list) {
                byProject.set(String(summary.id), {
                    today: Number(summary.reviewToday) || 0,
                    overdue: Number(summary.reviewOverdue) || 0
                });
            }
            reviewCounts = {
                byProject: byProject,
                today: Number(totals.today) || 0,
                overdue: Number(totals.overdue) || 0
            };
        } catch (error) {
            console.warn('刷新复习计数失败', error);
        }
        if (projectsView.classList.contains('active')) renderProjects();
    }

    function initEvents() {
        assessmentForm.addEventListener('submit', submitAssessment);
        assessmentAnswer.addEventListener('keydown', handleAssessmentEditorTab);
        assessmentAnswer.addEventListener('input', saveAssessmentDraft);
        assessmentFiles.addEventListener('change', () => readAssessmentFiles(assessmentFiles.files));
        assessmentQuestionBtn.addEventListener('click', requestAssessmentQuestion);
        assessmentCloseBtn.addEventListener('click', closeAssessment);
        assessmentCancelBtn.addEventListener('click', closeAssessment);
        assessmentModal.querySelector('[data-close-assessment]').addEventListener('click', closeAssessment);
        utilityCloseBtn.addEventListener('click', closeUtilityModal);
        utilityModal.querySelector('[data-close-utility]').addEventListener('click', closeUtilityModal);
        openMemoBtn.addEventListener('click', openMemoTool);
        document.querySelectorAll('[data-study-action]').forEach(button => {
            button.addEventListener('click', () => openStudyTool(button.dataset.studyAction));
        });
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && !assessmentModal.hidden) closeAssessment();
            if (event.key === 'Escape' && !utilityModal.hidden) closeUtilityModal();
        });
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) return;
            persistAssessmentDraft();
            if (saveTimer) flushProjectsSave();
        });
        window.addEventListener('pagehide', () => {
            persistAssessmentDraft();
            if (saveTimer) flushProjectsSave();
        });
        projectSearchInput.addEventListener('input', () => {
            projectFilters.query = projectSearchInput.value;
            renderProjects();
        });
        projectStatusFilter.addEventListener('change', () => {
            projectFilters.status = projectStatusFilter.value;
            renderProjects();
        });
        nodeSearchInput.addEventListener('input', () => {
            nodeFilters.query = nodeSearchInput.value;
            renderDetail();
        });
        nodeStatusFilter.addEventListener('change', () => {
            nodeFilters.status = nodeStatusFilter.value;
            renderDetail();
        });
        exportBtn.addEventListener('click', exportBackup);
        importInput.addEventListener('change', () => {
            importBackup(importInput.files && importInput.files[0]);
        });
        backgroundInput.addEventListener('change', () => {
            handleBackgroundUpload(backgroundInput.files && backgroundInput.files[0]);
        });
        resetBackgroundBtn.addEventListener('click', resetBackground);
        createDatabaseBackupBtn.addEventListener('click', createDatabaseBackupFromUi);
        renameDatabaseBackupBtn.addEventListener('click', renameDatabaseBackupFromUi);
        databaseBackupPickerButton.addEventListener('click', () => {
            databaseBackupMenu.hidden = !databaseBackupMenu.hidden;
            databaseBackupPickerButton.setAttribute('aria-expanded', String(!databaseBackupMenu.hidden));
        });
        document.addEventListener('click', event => {
            if (!backupPicker.contains(event.target)) {
                databaseBackupMenu.hidden = true;
                databaseBackupPickerButton.setAttribute('aria-expanded', 'false');
            }
        });
        restoreDatabaseBackupBtn.addEventListener('click', restoreDatabaseBackupFromUi);
        createProjectBtn.addEventListener('click', () => {
            const name = newProjectInput.value.trim();
            if (!name) return;
            projects.push({
                id: generateId(),
                name: name,
                description: '',
                createdAt: todayStr(),
                assessmentEnabled: Boolean(newProjectAiToggle.checked),
                tree: []
            });
            saveProjects();
            newProjectInput.value = '';
            newProjectAiToggle.checked = false;
            renderProjects();
        });
        newProjectInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') createProjectBtn.click();
        });
        backBtn.addEventListener('click', showProjectsView);
        reviewQueueBtn.addEventListener('click', () => { showReviewQueue(); });
        reviewBackBtn.addEventListener('click', () => { showProjectsView(); });
        if (projectReviewToggle) {
            projectReviewToggle.addEventListener('change', () => {
                const reviewProject = getCurrentProject();
                if (!reviewProject) return;
                reviewProject.reviewEnabled = projectReviewToggle.checked;
                saveProjects();
                renderDetail();
                showToast(reviewProject.reviewEnabled
                    ? '已开启本项目的间隔复习'
                    : '已关闭本项目的间隔复习（仍可手动安排）');
            });
        }
        projectAssessmentToggle.addEventListener('change', () => {
            const project = getCurrentProject();
            if (!project) return;
            setProjectAssessmentEnabled(project, projectAssessmentToggle.checked);
            saveProjects();
            renderDetail();
            showToast(project.assessmentEnabled ? '已开启本项目 AI 验收' : '已关闭本项目 AI 验收');
        });
        detailTitle.addEventListener('click', startEditProjectNameInDetail);
        addWeekBtn.addEventListener('click', () => {
            const project = getCurrentProject();
            if (!project) return;
            const text = newNodeInput.value.trim();
            if (!text) return;
            if (!project.tree) project.tree = [];
            project.tree.push({
                id: generateId(),
                type: 'week',
                text: text,
                completed: false,
                expanded: true,
                createdAt: todayStr(),
                children: []
            });
            ensureRemedialQueueAtBottom([project]);
            saveProjects();
            newNodeInput.value = '';
            renderDetail();
        });
        newNodeInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') addWeekBtn.click();
        });
        clearBtn.addEventListener('click', clearCompletedInDetail);
        clearHistoryBtn.addEventListener('click', clearAssessmentHistoryInDetail);
        expandAllBtn.addEventListener('click', () => {
            const project = getCurrentProject();
            if (!project) return;
            const allExpanded = (project.tree || []).every(w => w.expanded);
            expandAllNodes(project.tree || [], !allExpanded);
            renderDetail();
        });
    }

    async function init() {
        await Promise.all([loadProjects(), loadSavedBackground()]);
        renderProjects();
        loadReviewCounts();
        initEvents();
        startServiceHeartbeat();
        checkStorageHealth();
        loadDatabaseBackups();
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();