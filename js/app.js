(function() {
    'use strict';
    const projectsView = document.getElementById('projectsView');
    const detailView = document.getElementById('detailView');
    const projectGrid = document.getElementById('projectGrid');
    const emptyProjects = document.getElementById('emptyProjects');
    const newProjectInput = document.getElementById('newProjectInput');
    const createProjectBtn = document.getElementById('createProjectBtn');
    const newProjectAiToggle = document.getElementById('newProjectAiToggle');
    const newProjectPlanToggle = document.getElementById('newProjectPlanToggle');
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
// 第七批 Task 11：复习页工具栏（开始今日复习 + 题型/模块/范围筛选）
const startReviewSessionBtn = document.getElementById('startReviewSessionBtn');
const reviewTypeFilter = document.getElementById('reviewTypeFilter');
const reviewModuleFilter = document.getElementById('reviewModuleFilter');
const reviewScopeFilter = document.getElementById('reviewScopeFilter');
const projectReviewToggle = document.getElementById('projectReviewToggle');
// 第七批：复习会话视图（一次一题、先回忆后揭示、五档自评）
const reviewSessionView = document.getElementById('reviewSessionView');
const reviewSessionProgress = document.getElementById('reviewSessionProgress');
const reviewSessionExitBtn = document.getElementById('reviewSessionExitBtn');
const reviewQuestionCard = document.getElementById('reviewQuestionCard');
const reviewQuestionMeta = document.getElementById('reviewQuestionMeta');
const reviewQuestionPrompt = document.getElementById('reviewQuestionPrompt');
const reviewAnswerInput = document.getElementById('reviewAnswerInput');
const reviewRevealBtn = document.getElementById('reviewRevealBtn');
const reviewAnswerPanel = document.getElementById('reviewAnswerPanel');
const reviewGradeButtons = document.getElementById('reviewGradeButtons');
const reviewSessionSummary = document.getElementById('reviewSessionSummary');
// 第七批 Task 12：知识点库（按模块/层级筛选 + 立即练一次）
const knowledgeView = document.getElementById('knowledgeView');
const knowledgeList = document.getElementById('knowledgeList');
const knowledgeSearch = document.getElementById('knowledgeSearch');
const knowledgeModuleFilter = document.getElementById('knowledgeModuleFilter');
const knowledgeLevelFilter = document.getElementById('knowledgeLevelFilter');
const knowledgeBackBtn = document.getElementById('knowledgeBackBtn');
const openKnowledgeBtn = document.getElementById('openKnowledgeBtn');
// 复习页的模块下拉和知识点库共用这一份 /api/review/points 结果（见 showKnowledgeLibrary）。
let knowledgePoints = [];
    const exportBtn = document.getElementById('exportBtn');
    const viewBar = document.getElementById('viewBar');
    const viewChips = document.getElementById('viewChips');
    const saveViewBtn = document.getElementById('saveViewBtn');
    const nodePriorityFilter = document.getElementById('nodePriorityFilter');
    const nodeDueFilter = document.getElementById('nodeDueFilter');
    const nodeTagFilter = document.getElementById('nodeTagFilter');
    const batchToggleBtn = document.getElementById('batchToggleBtn');
    const projectArchiveBtn = document.getElementById('projectArchiveBtn');
    // 第五批：撤销重做 / 复制 / 模板 / 设置 / 活动历史 / 多格式导出
    const undoBtn = document.getElementById('undoBtn');
    const redoBtn = document.getElementById('redoBtn');
    const duplicateProjectBtn = document.getElementById('duplicateProjectBtn');
    const saveTemplateBtn = document.getElementById('saveTemplateBtn');
    const templateSelect = document.getElementById('templateSelect');
    const createFromTemplateBtn = document.getElementById('createFromTemplateBtn');
    const exportMarkdownBtn = document.getElementById('exportMarkdownBtn');
    const exportCsvBtn = document.getElementById('exportCsvBtn');
    const runAutoArchiveBtn = document.getElementById('runAutoArchiveBtn');
    const trashRetentionInput = document.getElementById('trashRetentionInput');
    const reviewDailyLimitInput = document.getElementById('reviewDailyLimitInput');
    const reviewNewPerDayInput = document.getElementById('reviewNewPerDayInput');
    const autoArchiveDaysInput = document.getElementById('autoArchiveDaysInput');
    const autoArchiveToggle = document.getElementById('autoArchiveToggle');
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');
    const settingsStatus = document.getElementById('settingsStatus');
    const templateList = document.getElementById('templateList');
    const activityList = document.getElementById('activityList');
    const refreshActivityBtn = document.getElementById('refreshActivityBtn');
    const clearActivityBtn = document.getElementById('clearActivityBtn');
    const batchToolbar = document.getElementById('batchToolbar');
    const workbenchView = document.getElementById('workbenchView');
    const workbenchBody = document.getElementById('workbenchBody');
    const workbenchSubline = document.getElementById('workbenchSubline');
    const workbenchBackBtn = document.getElementById('workbenchBackBtn');
    const workbenchRefreshBtn = document.getElementById('workbenchRefreshBtn');
    const openWorkbenchBtn = document.getElementById('openWorkbenchBtn');
    const openRecentBtn = document.getElementById('openRecentBtn');
    const quickAddInput = document.getElementById('quickAddInput');
    const quickAddBtn = document.getElementById('quickAddBtn');
    const reminderToggleBtn = document.getElementById('reminderToggleBtn');
    const reminderPermissionBtn = document.getElementById('reminderPermissionBtn');
    const reminderStatus = document.getElementById('reminderStatus');

    // 所有视图切换都走这里：避免新增视图后忘记在别处移除 active
    function activateView(activeView) {
        [projectsView, detailView, reviewView, reviewSessionView, knowledgeView, workbenchView].forEach(view => {
            if (view) view.classList.toggle('active', view === activeView);
        });
    }
    const importInput = document.getElementById('importInput');
    const backgroundInput = document.getElementById('backgroundInput');
    const resetBackgroundBtn = document.getElementById('resetBackgroundBtn');
    const databaseBackupSelect = document.getElementById('databaseBackupSelect');
    const backupPicker = document.getElementById('backupPicker');
    const databaseBackupPickerButton = document.getElementById('databaseBackupPickerButton');
    const databaseBackupMenu = document.getElementById('databaseBackupMenu');
    const renameDatabaseBackupBtn = document.getElementById('renameDatabaseBackupBtn');
    const downloadDatabaseBackupBtn = document.getElementById('downloadDatabaseBackupBtn');
    const inspectDatabaseBackupBtn = document.getElementById('inspectDatabaseBackupBtn');
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
    const assessmentLive = document.getElementById('assessmentLive');
    const assessmentLiveBody = document.getElementById('assessmentLiveBody');
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
    const globalSearchBtn = document.getElementById('globalSearchBtn');
    const openTrashBtn = document.getElementById('openTrashBtn');
    const copyQuestionBtn = document.getElementById('copyQuestionBtn');
    const extraQuestionBtn = document.getElementById('extraQuestionBtn');
    const extraAsk = document.getElementById('extraAsk');
    const extraCount = document.getElementById('extraCount');
    const extraConfirmBtn = document.getElementById('extraConfirmBtn');
    const extraCancelBtn = document.getElementById('extraCancelBtn');
    const summaryQuestionBtn = document.getElementById('summaryQuestionBtn');
    const openSummaryBtn = document.getElementById('openSummaryBtn');
    const assessmentFileHint = document.getElementById('assessmentFileHint');
    const assessmentTemplateConclusionBtn = document.getElementById('assessmentTemplateConclusionBtn');
    const assessmentTemplateExplainBtn = document.getElementById('assessmentTemplateExplainBtn');
    const assessmentTemplateCodeBtn = document.getElementById('assessmentTemplateCodeBtn');
    const assessmentTemplateCustomBar = document.getElementById('assessmentTemplateCustomBar');
    const manageTemplatesBtn = document.getElementById('manageTemplatesBtn');
    const assessmentRestoreBtn = document.getElementById('assessmentRestoreBtn');
    const studyTools = window.TodoStudyTools;
    const DATA_SCHEMA_VERSION = 2;
    // 收集箱是系统保留项目（服务端 INBOX_PROJECT_ID），不能归档：归档后工作台里
    // 看不到它，可快速添加仍然往里写，等于把任务丢进看不见的地方。
    const INBOX_PROJECT_ID = 'inbox';
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
    // 在飞的节点级 patch 数量：与全量保存共用 saveQueue，串行执行
    let inFlightPatches = 0;
    let saveConflict = false;
    let inFlightSaves = 0;
    let leaveGuardArmed = false;
    let timezoneWarned = false;
    let stateLoadError = '';
    let backupListError = '';
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
    let assessmentFileSummary = '';
    let trashItems = [];
    let dirtyProjectIds = new Set();
    let projectStatsCache = new Map();
    let nodeStatsCache = new Map();
    let memoState = { memos: [], selectedId: null, query: '', saveTimer: null, pendingMemoId: null,
        saveQueue: Promise.resolve() };
    const projectFilters = { query: '', status: 'all' };
    const nodeFilters = { query: '', status: 'all', priority: 'all', due: 'all', tag: '' };
    const batchState = { active: false, selected: new Set() };
    let savedViews = [];
    let savedViewsError = '';

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

    const SEARCH_DEBOUNCE_MS = 180;

    function debounce(fn, wait) {
        let timer = null;
        return function debounced(...args) {
            if (timer) clearTimeout(timer);
            timer = setTimeout(() => {
                timer = null;
                fn.apply(this, args);
            }, wait);
        };
    }

    // 弹窗里的纯文字状态（加载中 / 失败）统一走这里，避免把错误信息拼进 innerHTML。
    function renderUtilityMessage(text) {
        utilityBody.replaceChildren();
        const message = document.createElement('p');
        message.className = 'utility-empty';
        message.textContent = text;
        utilityBody.appendChild(message);
    }

    function setNodeCompleted(node, completed) {
        // 记住原状态：只有"未完成 → 完成"这一次才生成下一次周期任务。
        // 否则对已完成的周期任务反复点（分组复选框会把整棵子树再标一遍）会指数级复制。
        const wasCompleted = Boolean(node.completed);
        node.completed = Boolean(completed);
        node.completedAt = node.completed ? new Date().toISOString() : null;
        if (!node || node.type !== 'item') return { spawned: null, project: null };
        const project = owningProjectOfNode(node);
        let spawned = null;
        if (node.completed && !wasCompleted && node.repeat) {
            spawned = project ? spawnNextOccurrence(project, node) : null;
            if (spawned) showToast(`周期任务：已生成下一次（${spawned.dueDate}）`);
        }
        if (node.completed) {
            if (project && projectAutoReview(project) && !node.optional && !node.review) {
                node.review = { due: addDaysToIso(todayStr(), 1), learning: false,
                    log: (node.review && Array.isArray(node.review.log)) ? node.review.log : [] };
            }
        } else if (node.review) {
            delete node.review;
        }
        markProjectDirty(project);
        return { spawned, project };
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

    function normalizeAssessmentFiles(value) {
        if (!Array.isArray(value)) return [];
        const files = [];
        for (const item of value.slice(0, 10)) {
            if (!item || typeof item !== 'object') continue;
            const name = String(item.name || '未命名文件').slice(0, 200);
            const content = String(item.content || '').slice(0, 120000);
            if (name && content) files.push({ name: name, content: content });
        }
        return files;
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
        markProjectDirty(owningProjectOfNode(node));
    }

    function scheduleReview(node, dueIso) {
        if (!node || node.type !== 'item') return;
        if (!String(dueIso || '').trim()) return;
        node.review = {
            due: String(dueIso).slice(0, 10),
            learning: false,
            log: (node.review && Array.isArray(node.review.log)) ? node.review.log.slice(-50) : []
        };
        markProjectDirty(owningProjectOfNode(node));
    }

    function clearReview(node) {
        if (!node) return;
        delete node.review;
        markProjectDirty(owningProjectOfNode(node));
    }

    function getCurrentProject() {
        return projects.find(p => p.id === currentProjectId) || null;
    }

    function markProjectDirty(project) {
        if (!project || project.id == null) return;
        const key = String(project.id);
        dirtyProjectIds.add(key);
        projectStatsCache.delete(key);
        nodeStatsCache.delete(key);
    }

    function refreshProjectCaches(project) {
        if (!project || !Array.isArray(project.tree)) return null;
        const key = String(project.id);
        const nodeMap = new Map();
        const projectStats = { total: 0, remaining: 0, optionalTotal: 0, optionalCompleted: 0 };
        function walk(nodes) {
            let total = 0;
            let remaining = 0;
            for (const node of nodes || []) {
                let stats;
                if (node.type === 'item') {
                    const mainItem = !node.optional;
                    if (mainItem) {
                        projectStats.total += 1;
                        if (!node.completed) projectStats.remaining += 1;
                    } else {
                        projectStats.optionalTotal += 1;
                        if (node.completed) projectStats.optionalCompleted += 1;
                    }
                    stats = {
                        total: mainItem ? 1 : 0,
                        remaining: mainItem && !node.completed ? 1 : 0
                    };
                } else {
                    stats = walk(node.children || []);
                }
                nodeMap.set(String(node.id), stats);
                total += stats.total;
                remaining += stats.remaining;
            }
            return { total, remaining };
        }
        walk(project.tree || []);
        projectStatsCache.set(key, projectStats);
        nodeStatsCache.set(key, nodeMap);
        return projectStats;
    }

    function ensureProjectCaches(project) {
        if (!project || !Array.isArray(project.tree)) return null;
        const key = String(project.id);
        const cached = projectStatsCache.get(key);
        if (cached && nodeStatsCache.has(key)) return cached;
        return refreshProjectCaches(project);
    }

    function getCachedNodeStats(project, node) {
        if (!project || !node) return { total: 0, remaining: 0 };
        const key = String(project.id);
        const nodeMap = nodeStatsCache.get(key);
        if (!nodeMap) {
            ensureProjectCaches(project);
            return nodeStatsCache.get(key)?.get(String(node.id)) || { total: 0, remaining: 0 };
        }
        return nodeMap.get(String(node.id)) || { total: 0, remaining: 0 };
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

    function applyAssessmentRequirements(project, enabled) {
        // 只同步"是否要求 AI 验收"这一标记，绝不改动完成态。
        // 加载项目（normalizeProjects）时必须用这个版本：setProjectAssessmentEnabled 会把
        // 没有 assessment.passed 的已完成任务重置为未完成，而加载时静默改数据会随后被保存回库。
        const required = Boolean(enabled);
        function walk(nodes) {
            for (const node of nodes || []) {
                if (node.type === 'item') {
                    node.assessmentRequired = required;
                } else {
                    walk(node.children);
                }
            }
        }
        walk(project.tree);
    }

    function setProjectAssessmentEnabled(project, enabled) {
        // 仅供用户手动切换项目级"AI 验收"开关时调用（会重置未验收的完成态）。
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
        markProjectDirty(project);
    }

    // 内置"补漏队列"单元的 id（内存里可能是数字 1600，也可能从服务端读回字符串 '1600'）
    const REMEDIAL_QUEUE_ID = '1600';

    function ensureRemedialQueueAtBottom(projectList) {
        if (!Array.isArray(projectList) || projectList.length === 0) return;
        const firstProject = projectList[0];
        let queue = null;
        function takeQueue(nodes) {
            for (let index = nodes.length - 1; index >= 0; index--) {
                const node = nodes[index];
                // 服务端存的是 JSON 字符串 id（'1600'），内置模板里是数字 1600：
                // 只用 === 比数字会漏掉服务端那份，于是又克隆一份 → 保存时报"节点 ID 重复"。
                if (String(node.id) === REMEDIAL_QUEUE_ID) {
                    if (!queue) queue = node;
                    nodes.splice(index, 1);
                    continue;
                }
                if (node.children && node.children.length > 0) takeQueue(node.children);
            }
        }
        takeQueue(firstProject.tree || []);
        if (!queue) {
            queue = createDefaultTree()[0].children.find(node => String(node.id) === REMEDIAL_QUEUE_ID);
            queue = queue ? cloneData(queue) : null;
        }
        if (queue) {
            queue.expanded = false;
            firstProject.tree.push(queue);
        }
    }

    function cloneData(value) {
        return JSON.parse(JSON.stringify(value));
    }

    function readStoredState() {
        // 带上浏览器本地日期：服务端用 WSL/宿主时区算复习计数会差一天（见 R3 ⑦）。
        return apiFetch(`/api/projects?today=${encodeURIComponent(todayStr())}`, { cache: 'no-store' })
            .then(response => {
                if (!response.ok) throw new Error('SQLite 服务不可用');
                return response.json();
            })
            .then(payload => payload || null);
    }

    function serializeProject(project) {
        // 顶层浅拷贝即可：JSON.stringify 只读取不修改。
        // 以前这里 cloneData(project) 会把整棵树 JSON 往返一次（10k 任务 ≈ 100ms/次），
        // 而调用方只拿去 stringify，深拷贝纯属浪费（第六批 item 1）。
        const stored = { ...project };
        delete stored._revision;
        delete stored.stats;
        return stored;
    }

    // ---------- 项目"内存 vs 服务端"判据（第六批 item 1/2）----------
    // 视图态字段只影响本机显示，不该让节点级 patch 退化成整棵树重写；
    // 其中 expanded 目前本来也不会触发保存（只在本机内存里变），
    // 所以把它排除在判据外不会改变"什么时候写库"的行为。
    const PROJECT_STATE_SKIP_KEYS = new Set(['expanded', '_revision', 'stats']);

    // "数据内容"指纹：跳过视图态字段（expanded 等），用来判断内存与服务端是否一致。
    // 直接用原生 JSON.stringify + replacer（10k 任务约 27ms），
    // 手写递归拼接虽然省了克隆但要 90ms+，不划算。
    function skipViewState(key, item) {
        return PROJECT_STATE_SKIP_KEYS.has(key) ? undefined : item;
    }

    function projectStateJson(project) {
        return JSON.stringify(project, skipViewState);
    }

    function rememberProjectBaseline(project) {
        if (!project) return;
        const key = String(project.id);
        savedProjectJsonById.set(key, projectStateJson(serializeProject(project)));
    }

    function forgetProjectBaseline(projectId) {
        savedProjectJsonById.delete(String(projectId));
    }

    function writeStoredProject(project, expectedRevision) {
        const body = JSON.stringify({
            project: serializeProject(project),
            expectedRevision
        });
        return apiFetch('/api/project', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body,
            // 关页/切后台时 keepalive 能让请求继续发完（浏览器上限约 64 KB，大项目退回普通请求）。
            keepalive: body.length <= 60000
        }).then(response => {
            return response.json().catch(() => ({})).then(payload => {
                if (!response.ok) {
                    const error = new Error(payload.error || 'SQLite 写入失败，请重试');
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
                if (!response.ok || !payload.project) throw new Error(payload.error || '读取项目失败，请重试');
                return payload;
            });
    }

    function deleteStoredProject(projectId, revision) {
        return apiFetch(`/api/project?id=${encodeURIComponent(projectId)}&revision=${encodeURIComponent(revision)}`, {
            method: 'DELETE'
        }).then(async response => {
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                const error = new Error(payload.error || '删除项目失败，请重试');
                error.status = response.status;
                throw error;
            }
            return payload;
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
            throw new Error(payload.error || '保存背景图片失败，请重试');
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
        assessment.uploadedFiles = normalizeAssessmentFiles(assessment.uploadedFiles);
        assessment.lastSubmittedAt = typeof assessment.lastSubmittedAt === 'string'
            ? assessment.lastSubmittedAt : '';
        return assessment;
    }

    const NODE_PRIORITIES = ['high', 'mid', 'low'];
    const MAX_TAGS = 20;
    const MAX_TAG_CHARS = 40;
    const MAX_NOTE_CHARS = 20000;
    const MAX_LINKS = 20;
    const MAX_LINK_CHARS = 2000;
    const MAX_ESTIMATE_MINUTES = 60 * 24 * 30;

    // 纯函数：任务元数据归一化（与服务端 storage.clean_* 规则保持一致）
    function normalizeNodeMeta(node) {
        const priority = NODE_PRIORITIES.includes(node.priority) ? node.priority : '';
        const dueRaw = String(node.dueDate || '').slice(0, 10);
        const dueDate = /^\d{4}-\d{2}-\d{2}$/.test(dueRaw) && isValidIsoDate(dueRaw) ? dueRaw : '';
        const estimateMinutes = Math.max(0, Math.min(MAX_ESTIMATE_MINUTES, Number(node.estimateMinutes) || 0));
        const tags = [];
        for (const raw of Array.isArray(node.tags) ? node.tags : []) {
            const tag = String(raw || '').trim().slice(0, MAX_TAG_CHARS);
            if (tag && !tags.includes(tag)) tags.push(tag);
            if (tags.length >= MAX_TAGS) break;
        }
        const links = [];
        for (const raw of Array.isArray(node.links) ? node.links : []) {
            if (!raw || typeof raw !== 'object') continue;
            const url = String(raw.url || '').trim().slice(0, MAX_LINK_CHARS);
            if (!/^https?:\/\//.test(url)) continue;
            links.push({ label: String(raw.label || '').trim().slice(0, 80) || url.slice(0, 80), url });
            if (links.length >= MAX_LINKS) break;
        }
        const note = String(node.note || '').slice(0, MAX_NOTE_CHARS);
        const repeat = cleanRepeat(node.repeat);
        return { priority, dueDate, estimateMinutes, tags, links, note, repeat };
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
            children,
            ...(type === 'item' ? normalizeNodeMeta(node) : {})
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
                // 保留归档标记：丢掉它以后任何一次保存都会把服务端的 archived=1 写成 0。
                archived: Boolean(project.archived),
                tree
            };
            // 加载时只同步"是否需要验收"标记；重置完成态只发生在用户手动切换开关时。
            applyAssessmentRequirements(normalized, normalized.assessmentEnabled);
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
            // archived / reviewEnabled 必须原样带过来：后端 project_summary() 会返回它们，
            // 丢掉的话刷新后"已归档"筛选恒为空、归档按钮永远显示"归档"。
            archived: Boolean(project.archived),
            reviewEnabled: typeof project.reviewEnabled === 'boolean' ? project.reviewEnabled : undefined,
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

    // 纯函数：找出导入 JSON 里的重复 ID。节点 ID 按项目作用域校验（与服务端一致）。
    function findImportDuplicateIds(projects) {
        const problems = [];
        const projectIds = new Map();
        (projects || []).forEach((project, index) => {
            if (!project || typeof project !== 'object') return;
            const name = String(project.name || `第 ${index + 1} 个项目`);
            const projectId = project.id;
            if (projectId !== undefined && projectId !== null && String(projectId).trim() !== '') {
                const key = String(projectId);
                if (projectIds.has(key)) problems.push(`重复项目 ID：${key}（“${projectIds.get(key)}”与“${name}”）`);
                else projectIds.set(key, name);
            }
            const seenNodes = new Set();
            const walk = (nodes, path) => {
                for (const node of nodes || []) {
                    if (!node || typeof node !== 'object') continue;
                    const label = String(node.text || node.type || '未命名节点');
                    const nodePath = path ? `${path} / ${label}` : label;
                    const nodeId = node.id;
                    if (nodeId !== undefined && nodeId !== null && String(nodeId).trim() !== '') {
                        const key = String(nodeId);
                        if (seenNodes.has(key)) problems.push(`重复节点 ID：${nodePath}（${key}）`);
                        else seenNodes.add(key);
                    }
                    walk(node.children, nodePath);
                }
            };
            walk(project.tree, name);
        });
        return problems;
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
            // 记住失败原因：renderProjects() 用它显示"读取失败 + 重试"，而不是伪装成"还没有项目"。
            stateLoadError = (error && error.message) || '无法连接本地服务';
            showToast('无法连接本地服务，请先运行 open-ai-list.sh');
            return;
        }
        stateLoadError = '';
        const storedProjects = storedPayload && Array.isArray(storedPayload.projects)
            ? storedPayload.projects : [];
        projects = storedProjects.map(normalizeProjectSummary);
        if (projects.length === 0) {
            projects = createDefaultProjects();
            projects.forEach(markProjectDirty);
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
        refreshProjectCaches(project);
        projects[index] = project;
        rememberProjectBaseline(project);
        return project;
    }

    function flushProjectsSave() {
        if (saveTimer) {
            clearTimeout(saveTimer);
            saveTimer = null;
        }
        const waiters = saveWaiters.splice(0);
        const operation = saveQueue.catch(() => undefined).then(async () => {
            if (saveConflict) {
                // 打标记：调用方（含 beforeunload 守卫与提示文案）要能区分"版本冲突"和"服务不可用"。
                const conflictError = new Error('存在未解决的版本冲突，请先解决冲突再保存');
                conflictError.conflict = true;
                // 冲突期间还有本地改动没落库，离开守卫必须挂着（savePending() 也认这两个条件）。
                if (dirtyProjectIds.size > 0) armLeaveGuard();
                throw conflictError;
            }
            // 不再把整棵项目树 cloneData 一份快照：判据用规范化指纹（只读、同步），
            // 写库时现场构造请求体，省掉每个项目一次 4 MB 级别的 JSON 往返（第六批 item 1）。
            const candidates = projects.filter(project => Array.isArray(project.tree));
            const currentProjectJsonById = new Map(
                candidates.map(project => [String(project.id), projectStateJson(serializeProject(project))])
            );
            // 只要“被标记为脏”或“与上次保存的指纹不一致”就写入；
            // 即便个别改动路径漏标 dirty，也仍会被差集兜住，不会丢保存。
            const changedProjects = candidates.filter(project =>
                dirtyProjectIds.has(String(project.id))
                || savedProjectJsonById.get(String(project.id)) !== currentProjectJsonById.get(String(project.id))
            );
            if (changedProjects.length === 0) return;
            inFlightSaves += 1;
            armLeaveGuard();
            setSaveStatus('保存中…', 'saving');
            try {
                for (const project of changedProjects) {
                    const current = project;
                    const projectId = String(project.id);
                    // 用内存里最新的版本号做乐观锁（原实现是快照克隆的版本，现在直接用同一对象）
                    const expectedRevision = current ? current._revision : undefined;
                    let payload;
                    try {
                        payload = await writeStoredProject(project, expectedRevision);
                    } catch (writeError) {
                        if (!(writeError && writeError.status === 409)) throw writeError;
                        // ① 冲突：绝不自动用本地内容覆盖服务端，停下来让用户决定。
                        await beginProjectConflict(project, current);
                        continue;
                    }
                    savedProjectJsonById.set(projectId, currentProjectJsonById.get(projectId));
                    dirtyProjectIds.delete(projectId);
                    if (current) {
                        current._revision = Number(payload.revision) || expectedRevision + 1;
                        if (payload.summary) current.stats = payload.summary.stats;
                    }
                }
            } finally {
                inFlightSaves -= 1;
                if (!savePending()) disarmLeaveGuard();
            }
            if (!saveConflict) setSaveStatus('已保存');
        });
        saveQueue = operation.catch(() => undefined);
        operation.catch(error => {
            console.error('保存项目失败', error);
            if (error && error.conflict) {
                // 冲突已经由 beginProjectConflict 提示过，这里只维持状态，不再每次防抖刷屏。
                saveConflict = true;
                setSaveStatus('版本冲突', 'error');
            } else if (error.status === 409) {
                saveConflict = true;
                setSaveStatus('版本冲突', 'error');
                showToast('检测到其他页面已修改数据，请先解决冲突');
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

    // ---------- ① 版本冲突：停写 + 差异 + 三选（保留本地 / 保留远端 / 手动合并） ----------

    let pendingConflict = null;

    function walkTreeEntriesForDiff(nodes, path, out) {
        for (const node of nodes || []) {
            if (!node || typeof node !== 'object') continue;
            const label = String(node.text || node.type || '未命名');
            const nodePath = path ? `${path} / ${label}` : label;
            out.set(String(node.id), { node, path: nodePath });
            walkTreeEntriesForDiff(node.children, nodePath, out);
        }
    }

    function nodeFieldDifferences(localNode, remoteNode) {
        const fields = [];
        const compare = (field, localValue, remoteValue) => {
            if (localValue !== remoteValue) fields.push({ field, local: localValue, remote: remoteValue });
        };
        const assessment = node => node.assessment || {};
        const review = node => node.review || {};
        compare('文字', String(localNode.text || ''), String(remoteNode.text || ''));
        compare('完成', Boolean(localNode.completed), Boolean(remoteNode.completed));
        compare('完成时间', localNode.completedAt || '', remoteNode.completedAt || '');
        compare('选做', Boolean(localNode.optional), Boolean(remoteNode.optional));
        compare('需要验收', Boolean(localNode.assessmentRequired), Boolean(remoteNode.assessmentRequired));
        compare('验收通过', Boolean(assessment(localNode).passed), Boolean(assessment(remoteNode).passed));
        compare('验收分数', Number(assessment(localNode).score) || 0, Number(assessment(remoteNode).score) || 0);
        compare('复习日期', String(review(localNode).due || ''), String(review(remoteNode).due || ''));
        compare('展开', Boolean(localNode.expanded), Boolean(remoteNode.expanded));
        return fields;
    }

    // 纯函数：本地 vs 服务端的结构化差异（面板与测试都用它）
    function diffProject(local, remote) {
        const localMap = new Map();
        const remoteMap = new Map();
        walkTreeEntriesForDiff(local && local.tree, '', localMap);
        walkTreeEntriesForDiff(remote && remote.tree, '', remoteMap);
        const projectFields = [];
        if (String(local.name || '') !== String(remote.name || '')) {
            projectFields.push({ field: '项目名', local: local.name, remote: remote.name });
        }
        if (String(local.description || '') !== String(remote.description || '')) {
            projectFields.push({ field: '描述', local: local.description, remote: remote.description });
        }
        const changed = [];
        const onlyLocal = [];
        const onlyRemote = [];
        for (const [id, entry] of localMap) {
            const other = remoteMap.get(id);
            if (!other) {
                onlyLocal.push({ id, path: entry.path });
                continue;
            }
            const fields = nodeFieldDifferences(entry.node, other.node);
            if (fields.length > 0) changed.push({ id, path: entry.path, fields });
        }
        for (const [id, entry] of remoteMap) {
            if (!localMap.has(id)) onlyRemote.push({ id, path: entry.path });
        }
        return { projectFields, changed, onlyLocal, onlyRemote };
    }

    // 纯函数：按用户选择合并。choices = { project: 'local'|'remote', nodes: {id: 'local'|'remote'},
    //                                      keepLocalOnly:Set, keepRemoteOnly:Set }
    function mergeProjects(local, remote, choices) {
        const options = choices || {};
        const projectChoice = options.project === 'remote' ? 'remote' : 'local';
        const nodeChoices = options.nodes || {};
        const keepLocalOnly = options.keepLocalOnly || new Set();
        const keepRemoteOnly = options.keepRemoteOnly || new Set();
        const base = projectChoice === 'remote' ? remote : local;
        const other = projectChoice === 'remote' ? local : remote;
        const baseIsLocal = projectChoice === 'local';
        const localMap = new Map();
        const remoteMap = new Map();
        walkTreeEntriesForDiff(local && local.tree, '', localMap);
        walkTreeEntriesForDiff(remote && remote.tree, '', remoteMap);
        const keyOf = id => String(id);
        // 逐层做"并集"：两边都有的节点按选择取内容并继续递归；只有一边有的按保留开关决定。
        const build = (baseNodes, otherNodes) => {
            const result = [];
            const seen = new Set();
            for (const node of baseNodes || []) {
                const id = keyOf(node.id);
                seen.add(id);
                const counterpart = (baseIsLocal ? remoteMap : localMap).get(id);
                if (counterpart) {
                    const choice = nodeChoices[id];
                    const source = choice === 'remote' ? remoteMap.get(id).node
                        : choice === 'local' ? localMap.get(id).node
                            : node;
                    const copy = cloneData(source);
                    copy.children = build(node.children, counterpart.node.children);
                    result.push(copy);
                    continue;
                }
                const keep = baseIsLocal ? keepLocalOnly.has(id) : keepRemoteOnly.has(id);
                if (keep) result.push(cloneData(node));
            }
            for (const node of otherNodes || []) {
                const id = keyOf(node.id);
                if (seen.has(id)) continue;
                seen.add(id);
                const keep = baseIsLocal ? keepRemoteOnly.has(id) : keepLocalOnly.has(id);
                if (keep) result.push(cloneData(node));
            }
            return result;
        };
        return {
            id: base.id,
            name: projectChoice === 'remote' ? remote.name : local.name,
            description: projectChoice === 'remote' ? remote.description : local.description,
            createdAt: base.createdAt,
            assessmentEnabled: Boolean(base.assessmentEnabled),
            reviewEnabled: base.reviewEnabled,
            // 合并结果必须带上归档标记，否则解决冲突后已归档项目会被写成未归档。
            archived: Boolean(projectChoice === 'remote' ? remote.archived : local.archived),
            tree: build(base.tree, other.tree),
        };
    }

    async function beginProjectConflict(localProject, localRef) {
        saveConflict = true;
        setSaveStatus('版本冲突', 'error');
        let remotePayload = null;
        try {
            remotePayload = await readStoredProject(String(localProject.id));
        } catch (error) {
            showToast(`检测到其他页面已修改该项目，读取服务端版本失败：${error.message || ''}`);
            return;
        }
        const remote = normalizeProjects([remotePayload.project])[0];
        if (!remote) {
            showToast('服务端版本无法解析，已停止写入，请刷新页面');
            return;
        }
        remote._revision = Math.max(0, Number(remotePayload.revision) || 0);
        remote.stats = localRef ? localRef.stats : remote.stats;
        pendingConflict = { local: localProject, remote };
        showToast('两个页面改了同一项目，已停止写入', { label: '解决冲突', onClick: () => openConflictPanel() });
    }

    function openConflictPanel() {
        if (!pendingConflict) return;
        const { local, remote } = pendingConflict;
        const diff = diffProject(local, remote);
        showUtilityModal('版本冲突', '选择保留哪一份');
        utilityBody.innerHTML = '';
        const hint = document.createElement('p');
        hint.className = 'utility-hint';
        hint.textContent = `本地版本 ${Number(local._revision) || 0} · 服务端版本 ${Number(remote._revision) || 0}`
            + `；差异：${diff.changed.length} 个任务被改、仅本地 ${diff.onlyLocal.length} 个、仅服务端 ${diff.onlyRemote.length} 个、项目字段 ${diff.projectFields.length} 处`;
        utilityBody.appendChild(hint);
        const list = document.createElement('div');
        list.className = 'conflict-list';
        const addRow = text => {
            const row = document.createElement('div');
            row.className = 'conflict-row';
            row.textContent = text;
            list.appendChild(row);
        };
        diff.projectFields.forEach(item => addRow(`${item.field}：本地「${item.local || '空'}」/ 服务端「${item.remote || '空'}」`));
        diff.changed.forEach(item => addRow(`改动 · ${item.path}（${item.fields.map(f => f.field).join('、')}）`));
        diff.onlyLocal.forEach(item => addRow(`仅本地有 · ${item.path}`));
        diff.onlyRemote.forEach(item => addRow(`仅服务端有 · ${item.path}`));
        if (diff.projectFields.length + diff.changed.length + diff.onlyLocal.length + diff.onlyRemote.length === 0) {
            addRow('没有可显示的差异（可能只是版本号不同）。');
        }
        utilityBody.appendChild(list);
        const actions = document.createElement('div');
        actions.className = 'utility-actions';
        const keepLocal = document.createElement('button');
        keepLocal.type = 'button';
        keepLocal.className = 'utility-primary-btn';
        keepLocal.textContent = '保留本地并覆盖服务端';
        keepLocal.addEventListener('click', () => resolveConflictForce(local, remote, local, '已用本地版本覆盖服务端'));
        const keepRemote = document.createElement('button');
        keepRemote.type = 'button';
        keepRemote.className = 'utility-secondary-btn';
        keepRemote.textContent = '保留服务端并丢弃本地';
        keepRemote.addEventListener('click', () => resolveConflictTakeRemote(local, remote));
        const merge = document.createElement('button');
        merge.type = 'button';
        merge.className = 'utility-secondary-btn';
        merge.textContent = '手动合并…';
        merge.addEventListener('click', () => openConflictMergeView(local, remote, diff));
        actions.append(keepLocal, keepRemote, merge);
        utilityBody.appendChild(actions);
    }

    function openConflictMergeView(local, remote, diff) {
        const choices = { project: 'local', nodes: {}, keepLocalOnly: new Set(diff.onlyLocal.map(i => i.id)),
                          keepRemoteOnly: new Set(diff.onlyRemote.map(i => i.id)) };
        const render = () => {
            const step = document.createElement('div');
            step.className = 'conflict-merge';
            showUtilityModal('手动合并', '逐项选择');
            utilityBody.innerHTML = '';
            const projectRow = document.createElement('div');
            projectRow.className = 'conflict-row';
            projectRow.textContent = `项目名/描述采用：${choices.project === 'local' ? '本地' : '服务端'}`;
            const projectToggle = document.createElement('button');
            projectToggle.type = 'button';
            projectToggle.className = 'utility-secondary-btn';
            projectToggle.textContent = '切换';
            projectToggle.addEventListener('click', () => {
                choices.project = choices.project === 'local' ? 'remote' : 'local';
                render();
            });
            projectRow.appendChild(projectToggle);
            utilityBody.appendChild(projectRow);
            diff.changed.forEach(item => {
                const row = document.createElement('div');
                row.className = 'conflict-row';
                const current = choices.nodes[item.id] || 'local';
                row.textContent = `${item.path}：${item.fields.map(f => f.field).join('、')} → ${current === 'local' ? '本地' : '服务端'}`;
                const toggle = document.createElement('button');
                toggle.type = 'button';
                toggle.className = 'utility-secondary-btn';
                toggle.textContent = '切换';
                toggle.addEventListener('click', () => {
                    choices.nodes[item.id] = current === 'local' ? 'remote' : 'local';
                    render();
                });
                row.appendChild(toggle);
                utilityBody.appendChild(row);
            });
            const toggleListRow = (item, key) => {
                const row = document.createElement('div');
                row.className = 'conflict-row';
                const on = choices[key].has(item.id);
                row.textContent = `${key === 'keepLocalOnly' ? '仅本地有' : '仅服务端有'} · ${item.path}：${on ? '保留' : '丢弃'}`;
                const toggle = document.createElement('button');
                toggle.type = 'button';
                toggle.className = 'utility-secondary-btn';
                toggle.textContent = '切换';
                toggle.addEventListener('click', () => {
                    if (on) choices[key].delete(item.id);
                    else choices[key].add(item.id);
                    render();
                });
                row.appendChild(toggle);
                utilityBody.appendChild(row);
            };
            diff.onlyLocal.forEach(item => toggleListRow(item, 'keepLocalOnly'));
            diff.onlyRemote.forEach(item => toggleListRow(item, 'keepRemoteOnly'));
            const actions = document.createElement('div');
            actions.className = 'utility-actions';
            const apply = document.createElement('button');
            apply.type = 'button';
            apply.className = 'utility-primary-btn';
            apply.textContent = '按选择合并并保存';
            apply.addEventListener('click', () => {
                const merged = mergeProjects(local, remote, choices);
                resolveConflictForce(local, remote, merged, '已按选择合并并保存');
            });
            const back = document.createElement('button');
            back.type = 'button';
            back.className = 'utility-secondary-btn';
            back.textContent = '返回';
            back.addEventListener('click', openConflictPanel);
            actions.append(apply, back);
            utilityBody.appendChild(actions);
        };
        render();
    }

    async function resolveConflictForce(localProject, remote, replacement, successMessage) {
        try {
            const saved = await writeStoredProject(replacement, remote._revision);
            const index = projects.findIndex(item => String(item.id) === String(localProject.id));
            if (index >= 0) {
                const stored = normalizeProjects([replacement])[0] || replacement;
                stored._revision = Number(saved.revision) || (Number(remote._revision) || 0) + 1;
                if (saved.summary) stored.stats = saved.summary.stats;
                projects[index] = stored;
                rememberProjectBaseline(stored);
            }
            dirtyProjectIds.delete(String(localProject.id));
            pendingConflict = null;
            saveConflict = false;
            setSaveStatus('已保存');
            closeUtilityModal();
            renderDetail();
            showToast(successMessage);
        } catch (error) {
            if (error && error.status === 409) {
                showToast('服务端刚刚又被改动，请重新打开冲突面板');
                await beginProjectConflict(localProject, projects.find(item => String(item.id) === String(localProject.id)));
                return;
            }
            showToast(`解决冲突失败：${error.message || ''}`);
        }
    }

    function resolveConflictTakeRemote(localProject, remote) {
        const index = projects.findIndex(item => String(item.id) === String(localProject.id));
        if (index >= 0) {
            const previous = projects[index];
            remote.stats = previous.stats;
            projects[index] = remote;
            rememberProjectBaseline(remote);
        }
        dirtyProjectIds.delete(String(localProject.id));
        pendingConflict = null;
        saveConflict = false;
        setSaveStatus('已保存');
        closeUtilityModal();
        renderDetail();
        showToast('已采用服务端版本，本地改动已丢弃');
    }

    function saveProjects() {
        const completion = new Promise((resolve, reject) => saveWaiters.push({ resolve, reject }));
        completion.catch(() => undefined);
        if (!saveTimer) saveTimer = setTimeout(flushProjectsSave, SAVE_DEBOUNCE_MS);
        return completion;
    }

    // "还有没落库的东西"：排队中的防抖、在飞的请求，以及"冲突挂起 / 已标脏但没写成功"的本地改动。
    // 后两种以前被漏掉，导致冲突或保存失败期间关页不会提示，静默丢改动。
    function savePending() {
        return Boolean(saveTimer) || inFlightSaves > 0 || inFlightPatches > 0
            || Boolean(saveConflict) || dirtyProjectIds.size > 0;
    }

    function warnBeforeUnload(event) {
        if (!savePending()) return undefined;
        event.preventDefault();
        event.returnValue = '';
        return '';
    }

    function armLeaveGuard() {
        if (leaveGuardArmed) return;
        leaveGuardArmed = true;
        window.addEventListener('beforeunload', warnBeforeUnload);
    }

    function disarmLeaveGuard() {
        if (!leaveGuardArmed) return;
        leaveGuardArmed = false;
        window.removeEventListener('beforeunload', warnBeforeUnload);
    }

    // 统一等待"所有保存"：既有排队中的（saveTimer），也有已经在飞的（saveQueue/inFlightSaves）。
    // 只判断 saveTimer 会漏掉"防抖已触发、请求还没落地"的那一段窗口；
    // 单次等待又会漏掉"await 期间用户又改了东西、排了新的防抖"的情况，所以循环到真的干净为止。
    async function settleSaves() {
        for (let round = 0; round < 50; round += 1) {
            if (saveTimer) {
                await flushProjectsSave();     // 有排队中的就立刻发出去（冲突时会 reject，交给调用方处理）
            } else {
                await saveQueue.catch(() => undefined);
            }
            if (!saveTimer && inFlightSaves === 0 && inFlightPatches === 0) {
                await saveQueue.catch(() => undefined);
                if (!saveTimer && inFlightSaves === 0 && inFlightPatches === 0) return;
            }
        }
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
            showToast('背景图片读取失败，请重试');
        }
    }

    async function handleBackgroundUpload(file) {
        if (!file) return;
        try {
            showToast('正在处理背景图片…');
            const prepared = await prepareBackgroundImage(file);
            await writeStoredBackground(prepared, file.name);
            applyBackground(prepared);
            const size = (prepared.size / 1024 / 1024).toFixed(1);
            showToast(`背景已保存（${size} MB）`);
        } catch (error) {
            console.error('背景图片处理失败', error);
            showToast(`背景设置失败：${error.message || '图片读取失败，请重试'}`);
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
            showToast('恢复默认背景失败，请重试');
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
        const cached = ensureProjectCaches(project);
        return cached ? cached.remaining : countRemainingInTree(project.tree || []);
    }

    function getProjectTotal(project) {
        if (!Array.isArray(project.tree)) return Math.max(0, Number(project.stats?.total) || 0);
        const cached = ensureProjectCaches(project);
        return cached ? cached.total : 0;
    }

    function getProjectOptionalStats(project) {
        if (!Array.isArray(project.tree)) {
            return {
                total: Math.max(0, Number(project.stats?.optionalTotal) || 0),
                completed: Math.max(0, Number(project.stats?.optionalCompleted) || 0)
            };
        }
        const cached = ensureProjectCaches(project);
        return cached ? {
            total: cached.optionalTotal || 0,
            completed: cached.optionalCompleted || 0
        } : { total: 0, completed: 0 };
    }

    function findNodeById(nodes, id) {
        // 用字符串比较：服务端返回的 nodeId 一律是字符串，而默认项目里的 ID 是数字字面量，
        // 严格相等会让"首次运行、还没刷新的默认项目"在工作台里查不到任何任务。
        const wanted = String(id);
        for (const node of nodes) {
            if (String(node.id) === wanted) return node;
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

    function snapshotNodeForTrash(nodes, targetId, ancestors = []) {
        for (let index = 0; index < (nodes || []).length; index += 1) {
            const node = nodes[index];
            if (String(node.id) === String(targetId)) {
                return {
                    node: cloneData(node),
                    parentId: ancestors.length > 0 ? ancestors[ancestors.length - 1].id : null,
                    position: index,
                    path: ancestors.map(item => item.text || '').filter(Boolean).join(' / ')
                };
            }
            const child = snapshotNodeForTrash(node.children || [], targetId, ancestors.concat(node));
            if (child) return child;
        }
        return null;
    }

    function toggleAllChildren(node, completed) {
        if (node.type === 'item' && node.optional) return;
        // 已经是目标状态的节点不要再走一遍 setNodeCompleted：
        // 对已完成的周期任务重复"完成"会再克隆出下一次（连点分组复选框会指数级复制）。
        if (Boolean(node.completed) !== Boolean(completed)) {
            setNodeCompleted(node, completed);
        }
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

    function cleanupEmptyNodes(nodes, removed = null) {
        // removed（可选）用于节点级 patch：把这些"顺手清掉的空分组"也一起从服务端删掉，
        // 否则 patch 之后服务端还留着空壳，下次全量保存才消失。
        for (let i = nodes.length - 1; i >= 0; i--) {
            const node = nodes[i];
            if (node.children && node.children.length > 0) cleanupEmptyNodes(node.children, removed);
            if (node.type !== 'item' && (!node.children || node.children.length === 0)) {
                if (removed) removed.push(node.id);
                nodes.splice(i, 1);
            }
        }
        return removed;
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
        backupListError = '';
        databaseBackupPickerButton.textContent = listStatusText('backup', 'loading');
        setBackupActionsEnabled(false);
        try {
            const response = await apiFetch('/api/backups', { cache: 'no-store' });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.error || '读取备份失败，请重试');
            const optionFragment = document.createDocumentFragment();
            const menuFragment = document.createDocumentFragment();
            for (const backup of payload.backups || []) {
                const option = document.createElement('option');
                option.value = backup.name;
                option.textContent = `${backup.name} · ${formatBytes(backup.bytes)}`
                    + `${backup.kind === 'legacy' ? ' · 旧格式' : ''}${backup.valid ? '' : ' · 损坏'}`;
                option.disabled = !backup.valid;
                optionFragment.appendChild(option);
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
                menuFragment.appendChild(row);
            }
            databaseBackupSelect.replaceChildren(optionFragment);
            databaseBackupMenu.replaceChildren(menuFragment);
            if (databaseBackupSelect.options.length === 0) {
                const option = document.createElement('option');
                option.textContent = '还没有数据库备份';
                option.value = '';
                databaseBackupSelect.appendChild(option);
            }
            updateBackupPickerLabel();
        } catch (error) {
            // 失败时不能继续显示"还没有数据库备份"：那会让人以为是空目录。
            backupListError = (error && error.message) || '未知错误';
            databaseBackupSelect.replaceChildren();
            databaseBackupMenu.replaceChildren();
            databaseBackupPickerButton.textContent = listStatusText('backup', 'failed', backupListError) + '（点击重试）';
            setBackupActionsEnabled(false);
            showToast(listStatusText('backup', 'failed', backupListError));
        }
    }

    function setBackupActionsEnabled(enabled) {
        renameDatabaseBackupBtn.disabled = !enabled;
        downloadDatabaseBackupBtn.disabled = !enabled;
        inspectDatabaseBackupBtn.disabled = !enabled;
        restoreDatabaseBackupBtn.disabled = !enabled;
    }

    function updateBackupPickerLabel() {
        if (backupListError) {
            databaseBackupPickerButton.textContent = listStatusText('backup', 'failed', backupListError) + '（点击重试）';
            setBackupActionsEnabled(false);
            return;
        }
        const selected = databaseBackupSelect.options[databaseBackupSelect.selectedIndex];
        databaseBackupPickerButton.textContent = selected ? selected.textContent : '还没有数据库备份';
        setBackupActionsEnabled(Boolean(databaseBackupSelect.value));
    }

    async function createDatabaseBackupFromUi() {
        try {
            const response = await apiFetch('/api/backup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'create' })
            });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.error || '创建备份失败，请重试');
            await loadDatabaseBackups();
            databaseBackupSelect.value = payload.name;
            updateBackupPickerLabel();
            showToast(`已创建完整备份：${payload.name}`);
        } catch (error) {
            showToast(error.message || '创建数据库备份失败，请重试');
        }
    }

    async function renameDatabaseBackupFromUi() {
        const name = databaseBackupSelect.value;
        if (!name) return;
        const suggested = name.replace(/\.(sqlite3|zip)$/, '');
        const newName = window.prompt('请输入新的备份名称（可不写 .sqlite3）：', suggested);
        if (newName === null || !newName.trim()) return;
        try {
            const response = await apiFetch('/api/backup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'rename', name, newName: newName.trim() })
            });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.error || '重命名备份失败，请重试');
            await loadDatabaseBackups();
            databaseBackupSelect.value = payload.name;
            updateBackupPickerLabel();
            showToast(`已重命名备份：${payload.name}`);
        } catch (error) {
            showToast(error.message || '重命名备份失败，请重试');
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
            if (!response.ok) throw new Error(payload.error || '删除备份失败，请重试');
            await loadDatabaseBackups();
            showToast(`已删除备份：${name}`);
        } catch (error) {
            showToast(error.message || '删除备份失败，请重试');
        }
    }

    async function inspectBackup(name) {
        const response = await apiFetch(`/api/backup/inspect?name=${encodeURIComponent(name)}`, { cache: 'no-store' });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !payload.backup) throw new Error(payload.error || '读取备份内容失败，请重试');
        return payload.backup;
    }

    async function inspectDatabaseBackupFromUi() {
        const name = databaseBackupSelect.value;
        if (!name) return;
        showUtilityModal('备份内容', '恢复预览');
        renderUtilityMessage('正在校验备份…');
        let preview;
        try {
            preview = await inspectBackup(name);
        } catch (error) {
            renderUtilityMessage(error.message || '读取备份内容失败，请重试');
            return;
        }
        utilityBody.innerHTML = '';
        const list = document.createElement('div');
        list.className = 'conflict-list';
        const addRow = text => {
            const row = document.createElement('div');
            row.className = 'conflict-row';
            row.textContent = text;
            list.appendChild(row);
        };
        addRow(`备份：${preview.name}`);
        addRow(preview.kind === 'legacy'
            ? '格式：旧格式，只包含任务数据库（todo.sqlite3）'
            : `格式：完整备份（任务 + 备忘录 + 摘要），生成于 ${preview.createdAt || '未知'}`);
        if (preview.kind !== 'legacy') {
            const counts = preview.counts || {};
            addRow(`内容：项目 ${counts.projects ?? 0} · 节点 ${counts.nodes ?? 0} · 备忘录 ${counts.memos ?? 0} · 摘要 ${counts.summaries ?? 0}`);
            addRow(`schema 版本：${preview.appSchemaVersion ?? '未知'}`);
        }
        (preview.files || []).forEach(file => addRow(`${file.ok ? '校验通过' : '校验失败'} · ${file.name}（${formatBytes(file.bytes || 0)}）`));
        utilityBody.appendChild(list);
        const actions = document.createElement('div');
        actions.className = 'utility-actions';
        const restore = document.createElement('button');
        restore.type = 'button';
        restore.className = 'utility-primary-btn';
        restore.textContent = '恢复这个备份';
        restore.disabled = !preview.checksumOk;
        restore.addEventListener('click', () => resolveRestoreBackup(preview));
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'utility-secondary-btn';
        close.textContent = '关闭';
        close.addEventListener('click', closeUtilityModal);
        actions.append(restore, close);
        utilityBody.appendChild(actions);
    }

    async function resolveRestoreBackup(preview) {
        const scope = preview.kind === 'legacy'
            ? '任务数据库（todo.sqlite3）'
            : '任务、备忘录、摘要三个数据库';
        if (!window.confirm(`确认用“${preview.name}”覆盖${scope}？\n\n恢复前会自动生成一份完整应急备份；恢复后页面会重新加载。`)) return;
        try {
            const response = await apiFetch('/api/backup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'restore', name: preview.name })
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '恢复备份失败，请重试');
            window.location.reload();
        } catch (error) {
            showToast(error.message || '恢复备份失败，请重试');
        }
    }

    async function createSnapshot(reason) {
        // 大批量改动前先落一份完整快照；失败不阻断操作，但要让用户知道。
        try {
            const response = await apiFetch('/api/backup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'snapshot', reason })
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '创建快照失败');
            return payload.name;
        } catch (error) {
            showToast(`改动前快照创建失败：${error.message || ''}`);
            return null;
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
            if (!response.ok) throw new Error(payload.error || '恢复备份失败，请重试');
            window.location.reload();
        } catch (error) {
            showToast(error.message || '恢复数据库备份失败，请重试');
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
        assessmentResult.classList.add('rich-text');
        assessmentResult.innerHTML = richToHtml(formatAssessmentResult(result));
    }

    function formatBytes(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    }

    function updateAssessmentFileHint() {
        if (!assessmentFileHint) return;
        if (assessmentCodeFiles.length === 0) {
            assessmentFileHint.textContent = '可上传代码文件，也可直接在回答框中写代码；只读文本，不会执行';
            return;
        }
        const totalBytes = assessmentCodeFiles.reduce((sum, file) => sum + (Number(file.size) || 0), 0);
        const truncated = assessmentCodeFiles.some(file => Number(file.size) > 120000);
        assessmentFileHint.textContent = `已选 ${assessmentCodeFiles.length} 个文件 · ${formatBytes(totalBytes)} · 每个文件会截断到 120 KB${truncated ? '，超出部分不会发送' : ''}`;
    }

    function renderAssessmentFiles() {
        assessmentFilesList.replaceChildren();
        if (assessmentCodeFiles.length === 0) {
            assessmentFilesList.hidden = true;
            updateAssessmentFileHint();
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
        updateAssessmentFileHint();
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
        if (assessmentNode) {
            assessmentNode.assessment = {
                ...(assessmentNode.assessment || {}),
                uploadedFiles: await Promise.all(assessmentCodeFiles.map(async file => ({
                    name: file.name,
                    content: (await file.text()).slice(0, 120000)
                })))
            };
            markProjectDirty(owningProjectOfNode(assessmentNode));
            saveProjects();
        }
        renderAssessmentFiles();
    }

    async function getAssessmentFilePayload() {
        return Promise.all(assessmentCodeFiles.map(async file => ({
            name: file.name,
            content: (await file.text()).slice(0, 120000)
        })));
    }

    function renderAssessmentQuestions() {
        closeExtraAsk();
        const total = assessmentQuestionItems.length;
        assessmentQuestions.hidden = assessmentStageName !== 'questions' || total < 3;
        assessmentQuestionProgress.textContent = total >= 3
            ? `第 ${assessmentQuestionIndex + 1} / ${total} 题`
            : '正在准备题目…';
        const currentQuestion = assessmentQuestionItems[assessmentQuestionIndex] || '';
        assessmentCurrentQuestion.innerHTML = currentQuestion ? richToHtml(currentQuestion) : '';
        assessmentQuestionBtn.textContent = total >= 3 ? '重新出三道题' : 'AI 出三道题';
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
            content.className = 'rich-text';
            content.innerHTML = richToHtml(message.content);
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

    function setQuickDisabled(disabled) {
        const els = [copyQuestionBtn, summaryQuestionBtn, extraQuestionBtn,
            assessmentTemplateConclusionBtn, assessmentTemplateExplainBtn,
            assessmentTemplateCodeBtn];
        for (const el of els) {
            if (el) el.disabled = !!disabled;
        }
        if (assessmentTemplateCustomBar) {
            Array.from(assessmentTemplateCustomBar.querySelectorAll('button')).forEach(function(btn) {
                btn.disabled = !!disabled;
            });
        }
    }

    async function requestAssessmentQuestion() {
        if (!assessmentNode || assessmentQuestioning) return;
        assessmentQuestioning = true;
        setQuickDisabled(true);
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
                uploadedFiles: await getAssessmentFilePayload(),
                model: assessmentModel.value
            };
            markProjectDirty(owningProjectOfNode(assessmentNode));
            await saveProjects();
            assessmentServiceStatus.textContent = '题目已生成，请回答当前题';
        } catch (error) {
            assessmentServiceStatus.textContent = error.message || 'AI 出题失败，请重试';
        } finally {
            assessmentQuestioning = false;
            setQuickDisabled(false);
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
                assessmentServiceStatus.textContent = 'AI 服务未就绪，请检查 Key 配置';
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
        showAssessmentLive(false, true);
        assessmentCodeFiles = [];
        if (Array.isArray(node.assessment?.uploadedFiles) && node.assessment.uploadedFiles.length > 0 && typeof window.File === 'function') {
            assessmentCodeFiles = normalizeAssessmentFiles(node.assessment.uploadedFiles).map(item =>
                new File([item.content], item.name, { type: 'text/plain' })
            );
        }
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

    function restoreAssessmentSubmission() {
        if (!assessmentNode || !assessmentNode.assessment) return;
        if (assessmentNode.assessment.answer || assessmentNode.assessment.implementationDraft) {
            assessmentAnswer.value = assessmentNode.assessment.implementationDraft || assessmentNode.assessment.answer || '';
        }
        const restored = normalizeAssessmentFiles(assessmentNode.assessment.uploadedFiles);
        assessmentCodeFiles = restored.map(item => new File([item.content], item.name, { type: 'text/plain' }));
        renderAssessmentFiles();
        if (assessmentStageName === 'questions') {
            const questionText = assessmentQuestionAnswers[assessmentQuestionIndex] || '';
            if (questionText) assessmentAnswer.value = questionText;
        }
        showToast('已恢复上次输入');
    }


    function customTemplatesLoad() {
        try {
            const raw = localStorage.getItem('todo_ai_custom_templates');
            if (raw) {
                const arr = JSON.parse(raw);
                if (Array.isArray(arr)) {
                    return arr.filter(function(item) { return item && item.label && item.text; });
                }
            }
        } catch (error) { /* 忽略 */ }
        return [];
    }
    function customTemplatesSave(list) {
        try { localStorage.setItem('todo_ai_custom_templates', JSON.stringify(list)); } catch (error) { /* 忽略 */ }
    }
    function renderCustomTemplates() {
        if (!assessmentTemplateCustomBar) return;
        const list = customTemplatesLoad();
        assessmentTemplateCustomBar.hidden = list.length === 0;
        const templateFragment = document.createDocumentFragment();
        list.forEach(function(item) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'assessment-question-btn template-custom';
            btn.textContent = item.label;
            btn.title = item.text;
            btn.addEventListener('click', function() { insertTemplateText(item.text); });
            templateFragment.appendChild(btn);
        });
        assessmentTemplateCustomBar.replaceChildren(templateFragment);
    }
    function openTemplateManager() {
        showUtilityModal('答案模板', '模板管理');
        utilityBody.innerHTML = '';
        const hint = document.createElement('p');
        hint.className = 'utility-hint';
        hint.textContent = '自定义模板保存在本浏览器；点「添加」后即可在答题框一键插入';
        utilityBody.appendChild(hint);
        const listBox = document.createElement('div');
        listBox.className = 'summary-list';
        function rerender() {
            listBox.innerHTML = '';
            const cur = customTemplatesLoad();
            if (cur.length === 0) {
                const empty = document.createElement('p');
                empty.className = 'utility-empty';
                empty.textContent = '还没有自定义模板';
                listBox.appendChild(empty);
                return;
            }
            cur.forEach(function(item, index) {
                const card = document.createElement('div');
                card.className = 'summary-item';
                const row = document.createElement('div');
                row.className = 'summary-row';
                const q = document.createElement('div');
                q.className = 'summary-question';
                q.textContent = item.label;
                const del = document.createElement('button');
                del.type = 'button';
                del.className = 'utility-secondary-btn summary-delete';
                del.textContent = '删除';
                del.addEventListener('click', function() {
                    if (!window.confirm('删除模板「' + item.label + '」？')) return;
                    const cur2 = customTemplatesLoad();
                    cur2.splice(index, 1);
                    customTemplatesSave(cur2);
                    rerender();
                    renderCustomTemplates();
                });
                row.appendChild(q);
                row.appendChild(del);
                const c = document.createElement('div');
                c.className = 'summary-content';
                c.textContent = item.text;
                card.appendChild(row);
                card.appendChild(c);
                listBox.appendChild(card);
            });
        }
        utilityBody.appendChild(listBox);
        rerender();
        const editor = document.createElement('div');
        editor.className = 'template-editor';
        const labelInput = document.createElement('input');
        labelInput.type = 'text';
        labelInput.className = 'memo-title-input';
        labelInput.placeholder = '模板名称（如：排错三步）';
        const ta = document.createElement('textarea');
        ta.className = 'memo-content-input';
        ta.rows = 6;
        ta.placeholder = '模板内容：可含 Markdown / 代码块 / 换行';
        const add = document.createElement('button');
        add.type = 'button';
        add.className = 'utility-primary-btn';
        add.textContent = '添加模板';
        add.addEventListener('click', function() {
            const label = labelInput.value.trim();
            const text = ta.value;
            if (!label || !text) { showToast('请填写模板名称和内容'); return; }
            const cur = customTemplatesLoad();
            cur.push({ label: label.slice(0, 20), text: text });
            customTemplatesSave(cur);
            labelInput.value = '';
            ta.value = '';
            rerender();
            renderCustomTemplates();
            showToast('已添加模板');
        });
        editor.append(labelInput, ta, add);
        utilityBody.appendChild(editor);
    }
    function insertTemplateText(text) {
        if (!text) return;
        const start = assessmentAnswer.selectionStart ?? assessmentAnswer.value.length;
        const end = assessmentAnswer.selectionEnd ?? assessmentAnswer.value.length;
        assessmentAnswer.value = assessmentAnswer.value.slice(0, start) + text + assessmentAnswer.value.slice(end);
        assessmentAnswer.selectionStart = assessmentAnswer.selectionEnd = start + text.length;
        assessmentAnswer.focus();
        saveAssessmentDraft();
    }
    function insertAssessmentTemplate(kind) {
        const templates = {
            conclusion: '结论：\n原因：\n边界：\n',
            explain: '我先说结论：\n然后解释机制：\n最后补充容易错的边界：\n',
            code: '```python\n# 先写核心思路\n\n```\n'
        };
        insertTemplateText(templates[kind]);
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
        // 打字自动保存每 600ms 一次：判定要在改动之前做，
        // 能走节点级 patch 就不会每 600ms 上传一次整棵树（第六批 item 2）。
        const owner = owningProjectOfNode(assessmentNode);
        const patchSafe = canUseNodePatch(owner);
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
        persistNodeFields(owner, assessmentNode, nodeStateFields(assessmentNode), patchSafe);
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


    function escapeHtmlText(value) {
        return String(value).replace(/[&<>"']/g, function(ch) {
            if (ch === '&') return '&amp;';
            if (ch === '<') return '&lt;';
            if (ch === '>') return '&gt;';
            if (ch === '"') return '&quot;';
            return '&#39;';
        });
    }

    function fmtInline(seg) {
        var parts = String(seg).split('\`');
        var html = '';
        for (var i = 0; i < parts.length; i += 1) {
            if (i % 2 === 0) html += parts[i];
            else html += '<code>' + parts[i] + '</code>';
        }
        return html;
    }

    function fmtBold(seg) {
        var parts = String(seg).split('**');
        var html = '';
        for (var i = 0; i < parts.length; i += 1) {
            if (i % 2 === 0) html += fmtInline(parts[i]);
            else html += '<strong>' + fmtInline(parts[i]) + '</strong>';
        }
        return html;
    }

    function richToHtml(source) {
        var esc = escapeHtmlText(source);
        var NL = String.fromCharCode(10);
        var html = '';
        var rest = esc;
        for (;;) {
            var open = rest.indexOf('\`\`\`');
            if (open < 0) {
                html += fmtBold(rest);
                break;
            }
            html += fmtBold(rest.slice(0, open));
            var cursor = open + 3;
            var nl = rest.indexOf(NL, cursor);
            var lang = '';
            if (nl >= 0) {
                lang = rest.slice(cursor, nl).trim();
                cursor = nl + 1;
            } else {
                cursor = open + 3;
            }
            var close = rest.indexOf('\`\`\`', cursor);
            if (close < 0) {
                html += fmtBold(rest.slice(cursor));
                break;
            }
            var code = rest.slice(cursor, close);
            html += '<pre class="rich-code"><code>';
            if (lang) html += '<span class="rich-lang">' + escapeHtmlText(lang) + '</span>';
            html += code + '</code></pre>';
            rest = rest.slice(close + 3);
        }
        return html;
    }

    function showAssessmentLive(visible, clear) {
        if (!assessmentLive) return;
        if (clear && assessmentLiveBody) assessmentLiveBody.textContent = '';
        assessmentLive.hidden = !visible;
    }

    function buildPriorSummary() {
        var node = assessmentNode;
        var results = node && node.assessment && Array.isArray(node.assessment.questionResults)
            ? node.assessment.questionResults : [];
        var passed = results.filter(function(item) { return item && item.passed; });
        if (passed.length === 0) return '';
        var NL = String.fromCharCode(10);
        var lines = passed.map(function(item, index) {
            var q = String(item.question || ('第 ' + (index + 1) + ' 题')).split(NL).join(' ').slice(0, 140);
            var a = String(item.answer || '').split(NL).join(' ').slice(0, 220);
            var s = String(item.summary || item.reply || '').split(NL).join(' ').slice(0, 140);
            return '通过题: ' + q + ' | 回答要点: ' + a + ' | 结论: ' + s;
        });
        return lines.join(NL).slice(0, 1800);
    }

    async function streamEvaluate(payload, onToken, signal) {
        var response = await apiFetch('/api/evaluate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/x-ndjson' },
            body: JSON.stringify(payload),
            signal: signal
        });
        var contentType = String(response.headers.get('content-type') || '');
        if (contentType.indexOf('application/json') === 0) {
            var jsonBody = await response.json().catch(function() { return {}; });
            if (!response.ok || !jsonBody.result) throw new Error(jsonBody.error || 'AI 验收失败，请重试');
            return { result: jsonBody.result, streamed: '' };
        }
        if (!response.ok) {
            var errorBody = await response.json().catch(function() { return {}; });
            throw new Error(errorBody.error || ('AI 验收失败 (' + response.status + ')'));
        }
        if (!response.body || typeof response.body.getReader !== 'function') {
            throw new Error('当前浏览器不支持流式读取，请使用现代浏览器');
        }
        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var buffer = '';
        var streamed = '';
        for (;;) {
            var chunk = await reader.read();
            if (chunk.done) break;
            buffer += decoder.decode(chunk.value, { stream: true });
            var nlIndex;
            while ((nlIndex = buffer.indexOf('\n')) >= 0) {
                var line = buffer.slice(0, nlIndex).trim();
                buffer = buffer.slice(nlIndex + 1);
                if (!line) continue;
                var event;
                try { event = JSON.parse(line); } catch (err) { continue; }
                if (!event || typeof event !== 'object') continue;
                if (event.type === 'text') {
                    var token = String(event.text || '');
                    streamed += token;
                    if (onToken) onToken(token);
                } else if (event.type === 'result') {
                    return {
                        result: event.result,
                        streamed: streamed || String((event.humanText) || '')
                    };
                } else if (event.type === 'error') {
                    throw new Error(event.message || 'AI 验收失败，请重试');
                }
            }
        }
        throw new Error('AI 响应不完整，请重试');
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
        setQuickDisabled(true);
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
                assessmentResult.textContent = error.message || '提交失败，请重试';
                assessmentServiceStatus.textContent = '提交失败，请重试';
            } finally {
                assessmentSubmitting = false;
            setQuickDisabled(false);
                assessmentSubmitBtn.disabled = false;
                assessmentSubmitBtn.textContent = '提交';
            }
            return;
        }
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 90000);
        try {
            showAssessmentLive(true, true);
            const evaluatePayload = {
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
                totalQuestions: assessmentQuestionItems.length,
                priorSummary: buildPriorSummary(),
                stream: true
            };
            const payload = await streamEvaluate(evaluatePayload, (token) => {
                assessmentLiveBody.textContent += token;
                assessmentLiveBody.scrollTop = assessmentLiveBody.scrollHeight;
            }, controller.signal);
            showAssessmentLive(false);
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
            result.question = assessmentStageName === 'questions'
                ? String(assessmentQuestionItems[assessmentQuestionIndex] || '') : '';
            if (assessmentStageName === 'questions') {
                assessmentQuestionAnswers[assessmentQuestionIndex] = answer;
                const conversation = assessmentQuestionConversations[assessmentQuestionIndex] || [];
                conversation.push({ role: 'user', content: answer.slice(0, MAX_CONVERSATION_MESSAGE_CHARS) });
                conversation.push({
                    role: 'assistant',
                    content: (payload.streamed || result.reply || formatAssessmentResult(result))
                        .slice(0, MAX_CONVERSATION_MESSAGE_CHARS)
                });
                assessmentQuestionConversations[assessmentQuestionIndex] = conversation.slice(-MAX_CONVERSATION_MESSAGES);
                assessmentNode.assessment = {
                    ...(assessmentNode.assessment || {}),
                    questionSet: assessmentQuestionItems,
                    questionIndex: assessmentQuestionIndex,
                    questionAnswers: assessmentQuestionAnswers,
                    questionConversations: assessmentQuestionConversations,
                    uploadedFiles: await getAssessmentFilePayload(),
                    questionResults: [...(assessmentNode.assessment?.questionResults || []), result]
                        .slice(-MAX_QUESTION_RESULTS),
                    model: assessmentModel.value
                };
                if (!result.passed) {
                    markProjectDirty(owningProjectOfNode(assessmentNode));
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
                markProjectDirty(owningProjectOfNode(assessmentNode));
                await saveProjects();
                showAssessmentResult({ ...result, summary: '三道题全部通过。第二阶段可留空提交；填写内容则继续由 AI 验收。' });
                assessmentServiceStatus.textContent = '第一阶段已通过；第二阶段可留空提交';
                return;
            }
            assessmentNode.assessment = { ...(assessmentNode.assessment || {}), ...result,
                stage: assessmentStageName,
                answer: answer.slice(0, MAX_ASSESSMENT_ANSWER_CHARS),
                implementationDraft: '',
                uploadedFiles: await getAssessmentFilePayload()
            };
            setNodeCompleted(assessmentNode, assessmentStageName === 'implementation' && result.passed);
            markProjectDirty(owningProjectOfNode(assessmentNode));
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
            showAssessmentLive(false);
            const message = error.name === 'AbortError' ? '请求超时，请重试' : error.message || 'AI 验收失败，请重试';
            assessmentResult.hidden = false;
            assessmentResult.classList.add('failed');
            assessmentResult.textContent = message;
            assessmentServiceStatus.textContent = '验收请求失败，请重试';
        } finally {
            clearTimeout(timeout);
            assessmentSubmitting = false;
            setQuickDisabled(false);
            assessmentSubmitBtn.disabled = false;
            assessmentSubmitBtn.textContent = assessmentStageName === 'questions' ? '提交本题' : '提交';
        }
    }

    function subtreeRequiresAssessment(node) {
        if (node.type === 'item') return Boolean(node.assessmentRequired);
        return (node.children || []).some(child => subtreeRequiresAssessment(child));
    }

    function getNodeStats(node) {
        const project = getCurrentProject();
        if (!project) return { total: 0, remaining: 0 };
        return getCachedNodeStats(project, node);
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

    function nodeMatchesMetaFilter(node) {
        if (nodeFilters.priority !== 'all') {
            const priority = node.priority || '';
            if (nodeFilters.priority === 'none' ? Boolean(priority) : priority !== nodeFilters.priority) return false;
        }
        const tagQuery = nodeFilters.tag.trim().toLowerCase();
        if (tagQuery) {
            const tags = (node.tags || []).map(tag => String(tag).toLowerCase());
            if (!tags.some(tag => tag.includes(tagQuery))) return false;
        }
        if (nodeFilters.due !== 'all') {
            const due = node.dueDate || '';
            const today = todayStr();
            if (nodeFilters.due === 'none') {
                if (due) return false;
            } else if (!due) {
                return false;
            } else if (nodeFilters.due === 'overdue') {
                if (!(due < today)) return false;
            } else if (nodeFilters.due === 'today') {
                if (due !== today) return false;
            } else if (nodeFilters.due === 'week') {
                // "未来 1-7 天"：今天到期另有单独的筛选项。
                const days = daysBetween(today, due);
                if (days === null || days < 1 || days > 7) return false;
            } else if (nodeFilters.due === 'soon') {
                // "7 天内到期（含今天）"
                const days = daysBetween(today, due);
                if (days === null || days < 0 || days > 7) return false;
            }
        }
        return true;
    }

    function nodeMatchesOwnFilter(node) {
        if (!nodeMatchesMetaFilter(node)) return false;
        const query = nodeFilters.query.trim().toLowerCase();
        const textMatches = !query || node.text.toLowerCase().includes(query);
        return textMatches && nodeMatchesStatus(node, nodeFilters.status);
    }

    function nodeHasVisibleMatch(node) {
        if (nodeMatchesOwnFilter(node)) return true;
        return (node.children || []).some(child => nodeHasVisibleMatch(child));
    }

    function isNodeFiltering() {
        // 元数据筛选（优先级/截止/标签）也算"正在筛选"：
        // 漏掉它们时 renderDetail 会走"整棵树原样渲染"的分支，筛选条件被完全忽略。
        return Boolean(nodeFilters.query.trim())
            || nodeFilters.status !== 'all'
            || nodeFilters.priority !== 'all'
            || nodeFilters.due !== 'all'
            || Boolean(nodeFilters.tag.trim());
    }

    function projectMatchesFilter(project) {
        const query = projectFilters.query.trim().toLowerCase();
        const textMatches = !query || `${project.name} ${project.description || ''}`.toLowerCase().includes(query);
        if (!textMatches) return false;
        const total = getProjectTotal(project);
        const remaining = getProjectRemaining(project);
        if (projectFilters.status === 'archived') return Boolean(project.archived);
        if (project.archived) return false;
        if (projectFilters.status === 'active') return remaining > 0;
        if (projectFilters.status === 'completed') return total > 0 && remaining === 0;
        if (projectFilters.status === 'empty') return total === 0;
        return true;
    }

    function getVisibleProjects() {
        return projects.filter(projectMatchesFilter);
    }

    async function exportBackup(format = 'json') {
        // 导出的是服务端库里的完整项目，先把手上的改动落库，避免导出旧数据。
        try {
            await settleSaves();
        } catch (error) {
            showToast('当前修改尚未保存，请先解决保存失败');
            return;
        }
        const meta = {
            json: { ext: 'json', label: 'JSON 备份' },
            markdown: { ext: 'md', label: 'Markdown 文档' },
            csv: { ext: 'csv', label: 'CSV 表格' },
        }[format] || { ext: 'json', label: 'JSON 备份' };
        const link = document.createElement('a');
        link.href = `${getAssessmentApiUrl('/api/export')}?token=${encodeURIComponent(sessionToken)}`
            + `&format=${encodeURIComponent(format)}`;
        link.download = `todo-projects-${todayStr()}.${meta.ext}`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        showToast(`正在下载${meta.label}`);
    }

    function downloadDatabaseBackup() {
        const name = databaseBackupSelect.value;
        if (!name) return;
        const link = document.createElement('a');
        link.href = `${getAssessmentApiUrl('/api/backup/download')}?name=${encodeURIComponent(name)}&token=${encodeURIComponent(sessionToken)}`;
        link.download = name;
        document.body.appendChild(link);
        link.click();
        link.remove();
        showToast(`正在下载数据库备份：${name}`);
    }

    async function clearAssessmentHistoryInDetail() {
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
        await createSnapshot('before-clear-history');
        candidates.forEach(node => {
            const preserved = Object.fromEntries(
                Object.entries(node.assessment).filter(([key]) => !removableKeys.has(key))
            );
            node.assessment = Object.keys(preserved).length > 0 ? preserved : null;
        });
        markProjectDirty(project);
        saveProjects();
        renderDetail();
        showToast(`已清理 ${candidates.length} 个任务的验收记录`);
    }

    async function importBackup(file) {
        if (!file) return;
        try {
            let payload;
            try {
                payload = JSON.parse(await file.text());
            } catch (parseError) {
                throw new Error('这不是 JSON 备份文件；数据库备份（.sqlite3）请用上方备份列表的「恢复」');
            }
            const imported = extractProjects(payload);
            if (!imported) throw new Error('备份文件格式不正确');
            await openImportPreview(imported);
        } catch (error) {
            console.error('导入备份失败', error);
            showToast(`导入失败：${error.message || '文件读取失败，请重试'}`);
        } finally {
            importInput.value = '';
        }
    }

    // 导入预览：先看差异（新增/修改/重复/覆盖/AI 历史），再选替换 / 合并 / 新建
    async function openImportPreview(imported) {
        const nextProjects = normalizeProjects(imported);
        ensureRemedialQueueAtBottom(nextProjects);
        nextProjects.forEach(project => expandAllNodes(project.tree || [], false));
        const state = { mode: 'replace', keepAiHistory: true, preview: null };
        showUtilityModal('导入预览', '替换全部 · 合并到现有项目 · 导入为新项目');
        utilityBody.innerHTML = '';
        const form = document.createElement('div');
        form.className = 'meta-form';
        const hint = document.createElement('p');
        hint.className = 'utility-hint';
        hint.textContent = `文件里有 ${nextProjects.length} 个项目。三种模式都不会丢数据：执行前会自动留一份完整快照。`;
        form.appendChild(hint);
        const modeSelect = document.createElement('select');
        [
            ['replace', '替换全部（当前数据被文件覆盖）'],
            ['merge', '合并到现有项目（同 ID 覆盖，新节点追加，本地独有的保留）'],
            ['new', '导入为新项目（生成新项目 ID，不动现有项目）'],
        ].forEach(([value, text]) => {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = text;
            modeSelect.appendChild(option);
        });
        modeSelect.value = state.mode;
        addMetaField(form, '导入方式', modeSelect);
        const keepLabel = document.createElement('label');
        keepLabel.className = 'option-row';
        const keepInput = document.createElement('input');
        keepInput.type = 'checkbox';
        keepInput.checked = true;
        const keepText = document.createElement('span');
        keepText.textContent = '保留文件里的 AI 验收历史与复习安排';
        keepLabel.append(keepInput, keepText);
        form.appendChild(keepLabel);
        const report = document.createElement('div');
        report.className = 'import-report';
        form.appendChild(report);
        const actions = document.createElement('div');
        actions.className = 'utility-actions';
        const confirm = document.createElement('button');
        confirm.type = 'button';
        confirm.className = 'utility-primary-btn';
        confirm.textContent = '确认导入';
        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'utility-secondary-btn';
        cancel.textContent = '取消';
        cancel.addEventListener('click', closeUtilityModal);
        actions.append(confirm, cancel);
        form.appendChild(actions);
        utilityBody.appendChild(form);

        const renderReport = (preview) => {
            report.replaceChildren();
            const lines = [];
            if (preview.duplicates && preview.duplicates.length > 0) {
                lines.push(`✘ 发现 ${preview.duplicates.length} 处重复 ID，导入会被拒绝：`);
                preview.duplicates.slice(0, 5).forEach(problem => lines.push('　· ' + problem));
                if (preview.duplicates.length > 5) lines.push(`　· ……共 ${preview.duplicates.length} 处`);
                confirm.disabled = true;
            } else {
                confirm.disabled = false;
            }
            const totals = preview.totals || {};
            lines.push(`新增项目：${preview.newProjects.length} 个`
                + (preview.newProjects.length ? '（' + preview.newProjects.slice(0, 3).map(entry => entry.name).join('、')
                    + (preview.newProjects.length > 3 ? '…' : '') + '）' : ''));
            lines.push(`更新项目：${preview.updatedProjects.length} 个`
                + (preview.updatedProjects.length
                    ? `（新增 ${totals.addedNodes || 0} 个任务、修改 ${totals.updatedNodes || 0} 个）` : ''));
            if (preview.removedProjects.length > 0) {
                lines.push(`将被移除：${preview.removedProjects.length} 个项目`
                    + `（${preview.removedProjects.slice(0, 3).map(entry => entry.name).join('、')}`
                    + `${preview.removedProjects.length > 3 ? '…' : ''}，删除 ${totals.deletedNodes || 0} 个节点）`);
            }
            if (totals.keptLocalOnlyNodes) {
                lines.push(`本地独有、不会被删除的节点：${totals.keptLocalOnlyNodes} 个`);
            }
            const ai = preview.aiHistory || {};
            lines.push(`AI 历史：文件里有 ${ai.nodesWithAssessment || 0} 个验收记录、`
                + `${ai.nodesWithReview || 0} 个复习安排 —— ${ai.policy || ''}`);
            lines.forEach(text => {
                const line = document.createElement('p');
                line.className = 'import-report-line';
                line.textContent = text;
                report.appendChild(line);
            });
        };

        const refresh = async () => {
            report.replaceChildren();
            const loading = document.createElement('p');
            loading.className = 'utility-empty';
            loading.textContent = '正在对比…';
            report.appendChild(loading);
            try {
                const response = await apiFetch('/api/import/preview', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        projects: nextProjects.map(serializeProject),
                        mode: state.mode,
                        keepAiHistory: state.keepAiHistory,
                    }),
                });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(payload.error || '预览失败');
                state.preview = payload.preview;
                renderReport(payload.preview);
            } catch (error) {
                report.replaceChildren();
                const failed = document.createElement('p');
                failed.className = 'utility-empty';
                failed.textContent = `预览失败：${error.message || ''}`;
                report.appendChild(failed);
                confirm.disabled = true;
            }
        };
        modeSelect.addEventListener('change', () => { state.mode = modeSelect.value; refresh(); });
        keepInput.addEventListener('change', () => { state.keepAiHistory = keepInput.checked; refresh(); });
        confirm.addEventListener('click', async () => {
            if (confirm.disabled) return;
            confirm.disabled = true;
            try {
                await settleSaves();
                const response = await apiFetch('/api/import', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        projects: nextProjects.map(serializeProject),
                        mode: state.mode,
                        keepAiHistory: state.keepAiHistory,
                    }),
                });
                const result = await response.json().catch(() => ({}));
                if (!response.ok || !Array.isArray(result.projects)) {
                    throw new Error(result.error || '导入失败，请重试');
                }
                projects = result.projects.map(normalizeProjectSummary);
                savedProjectJsonById.clear();
                saveConflict = false;
                currentProjectId = null;
                renderProjects();
                closeUtilityModal();
                if (result.backup) {
                    pushUndoStep({
                        label: '导入项目',
                        ops: [{ kind: 'restore-backup', name: result.backup }],
                    });
                }
                showToast(`已导入（${state.mode === 'replace' ? '替换全部' : state.mode === 'merge' ? '合并' : '新项目'}）`,
                    undoAction());
            } catch (error) {
                confirm.disabled = false;
                showToast(`导入失败：${error.message || ''}`);
            }
        });
        await refresh();
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
        utilityModal.querySelector('.utility-dialog').classList.toggle('utility-wide', kicker === '摘要清单');
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

    async function loadMemos(query = '') {
        const suffix = query ? `?q=${encodeURIComponent(query)}` : '';
        const response = await apiFetch(`/api/memos${suffix}`, { cache: 'no-store' });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !Array.isArray(payload.memos)) throw new Error(payload.error || '读取备忘录失败，请重试');
        // 列表接口只回预览；已经取过全文的备忘录要把 content 保留下来，否则编辑框会被清空。
        const loadedContent = new Map(
            memoState.memos.filter(memo => typeof memo.content === 'string').map(memo => [memo.id, memo.content])
        );
        memoState.memos = payload.memos.map(summary => (
            loadedContent.has(summary.id)
                ? Object.assign(summary, { content: loadedContent.get(summary.id) })
                : summary
        ));
        if (!memoState.memos.some(memo => memo.id === memoState.selectedId)) {
            memoState.selectedId = memoState.memos[0]?.id || null;
        }
    }

    function memoContentReady(memo) {
        // 只有取到全文才允许写回：列表里的对象只有 contentPreview，直接保存会把备忘录截断。
        return Boolean(memo) && typeof memo.content === 'string';
    }

    async function ensureMemoLoaded(memo) {
        if (!memo || memoContentReady(memo)) return memo;
        const response = await apiFetch(`/api/memo?id=${encodeURIComponent(memo.id)}`, { cache: 'no-store' });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !payload.memo) throw new Error(payload.error || '读取备忘录失败，请重试');
        Object.assign(memo, payload.memo);
        return memo;
    }

    function currentMemo() {
        return memoState.memos.find(memo => memo.id === memoState.selectedId) || null;
    }

    function persistMemo(memo) {
        if (!memo) return Promise.resolve(null);
        if (!memoContentReady(memo)) {
            return Promise.reject(new Error('备忘录全文尚未加载，已取消保存以免覆盖原文'));
        }
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
            if (!response.ok || !payload.memo) throw new Error(payload.error || '保存备忘录失败，请重试');
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
            setMemoSaveStatus(error.message || '保存失败，请重试', 'error');
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
                showToast(error.message || '备忘录保存失败，请重试');
            }
        }, 450);
    }

    function renderMemoList(container, editor) {
        const query = memoState.query.trim();
        const visible = memoState.memos;
        if (visible.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'memo-empty';
            empty.textContent = query ? '没有匹配的备忘录' : '还没有备忘录';
            container.replaceChildren(empty);
            return;
        }
        const memoFragment = document.createDocumentFragment();
        visible.forEach(memo => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = `memo-list-item${memo.id === memoState.selectedId ? ' selected' : ''}`;
            const title = document.createElement('strong');
            title.textContent = memo.title || '未命名备忘录';
            const preview = document.createElement('small');
            const liveText = typeof memo.content === 'string' ? memo.content : (memo.contentPreview || '');
            preview.textContent = liveText.replace(/\s+/g, ' ').trim() || '还没有内容';
            const meta = document.createElement('span');
            const stamp = memo.updatedAt ? memo.updatedAt.slice(0, 10) : '';
            const size = Number.isFinite(memo.contentLength) ? ` · ${memo.contentLength} 字` : '';
            meta.textContent = `${memo.pinned ? '置顶 · ' : ''}${stamp}${size}`;
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
            memoFragment.appendChild(button);
        });
        container.replaceChildren(memoFragment);
    }

    async function renderMemoPanel() {
        showUtilityModal('备忘录', '个人记录');
        const selected = currentMemo();
        if (selected && !memoContentReady(selected)) {
            renderUtilityMessage('正在读取备忘录…');
            try {
                await ensureMemoLoaded(selected);
            } catch (error) {
                renderUtilityMessage(error.message || '读取备忘录失败，请重试');
                return;
            }
        }
        utilityBody.innerHTML = '';
        const toolbar = document.createElement('div');
        toolbar.className = 'memo-toolbar';
        const search = document.createElement('input');
        search.type = 'search';
        search.className = 'memo-search';
        search.placeholder = '搜索备忘录';
        search.value = memoState.query;
        search.addEventListener('input', debounce(async () => {
            memoState.query = search.value;
            try {
                if (memoState.saveTimer) await saveMemoNow(currentMemo());
                await loadMemos(memoState.query.trim());
            } catch (error) {
                showToast(error.message || '搜索备忘录失败，请重试');
                return;
            }
            renderMemoList(list, editor);
        }, SEARCH_DEBOUNCE_MS));
        const newButton = document.createElement('button');
        newButton.type = 'button';
        newButton.className = 'utility-primary-btn';
        newButton.textContent = '新建';
        newButton.addEventListener('click', async () => {
            try {
                if (currentMemo() && memoState.saveTimer) await saveMemoNow(currentMemo());
                const response = await apiFetch('/api/memo', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: '未命名备忘录', content: '', pinned: false })
                });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok || !payload.memo) throw new Error(payload.error || '新建备忘录失败，请重试');
                memoState.memos.unshift(payload.memo);
                memoState.selectedId = payload.memo.id;
                memoState.query = '';
                await renderMemoPanel();
                editorFocusTitle();
            } catch (error) {
                showToast(error.message || '新建备忘录失败，请重试');
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
        // 标题/正文每敲一个字就重建整个备忘录列表太浪费，跟搜索用同一档防抖。
        const refreshList = debounce(() => renderMemoList(list, editor), SEARCH_DEBOUNCE_MS);
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
                refreshList();
            });
            const contentInput = document.createElement('textarea');
            contentInput.className = 'memo-content-input';
            contentInput.value = memo.content;
            contentInput.placeholder = '记录想法、命令、代码片段或待办事项…';
            contentInput.addEventListener('input', () => {
                memo.content = contentInput.value;
                scheduleMemoSave();
                refreshList();
            });
            const editorToolbar = document.createElement('div');
            editorToolbar.className = 'memo-editor-toolbar';
            const pinButton = document.createElement('button');
            pinButton.type = 'button';
            pinButton.className = 'utility-secondary-btn';
            pinButton.textContent = memo.pinned ? '★ 已置顶' : '☆ 置顶';
            pinButton.addEventListener('click', async () => {
                if (memoState.saveTimer) {
                    try { await saveMemoNow(memo); } catch (error) { showToast('当前修改尚未保存，请先解决保存失败'); return; }
                }
                memo.pinned = !memo.pinned;
                pinButton.textContent = memo.pinned ? '★ 已置顶' : '☆ 置顶';
                try {
                    await persistMemo(memo);
                    renderMemoList(list, editor);
                } catch (error) {
                    showToast(error.message || '保存置顶状态失败，请重试');
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
                    if (!response.ok) throw new Error(payload.error || '删除备忘录失败，请重试');
                    memoState.memos = payload.memos || memoState.memos.filter(item => item.id !== memo.id);
                    memoState.selectedId = memoState.memos[0]?.id || null;
                    renderMemoPanel();
                } catch (error) {
                    showToast(error.message || '删除备忘录失败，请重试');
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
                    showToast(error.message || '备忘录保存失败，请重试');
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
        exportButton.textContent = '导出备忘录数据库';
        exportButton.addEventListener('click', downloadMemoDatabase);
        const importLabel = document.createElement('label');
        importLabel.className = 'utility-secondary-btn memo-import-label';
        importLabel.textContent = '导入备忘录数据库';
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
        renderUtilityMessage('正在读取备忘录…');
        memoState.query = '';
        try {
            await loadMemos();
            await renderMemoPanel();
        } catch (error) {
            renderUtilityMessage(error.message || '读取备忘录失败，请重试');
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
            showToast(error.message || '导出备忘录数据库失败，请重试');
        }
    }

    async function importMemoDatabase(file) {
        if (!file) return;
        if (!window.confirm('导入会替换当前全部备忘录，项目数据库不会改变。确认继续？')) return;
        try {
            const response = await apiFetch('/api/memos/database-import', { method: 'POST', body: await file.arrayBuffer() });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || !Array.isArray(payload.memos)) throw new Error(payload.error || '导入备忘录数据库失败，请重试');
            memoState.memos = payload.memos;
            memoState.selectedId = memoState.memos[0]?.id || null;
            memoState.query = '';
            renderMemoPanel();
            showToast('已导入独立备忘录数据库');
        } catch (error) {
            showToast(error.message || '导入备忘录数据库失败，请重试');
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
            showToast(error.message || '任务定位失败，请重试');
        }
    }

    function renderProjectPicker(action) {
        showUtilityModal(`选择项目 · ${studyActionNames[action]}`, '选择范围');
        utilityBody.innerHTML = '';
        const hint = document.createElement('p');
        hint.className = 'utility-hint';
        hint.textContent = '选择一个项目后继续，不会自动修改任何任务';
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
            progress.textContent = total > 0 ? `主线 ${completed}/${total}` : '还没有主线任务';
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
                    showToast(error.message || '项目加载失败，请重试');
                    button.disabled = false;
                }
            });
            list.appendChild(button);
        }
        if (projects.length === 0) {
            if (stateLoadError) {
                // 读失败时不能显示"还没有可选择的项目"，否则用户会以为库里真的没项目。
                const failed = document.createElement('p');
                failed.className = 'utility-empty';
                failed.textContent = '读取项目失败：' + stateLoadError;
                utilityBody.appendChild(failed);
                utilityBody.appendChild(createRetryButton('重新加载项目', async () => {
                    await retryLoadProjects();
                    renderProjectPicker(action);
                }));
                return;
            }
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
            list.replaceChildren(...entries.slice(0, visibleCount).map(entry => createTaskButton(entry, project.id)));
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
            again.textContent = '再抽一个';
            again.addEventListener('click', () => draw(true));
            const go = document.createElement('button');
            go.type = 'button';
            go.className = 'utility-primary-btn';
            go.textContent = '去复习';
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
                : '还没有完成记录'],
            ['最近完成', stats.latestCompletion
                ? `${new Date(stats.latestCompletion.completedAt).toLocaleString('zh-CN', { hour12: false })} · ${stats.latestCompletion.text}`
                : '还没有完成记录']
        ];
        const factFragment = document.createDocumentFragment();
        facts.forEach(([name, value]) => {
            const item = document.createElement('div');
            item.className = 'stats-item';
            const itemLabel = document.createElement('span');
            itemLabel.textContent = name;
            const itemValue = document.createElement('strong');
            itemValue.textContent = value;
            item.append(itemLabel, itemValue);
            factFragment.appendChild(item);
        });
        grid.replaceChildren(factFragment);
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
            showToast('学习工具加载失败，请刷新页面重试');
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

    // 纯函数：项目网格空状态该显示什么（便于单测；DOM 组装在 renderProjects 里）。
    function projectsEmptyStateView(loadError, totalCount, visibleCount) {
        if (loadError) return { text: '读取项目失败：' + loadError, retry: true };
        if (totalCount === 0) return { text: '还没有项目，创建一个开始学习吧', retry: false };
        if (visibleCount === 0) return { text: '没有符合筛选条件的项目', retry: false };
        return null;
    }

    // 纯函数：列表加载状态文案，供复习队列 / 全局搜索 / 备份列表共用（措辞统一）。
    function listStatusText(kind, state, detail) {
        const name = kind === 'review' ? '复习队列' : kind === 'search' ? '项目列表' : '数据库备份';
        if (state === 'loading') return '正在读取' + name + '…';
        if (state === 'failed') return '读取' + name + '失败：' + (detail || '未知错误');
        return '';
    }

    function renderProjectsMessage(state) {
        // 空/失败状态必须同时清空网格，否则筛选无结果时会留着上一次渲染的卡片。
        projectGrid.replaceChildren();
        emptyProjects.style.display = 'block';
        emptyProjects.replaceChildren();
        const text = document.createElement('span');
        text.textContent = state.text;
        emptyProjects.appendChild(text);
        if (state.retry) {
            emptyProjects.appendChild(createRetryButton('重新加载项目', retryLoadProjects));
        }
    }

    function createRetryButton(label, handler) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'inline-retry-btn';
        button.textContent = label;
        button.addEventListener('click', handler);
        return button;
    }

    async function retryLoadProjects() {
        renderProjectsMessage({ text: '正在重新加载项目…', retry: false });
        await loadProjects();
        renderProjects();
        loadReviewCounts();
        if (!stateLoadError) showToast('已重新连接本地服务');
    }

    function renderProjects() {
        const reviewTotal = reviewCounts.today + reviewCounts.overdue;
        if (reviewQueueCount) {
            reviewQueueCount.textContent = String(reviewTotal);
            reviewQueueBtn.classList.toggle('empty', reviewTotal === 0);
        }
        const visibleProjects = getVisibleProjects();
        const emptyState = projectsEmptyStateView(stateLoadError, projects.length, visibleProjects.length);
        if (emptyState) {
            renderProjectsMessage(emptyState);
            return;
        }
        emptyProjects.style.display = 'none';
        const cardFragment = document.createDocumentFragment();
        visibleProjects.forEach(project => {
            ensureProjectCaches(project);
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
            editBtn.textContent = '✎';
            editBtn.title = '编辑项目名称';
            editBtn.setAttribute('aria-label', '编辑项目名称');
            editBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                try {
                    const loadedProject = await ensureProjectLoaded(project.id);
                    startEditProjectName(loadedProject, nameDiv, card);
                } catch (error) {
                    showToast(error.message || '项目加载失败，请重试');
                }
            });
            const delBtn = document.createElement('button');
            delBtn.textContent = '✕';
            delBtn.title = '删除项目';
            delBtn.setAttribute('aria-label', '删除项目');
            delBtn.classList.add('delete-proj-btn');
            delBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteProject(project.id, card);
            });
            const archiveBtn = document.createElement('button');
            archiveBtn.type = 'button';
            archiveBtn.classList.add('archive-proj-btn');
            archiveBtn.textContent = project.archived ? '↩' : '▣';
            archiveBtn.title = project.archived ? '取消归档' : '归档（默认列表不再显示）';
            archiveBtn.setAttribute('aria-label', archiveBtn.title);
            archiveBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleProjectArchived(project.id);
            });
            actions.appendChild(editBtn);
            if (String(project.id) !== INBOX_PROJECT_ID) {
                // 收集箱不给归档入口（保留项目，快速添加永远写进它）
                actions.appendChild(archiveBtn);
            }
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
                    showToast(error.message || '项目加载失败，请重试');
                }
            });
            nameDiv.addEventListener('dblclick', async (e) => {
                e.stopPropagation();
                try {
                    const loadedProject = await ensureProjectLoaded(project.id);
                    startEditProjectName(loadedProject, nameDiv, card);
                } catch (error) {
                    showToast(error.message || '项目加载失败，请重试');
                }
            });
            cardFragment.appendChild(card);
        });
        projectGrid.replaceChildren(cardFragment);
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
                markProjectDirty(project);
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
        if (!window.confirm(`确认删除项目“${removedProject.name}”？\n会放进回收站，之后可以恢复（也能用 Ctrl+Z 撤销）。`)) return;
        try {
            setSaveStatus('保存中…', 'saving');
            const removed = await deleteStoredProject(projectId, removedProject._revision);
            pushUndoStep({
                label: `删除项目「${removedProject.name}」`,
                ops: [{ kind: 'project-delete', projectId }],
                trashId: (removed && removed.trashId) || '',
            });
        } catch (error) {
            setSaveStatus(error.status === 409 ? '版本冲突' : '保存失败', 'error');
            showToast(error.message || '删除项目失败，请重试');
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
            // 删除前可能还留着"脏"标记/旧 JSON 基准：不清掉的话 savePending() 会一直为真，
            // 每次关页面都弹"未保存"提示（而且那个项目已经不存在了）。
            dirtyProjectIds.delete(String(projectId));
            forgetProjectBaseline(projectId);
            if (currentProjectId === projectId) currentProjectId = null;
            renderProjects();
            setSaveStatus('已保存');
            showToast(`已删除项目：${removedProject.name}`, undoAction());
        }, 400);
    }

    // ===================== 第五批：历史（撤销/重做）与结构操作 =====================

    const UNDO_STORAGE_KEY = 'todo_list_undo_v1';
    const MAX_UNDO_STEPS = 20;
    const MAX_UNDO_BYTES = 200 * 1024;   // localStorage 单步太大就不持久化，避免写爆
    let undoStack = [];
    let redoStack = [];
    let historyBusy = false;
    let dragState = null;

    // 通用"勾选项"对话框：返回 {key: bool} 或 null（取消）
    function openOptionDialog(title, hint, options, confirmLabel) {
        return new Promise(resolve => {
            showUtilityModal(title, '可逆操作，之后还能撤销');
            utilityBody.innerHTML = '';
            const form = document.createElement('div');
            form.className = 'meta-form';
            const description = document.createElement('p');
            description.className = 'utility-hint';
            description.textContent = hint;
            form.appendChild(description);
            const boxes = {};
            options.forEach(entry => {
                const label = document.createElement('label');
                label.className = 'option-row';
                const input = document.createElement('input');
                input.type = 'checkbox';
                input.checked = Boolean(entry.checked);
                const span = document.createElement('span');
                span.textContent = entry.label;
                label.append(input, span);
                form.appendChild(label);
                boxes[entry.key] = input;
            });
            const actions = document.createElement('div');
            actions.className = 'utility-actions';
            const confirm = document.createElement('button');
            confirm.type = 'button';
            confirm.className = 'utility-primary-btn';
            confirm.textContent = confirmLabel || '确定';
            confirm.addEventListener('click', () => {
                const result = {};
                Object.entries(boxes).forEach(([key, input]) => { result[key] = input.checked; });
                closeUtilityModal();
                resolve(result);
            });
            const cancel = document.createElement('button');
            cancel.type = 'button';
            cancel.className = 'utility-secondary-btn';
            cancel.textContent = '取消';
            cancel.addEventListener('click', () => { closeUtilityModal(); resolve(null); });
            actions.append(confirm, cancel);
            form.appendChild(actions);
            utilityBody.appendChild(form);
        });
    }

    function addMetaField(form, labelText, control) {
        const label = document.createElement('label');
        label.className = 'meta-field';
        const caption = document.createElement('span');
        caption.textContent = labelText;
        label.append(caption, control);
        form.appendChild(label);
        return label;
    }

    function loadUndoStack() {
        try {
            const raw = JSON.parse(localStorage.getItem(UNDO_STORAGE_KEY) || 'null');
            if (raw && Array.isArray(raw.undo) && Array.isArray(raw.redo)) {
                undoStack = raw.undo.slice(-MAX_UNDO_STEPS);
                redoStack = raw.redo.slice(-MAX_UNDO_STEPS);
            }
        } catch (error) {
            undoStack = [];
            redoStack = [];
        }
        renderUndoButtons();
    }

    function persistUndoStack() {
        try {
            const payload = JSON.stringify({ undo: undoStack, redo: redoStack });
            if (payload.length > MAX_UNDO_BYTES) {
                // 太大（例如整棵子树的克隆）就只保留最近几步
                localStorage.setItem(UNDO_STORAGE_KEY, JSON.stringify({
                    undo: undoStack.slice(-3), redo: redoStack.slice(-3)
                }));
            } else {
                localStorage.setItem(UNDO_STORAGE_KEY, payload);
            }
        } catch (error) {
            console.warn('撤销记录无法持久化', error);
        }
    }

    function renderUndoButtons() {
        if (undoBtn) {
            undoBtn.disabled = undoStack.length === 0;
            undoBtn.title = undoStack.length
                ? `撤销：${undoStack[undoStack.length - 1].label}（Ctrl+Z）` : '没有可撤销的操作';
        }
        if (redoBtn) {
            redoBtn.disabled = redoStack.length === 0;
            redoBtn.title = redoStack.length
                ? `重做：${redoStack[redoStack.length - 1].label}（Ctrl+Shift+Z）` : '没有可重做的操作';
        }
    }

    function undoAction() {
        return undoStack.length ? { label: '撤销', onClick: () => performUndo() } : null;
    }

    function pushUndoStep(step) {
        if (!step || !Array.isArray(step.ops) || step.ops.length === 0) return;
        undoStack.push(step);
        while (undoStack.length > MAX_UNDO_STEPS) undoStack.shift();
        redoStack = [];
        persistUndoStack();
        renderUndoButtons();
    }

    async function callApi(path, method, body) {
        const options = { method: method || 'POST' };
        if (body !== undefined && body !== null) {
            options.headers = { 'Content-Type': 'application/json' };
            options.body = JSON.stringify(body);
        }
        const response = await apiFetch(path, options);
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.error || '操作失败');
        return payload;
    }

    // 完成任务后的生成回流：按 taskRefs 生成复习项，AI 只做补充。
    // 纯增强：任何失败都只 warn，绝不打断勾选/保存或弹错误提示刷屏。
    async function maybeGenerateReviewItems(project, node) {
        if (!project || !node) return;
        try {
            const payload = await callApi('/api/review/generate', 'POST', {
                taskId: node.id, projectId: project.id, taskText: node.text || '', count: 3,
            });
            const created = (payload.created || []).length;
            if (created > 0) showToast(`已生成 ${created} 个复习知识点`);
        } catch (error) {
            console.warn('生成复习知识点失败', error);
        }
    }

    // ---------- 节点级保存（第六批 item 2）：把"改 1 个节点"从整棵树重写降到 1 行 ----------

    // 只有当这个项目"和服务端数据一致"时才走 patch：否则本地还有别的改动没落库，
    // 用 patch 会和待写的整棵树打架，不如老老实实全量保存。
    //
    // 判据是"内存数据指纹 == 已保存基线"，而不是 dirtyProjectIds ——
    // 因为改一个节点本身就会把项目标脏，用 dirty 判断会导致永远走不到 patch。
    // 指纹会忽略 expanded 之类纯视图态字段（见 projectStateJson）。
    // 因此**必须在改动节点之前**调用（调用点都注意了这一点）。
    function canUseNodePatch(project) {
        if (!project || !Array.isArray(project.tree)) return false;
        if (saveTimer || inFlightSaves > 0 || inFlightPatches > 0 || saveConflict) return false;
        const baseline = savedProjectJsonById.get(String(project.id));
        if (typeof baseline !== 'string') return false;
        try {
            return baseline === projectStateJson(serializeProject(project));
        } catch (error) {
            return false;
        }
    }

    async function applyNodePatch(project, ops) {
        // 和整项目保存排在同一条队列里：否则两者会同时读同一个 revision，
        // 后到的那个被服务端 409 拒绝（真实浏览器测试抓到过 patch 与全量保存并发）。
        const run = saveQueue.catch(() => undefined).then(() => {
            inFlightPatches += 1;
            armLeaveGuard();
            return callApi('/api/node/patch', 'POST', {
                projectId: project.id,
                expectedRevision: Number(project._revision) || 0,
                ops,
            }).finally(() => {
                inFlightPatches -= 1;
                if (!savePending()) disarmLeaveGuard();
            });
        });
        saveQueue = run.catch(() => undefined);
        const payload = await run;
        project._revision = Number(payload.revision) || project._revision;
        if (payload.summary && payload.summary.stats) project.stats = payload.summary.stats;
        // 服务和内存现在一致：刷新"已保存"基线，免得下一次全量保存又整棵树重写
        if (Array.isArray(project.tree)) {
            rememberProjectBaseline(project);
        } else {
            forgetProjectBaseline(project.id);
        }
        dirtyProjectIds.delete(String(project.id));
        return payload;
    }

    async function saveNodeChange(project, ops, fallback) {
        if (project) {
            try {
                return await applyNodePatch(project, ops);
            } catch (error) {
                console.warn('节点级保存失败，回退为整项目保存', error);
                if (error && error.status === 409) {
                    showToast('其他页面刚改过这个项目，已改为整项目保存',
                        { label: '解决冲突', onClick: () => openConflictPanel() });
                }
            }
        }
        if (typeof fallback === 'function') fallback();
        return null;
    }

    // 单个节点的字段集合（完成态 + 验收 + 复习），供 patch 复用
    function nodeStateFields(node) {
        return {
            completed: Boolean(node.completed),
            completedAt: node.completedAt || null,
            assessment: node.assessment || null,
            assessmentHistory: Number(node.assessmentHistory) || 0,
            review: node.review || null,
        };
    }

    // 任务元数据字段（与 storage.PATCH_NODE_FIELDS 对齐）
    function nodeMetaFields(node) {
        return {
            priority: node.priority || '',
            dueDate: node.dueDate || '',
            estimateMinutes: Number(node.estimateMinutes) || 0,
            tags: Array.isArray(node.tags) ? node.tags : [],
            note: node.note || '',
            links: Array.isArray(node.links) ? node.links : [],
            repeat: node.repeat || null,
        };
    }

    // 单节点改动落库：能 patch 就 patch，否则整项目保存。
    // patchSafe 必须在**改动之前**算好（见 canUseNodePatch 注释），所以由调用方传进来。
    function persistNodeFields(project, node, fields, patchSafe) {
        if (!node) return null;
        const owner = project || owningProjectOfNode(node);
        markProjectDirty(owner);
        if (patchSafe && owner) {
            saveNodeChange(owner, [{ op: 'update', nodeId: node.id, fields }], () => saveProjects());
        } else {
            saveProjects();
        }
        return owner;
    }

    function findNodeParentIdIn(project, nodeId) {
        const walk = (nodes, parent) => {
            for (const entry of nodes || []) {
                if (String(entry.id) === String(nodeId)) return parent ? String(parent.id) : null;
                const found = walk(entry.children || [], entry);
                if (found !== undefined && found !== null) return found;
            }
            return null;
        };
        return walk(project.tree || [], null);
    }

    async function restoreTrashItemById(trashId) {
        if (!trashId) throw new Error('这条记录没有可恢复的回收站条目');
        await callApi('/api/trash', 'POST', { action: 'restore', id: trashId });
    }

    async function duplicateNodeRemote(projectId, nodeId, options = {}) {
        const payload = await callApi('/api/node/duplicate', 'POST', {
            projectId, nodeId,
            includeChildren: options.includeChildren !== false,
            keepCompletion: Boolean(options.keepCompletion),
            keepAssessment: Boolean(options.keepAssessment),
            keepReview: Boolean(options.keepReview),
        });
        return payload.node;
    }

    async function runStepOps(step, direction) {
        for (const op of step.ops) {
            if (op.kind === 'http') {
                if (direction === 'undo' && op.undoBody) {
                    await callApi(op.path, op.method || 'POST', op.undoBody);
                } else if (direction === 'redo' && op.redoBody) {
                    await callApi(op.path, op.method || 'POST', op.redoBody);
                } else if (direction === 'undo' && op.undoOnly) {
                    await callApi(op.undoOnly.path, op.undoOnly.method || 'POST', op.undoOnly.body);
                } else {
                    await callApi(op.path, op.method || 'POST', op.body);
                }
            } else if (op.kind === 'node-delete') {
                if (direction === 'undo') {
                    await restoreTrashItemById(step.trashId);
                } else {
                    const saved = await deleteNodeToTrash(op.projectId, op.nodeId);
                    step.trashId = saved && saved.id;
                }
            } else if (op.kind === 'project-delete') {
                if (direction === 'undo') {
                    await restoreTrashItemById(step.trashId);
                } else {
                    const entry = projects.find(item => String(item.id) === String(op.projectId));
                    const revision = entry ? Number(entry._revision) || 0 : 0;
                    const payload = await callApi(
                        `/api/project?id=${encodeURIComponent(op.projectId)}&revision=${encodeURIComponent(revision)}`,
                        'DELETE');
                    step.trashId = payload.trashId || '';
                }
            } else if (op.kind === 'node-duplicate') {
                if (direction === 'undo') {
                    if (step.createdNodeId) await deleteNodeToTrash(op.projectId, step.createdNodeId);
                } else {
                    const created = await duplicateNodeRemote(op.projectId, op.nodeId, op.options || {});
                    step.createdNodeId = created && created.id;
                }
            } else if (op.kind === 'restore-backup') {
                if (direction === 'undo') {
                    await callApi('/api/backup', 'POST', { action: 'restore', name: op.name });
                }
            } else if (op.kind === 'node-fields') {
                // 批量修改的逆操作：把记录下来的节点内容写回去（纯前端内存 + 保存）
                await restoreNodeFields(op.projectId, direction === 'undo' ? op.before : op.after);
            }
        }
    }

    async function restoreNodeFields(projectId, entries) {
        const project = await ensureProjectLoaded(projectId);
        for (const entry of entries || []) {
            const node = findNodeById(project.tree || [], entry.id);
            if (!node) continue;
            for (const [key, value] of Object.entries(entry.fields)) {
                if (value === null) delete node[key];
                else node[key] = cloneData(value);
            }
        }
        markProjectDirty(project);
        await saveProjects();
    }

    async function refreshAfterHistoryChange(step) {
        try {
            await saveProjects();
        } catch (error) {
            console.warn('撤销后保存失败', error);
        }
        const projectId = (step.ops.find(op => op.projectId) || {}).projectId;
        if (projectId && projects.some(entry => String(entry.id) === String(projectId))) {
            try {
                await reloadProjectFromServer(projectId);
            } catch (error) {
                console.warn('撤销后重载项目失败', error);
            }
        }
        renderProjects();
        if (currentProjectId) renderDetail();
        if (workbenchView.classList.contains('active')) showWorkbench();
        loadReviewCounts();
    }

    async function performUndo() {
        if (historyBusy) return;
        const step = undoStack.pop();
        if (!step) {
            showToast('没有可撤销的操作');
            return;
        }
        historyBusy = true;
        try {
            await runStepOps(step, 'undo');
        } catch (error) {
            undoStack.push(step);
            renderUndoButtons();
            showToast(`撤销失败：${error.message || '未知错误'}`);
            historyBusy = false;
            return;
        }
        redoStack.push(step);
        persistUndoStack();
        renderUndoButtons();
        await refreshAfterHistoryChange(step);
        historyBusy = false;
        showToast(`已撤销：${step.label}`, redoStack.length ? { label: '重做', onClick: () => performRedo() } : null);
    }

    async function performRedo() {
        if (historyBusy) return;
        const step = redoStack.pop();
        if (!step) {
            showToast('没有可重做的操作');
            return;
        }
        historyBusy = true;
        try {
            await runStepOps(step, 'redo');
        } catch (error) {
            redoStack.push(step);
            renderUndoButtons();
            showToast(`重做失败：${error.message || '未知错误'}`);
            historyBusy = false;
            return;
        }
        undoStack.push(step);
        persistUndoStack();
        renderUndoButtons();
        await refreshAfterHistoryChange(step);
        historyBusy = false;
        showToast(`已重做：${step.label}`, undoAction());
    }

    // ---------- 项目模板 / 设置 / 活动历史 ----------

    let templatesCache = [];

    function countTemplateItems(tree) {
        let count = 0;
        const walk = (nodes) => {
            (nodes || []).forEach(node => {
                if (node.type === 'item') count += 1;
                walk(node.children);
            });
        };
        walk(tree);
        return count;
    }

    async function loadTemplates() {
        try {
            const response = await apiFetch('/api/templates', { cache: 'no-store' });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '读取模板失败');
            templatesCache = payload.templates || [];
        } catch (error) {
            templatesCache = [];
            console.warn('读取模板失败', error);
        }
        renderTemplateOptions();
        renderTemplateList();
    }

    function renderTemplateOptions() {
        if (!templateSelect) return;
        const previous = templateSelect.value;
        templateSelect.replaceChildren();
        const blank = document.createElement('option');
        blank.value = '';
        blank.textContent = '从模板创建…';
        templateSelect.appendChild(blank);
        templatesCache.forEach(entry => {
            const option = document.createElement('option');
            option.value = entry.id;
            option.textContent = entry.name + (entry.builtin ? '（内置）' : '');
            templateSelect.appendChild(option);
        });
        templateSelect.value = templatesCache.some(entry => entry.id === previous) ? previous : '';
    }

    function renderTemplateList() {
        if (!templateList) return;
        templateList.replaceChildren();
        if (templatesCache.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'utility-empty';
            empty.textContent = '还没有模板：可以在项目详情页点「存为模板」。';
            templateList.appendChild(empty);
            return;
        }
        templatesCache.forEach(entry => {
            const row = document.createElement('div');
            row.className = 'template-row';
            const info = document.createElement('div');
            info.className = 'template-info';
            const name = document.createElement('strong');
            name.textContent = entry.name + (entry.builtin ? '（内置）' : '');
            const desc = document.createElement('small');
            desc.textContent = (entry.description || '没有说明') + ` · ${countTemplateItems(entry.tree)} 个任务`;
            info.append(name, desc);
            const use = document.createElement('button');
            use.type = 'button';
            use.className = 'utility-secondary-btn';
            use.textContent = '用它建项目';
            use.addEventListener('click', () => createProjectFromTemplate(entry.id));
            row.append(info, use);
            if (!entry.builtin) {
                const remove = document.createElement('button');
                remove.type = 'button';
                remove.className = 'utility-secondary-btn template-delete';
                remove.textContent = '删除';
                remove.addEventListener('click', async () => {
                    if (!window.confirm(`删除模板「${entry.name}」？`)) return;
                    try {
                        await callApi(`/api/templates?id=${encodeURIComponent(entry.id)}`, 'DELETE');
                        await loadTemplates();
                        showToast('已删除模板');
                    } catch (error) {
                        showToast(error.message || '删除模板失败');
                    }
                });
                row.appendChild(remove);
            }
            templateList.appendChild(row);
        });
    }

    async function createProjectFromTemplate(templateId, name) {
        try {
            const response = await apiFetch('/api/project/from-template', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ templateId, name }),
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '用模板创建项目失败');
            await loadProjects();
            renderProjects();
            await openProjectDetail(payload.project.id);
            showToast(`已用模板创建项目：${payload.project.name}`);
        } catch (error) {
            showToast(error.message || '用模板创建项目失败');
        }
    }

    async function saveCurrentProjectAsTemplate() {
        const project = getCurrentProject();
        if (!project) return;
        const name = window.prompt('模板名称（只保存结构，不带完成状态与 AI 历史）：',
            `${project.name} 模板`);
        if (name === null) return;
        try {
            await callApi('/api/templates', 'POST',
                { projectId: project.id, name: name.slice(0, 60), description: project.description || '' });
            await loadTemplates();
            showToast('已存为模板（可在“更多工具 → 项目模板”里使用）');
        } catch (error) {
            showToast(error.message || '存为模板失败');
        }
    }

    async function duplicateCurrentProject() {
        const project = getCurrentProject();
        if (!project) return;
        const options = await openOptionDialog(`复制项目：${project.name}`,
            '复制出来的是一个新项目（ID 全新），原项目不受影响。',
            [
                { key: 'keepCompletion', label: '保留完成状态', checked: true },
                { key: 'keepAssessment', label: '保留 AI 验收历史', checked: true },
                { key: 'keepReview', label: '保留复习安排', checked: true },
            ], '复制项目');
        if (!options) return;
        try {
            const response = await apiFetch('/api/project/duplicate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ projectId: project.id, name: `${project.name}（副本）`, ...options }),
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '复制项目失败');
            await loadProjects();
            renderProjects();
            showToast(`已复制项目：${payload.project.name}`);
        } catch (error) {
            showToast(error.message || '复制项目失败');
        }
    }

    async function loadSettings() {
        try {
            const response = await apiFetch('/api/settings', { cache: 'no-store' });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '读取设置失败');
            const settings = payload.settings || {};
            trashRetentionInput.value = String(settings.trashRetentionDays || 7);
            // 显式 0 是合法设置（关闭每日新知识点），不能用 || 兜底
            const reviewLimitValue = settings.reviewDailyLimit;
            reviewDailyLimitInput.value = String(reviewLimitValue === undefined || reviewLimitValue === null ? 10 : reviewLimitValue);
            const reviewNewValue = settings.reviewNewPerDay;
            reviewNewPerDayInput.value = String(reviewNewValue === undefined || reviewNewValue === null ? 2 : reviewNewValue);
            autoArchiveDaysInput.value = String(settings.autoArchiveDays || 30);
            autoArchiveToggle.checked = Boolean(settings.autoArchiveEnabled);
            settingsStatus.textContent = `回收站保留 ${settings.trashRetentionDays} 天；`
                + `自动归档${settings.autoArchiveEnabled ? '已开启' : '未开启'}`
                + `（超过 ${settings.autoArchiveDays} 天没动且全部完成的项目会被归档；收集箱永不归档）。`;
        } catch (error) {
            settingsStatus.textContent = `读取设置失败：${error.message || ''}`;
        }
    }

    async function saveSettingsFromUi() {
        try {
            await callApi('/api/settings', 'POST', {
                settings: {
                    trashRetentionDays: Number(trashRetentionInput.value),
                    reviewDailyLimit: Number(reviewDailyLimitInput.value) || 10,
                    reviewNewPerDay: Number(reviewNewPerDayInput.value) || 0,
                    autoArchiveDays: Number(autoArchiveDaysInput.value),
                    autoArchiveEnabled: autoArchiveToggle.checked,
                },
            });
            await loadSettings();
            showToast('设置已保存');
        } catch (error) {
            showToast(error.message || '保存设置失败');
        }
    }

    async function runAutoArchiveFromUi() {
        try {
            const response = await apiFetch('/api/archive/auto', { method: 'POST' });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '自动归档失败');
            await loadProjects();
            renderProjects();
            const count = (payload.archived || []).length;
            showToast(count ? `已归档 ${count} 个已完成项目` : '没有需要归档的项目');
        } catch (error) {
            showToast(error.message || '自动归档失败');
        }
    }

    async function loadActivity() {
        if (!activityList) return;
        try {
            const response = await apiFetch('/api/activity?limit=50', { cache: 'no-store' });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '读取活动历史失败');
            renderActivity(payload.entries || []);
        } catch (error) {
            activityList.replaceChildren();
            const failed = document.createElement('p');
            failed.className = 'utility-empty';
            failed.textContent = `读取活动历史失败：${error.message || ''}`;
            activityList.appendChild(failed);
        }
    }

    function renderActivity(entries) {
        activityList.replaceChildren();
        if (entries.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'utility-empty';
            empty.textContent = '还没有活动记录。';
            activityList.appendChild(empty);
            return;
        }
        entries.forEach(entry => {
            const row = document.createElement('div');
            row.className = 'activity-row';
            const time = document.createElement('span');
            time.className = 'activity-time';
            time.textContent = String(entry.at || '').replace('T', ' ').slice(5, 16);
            const text = document.createElement('span');
            text.className = 'activity-text';
            text.textContent = `${entry.summary}${entry.projectName ? ' · ' + entry.projectName : ''}`;
            row.append(time, text);
            if (entry.undoable) {
                const tag = document.createElement('span');
                tag.className = 'activity-tag';
                tag.textContent = '可撤销';
                row.appendChild(tag);
            }
            activityList.appendChild(row);
        });
    }

    async function clearActivityFromUi() {
        if (!window.confirm('清空活动历史？（只清记录，不影响项目数据）')) return;
        try {
            await callApi('/api/activity', 'DELETE');
            await loadActivity();
            showToast('已清空活动历史');
        } catch (error) {
            showToast(error.message || '清空失败');
        }
    }

    function handleHistoryShortcut(event) {
        const target = event.target;
        const tag = target && target.tagName ? String(target.tagName).toLowerCase() : '';
        if (target && (target.isContentEditable || tag === 'input' || tag === 'textarea' || tag === 'select')) return;
        if (!event.ctrlKey && !event.metaKey) return;
        const key = String(event.key || '').toLowerCase();
        if (key === 'z' && event.shiftKey) {
            event.preventDefault();
            performRedo();
        } else if (key === 'z') {
            event.preventDefault();
            performUndo();
        } else if (key === 'y') {
            event.preventDefault();
            performRedo();
        }
    }

    // ---------- 拖拽排序 / 跨周跨单元移动 ----------

    function clearDropHints() {
        document.querySelectorAll('#detailView .drop-before, #detailView .drop-after, #detailView .drop-inside')
            .forEach(el => el.classList.remove('drop-before', 'drop-after', 'drop-inside'));
    }

    function dropTargetFor(row, event, node) {
        const box = row.getBoundingClientRect();
        const offset = (event.clientY - box.top) / Math.max(1, box.height);
        const isContainer = node.type !== 'item';
        if (isContainer && offset > 0.3 && offset < 0.7) return { mode: 'inside', node };
        return { mode: offset < 0.5 ? 'before' : 'after', node };
    }

    async function reorderNodeRemote(projectId, nodeId, parentId, position) {
        const payload = await callApi('/api/node/reorder', 'POST', { projectId, nodeId, parentId, position });
        return payload.move;
    }


    function findNodeParentId(nodes, targetId, parentId = null) {
        for (const node of nodes || []) {
            if (String(node.id) === String(targetId)) return parentId;
            const found = findNodeParentId(node.children || [], targetId, node.id);
            if (found !== null) return found;
        }
        return null;
    }

    function attachDragHandlers(li, row, node) {
        row.draggable = true;
        row.addEventListener('dragstart', (event) => {
            const project = getCurrentProject();
            if (!project) return;
            dragState = { nodeId: node.id, projectId: project.id };
            event.dataTransfer.effectAllowed = 'move';
            try { event.dataTransfer.setData('text/plain', String(node.id)); } catch (error) { /* 老浏览器忽略 */ }
            li.classList.add('dragging');
        });
        row.addEventListener('dragend', () => {
            dragState = null;
            li.classList.remove('dragging');
            clearDropHints();
        });
        row.addEventListener('dragover', (event) => {
            if (!dragState || String(dragState.nodeId) === String(node.id)) return;
            event.preventDefault();
            event.dataTransfer.dropEffect = 'move';
            clearDropHints();
            const target = dropTargetFor(row, event, node);
            row.classList.add(target.mode === 'inside' ? 'drop-inside'
                : target.mode === 'before' ? 'drop-before' : 'drop-after');
        });
        row.addEventListener('dragleave', () => row.classList.remove('drop-before', 'drop-after', 'drop-inside'));
        row.addEventListener('drop', async (event) => {
            event.preventDefault();
            event.stopPropagation();
            const target = dropTargetFor(row, event, node);
            clearDropHints();
            await applyDrop(target);
        });
    }

    async function applyDrop(target) {
        const project = getCurrentProject();
        if (!project || !dragState || !target) return;
        const tree = project.tree || [];
        const sourceParent = findNodeParentId(tree, dragState.nodeId);
        const sourceList = findParentList(tree, dragState.nodeId) || [];
        const sourcePosition = sourceList.findIndex(entry => String(entry.id) === String(dragState.nodeId));
        let parentId = null;
        let position = 0;
        if (target.mode === 'inside') {
            parentId = target.node.id;
            position = (target.node.children || []).length;
        } else {
            parentId = findNodeParentId(tree, target.node.id);
            const siblings = findParentList(tree, target.node.id) || [];
            const index = siblings.findIndex(entry => String(entry.id) === String(target.node.id));
            position = target.mode === 'before' ? index : index + 1;
            // 同一个父节点内往下挪时，摘掉自己之后下标会前移一位
            if (String(parentId) === String(sourceParent) && sourcePosition >= 0 && sourcePosition < position) {
                position -= 1;
            }
        }
        if (String(parentId) === String(sourceParent) && sourcePosition === position) return;
        try {
            const move = await reorderNodeRemote(project.id, dragState.nodeId, parentId, position);
            pushUndoStep({
                label: '移动任务',
                ops: [{ kind: 'http', path: '/api/node/reorder', method: 'POST',
                        body: { projectId: project.id, nodeId: dragState.nodeId, parentId, position },
                        undoBody: { projectId: project.id, nodeId: dragState.nodeId,
                                    parentId: move.previous.parentId, position: move.previous.position } }],
            });
            await refreshAfterHistoryChange({ ops: [{ projectId: project.id }] });
            showToast('已移动', undoAction());
        } catch (error) {
            showToast(error.message || '移动失败，请重试');
        }
    }

    // ---------- 复制 / 移动 对话框 ----------

    async function duplicateNodeWithOptions(node) {
        const project = getCurrentProject();
        if (!project) return;
        const result = await openOptionDialog('复制：' + (node.text || ''),
            '复制出来的是独立副本（ID 全新），默认不带走完成状态、AI 历史与复习安排。',
            [
                { key: 'includeChildren', label: '包含子任务 / 整枝', checked: node.type !== 'item' },
                { key: 'keepCompletion', label: '保留完成状态', checked: false },
                { key: 'keepAssessment', label: '保留 AI 验收历史', checked: false },
                { key: 'keepReview', label: '保留复习安排', checked: false },
            ], '复制');
        if (!result) return;
        try {
            await verifyDeleteImpact(project.id, node.id);   // 提前把当前项目加载进内存
            const created = await duplicateNodeRemote(project.id, node.id, result);
            pushUndoStep({ label: `复制「${node.text || '未命名'}」`,
                           ops: [{ kind: 'node-duplicate', projectId: project.id, nodeId: node.id, options: result }],
                           createdNodeId: created.id });
            await refreshAfterHistoryChange({ ops: [{ projectId: project.id }] });
            showToast(`已复制：${created.text || node.text}`, undoAction());
        } catch (error) {
            showToast(error.message || '复制失败，请重试');
        }
    }

    async function openMoveNodeDialog(node) {
        const project = getCurrentProject();
        if (!project) return;
        showUtilityModal('移动到…', '可以移动到其他周 / 学习单元，也可以换项目');
        utilityBody.innerHTML = '';
        const form = document.createElement('div');
        form.className = 'meta-form';
        const hint = document.createElement('p');
        hint.className = 'utility-hint';
        hint.textContent = '任务：' + (node.text || '未命名');
        form.appendChild(hint);
        const projectSelect = document.createElement('select');
        summariesCache().forEach(entry => {
            const option = document.createElement('option');
            option.value = entry.id;
            option.textContent = entry.name;
            projectSelect.appendChild(option);
        });
        projectSelect.value = project.id;
        addMetaField(form, '目标项目', projectSelect);
        const parentSelect = document.createElement('select');
        addMetaField(form, '放到哪一周 / 单元', parentSelect);
        const positionInput = document.createElement('input');
        positionInput.type = 'number';
        positionInput.min = '0';
        positionInput.placeholder = '留空=放到最后';
        addMetaField(form, '位置（从 0 开始，可留空）', positionInput);
        const loadParents = async () => {
            parentSelect.replaceChildren();
            const rootOption = document.createElement('option');
            rootOption.value = '';
            rootOption.textContent = '（项目顶层）';
            parentSelect.appendChild(rootOption);
            try {
                const target = await ensureProjectLoaded(projectSelect.value);
                flattenParentOptions(target).forEach(entry => {
                    if (entry.id === null || String(entry.id) === String(node.id)) return;
                    const option = document.createElement('option');
                    option.value = String(entry.id);
                    option.textContent = entry.label;
                    parentSelect.appendChild(option);
                });
            } catch (error) {
                showToast(error.message || '读取目标项目失败');
            }
        };
        projectSelect.addEventListener('change', loadParents);
        await loadParents();
        const actions = document.createElement('div');
        actions.className = 'utility-actions';
        const confirm = document.createElement('button');
        confirm.type = 'button';
        confirm.className = 'utility-primary-btn';
        confirm.textContent = '移动';
        confirm.addEventListener('click', async () => {
            const toProjectId = projectSelect.value;
            const parentId = parentSelect.value || null;
            const position = positionInput.value === '' ? null : Number(positionInput.value);
            const sameProject = String(toProjectId) === String(project.id);
            try {
                if (sameProject) {
                    const move = await reorderNodeRemote(project.id, node.id, parentId,
                        position === null ? (findParentList(project.tree || [], parentId) || []).length : position);
                    pushUndoStep({ label: `移动「${node.text || '未命名'}」`,
                                   ops: [{ kind: 'http', path: '/api/node/reorder', method: 'POST',
                                           body: { projectId: project.id, nodeId: node.id, parentId, position: move.position },
                                           undoBody: { projectId: project.id, nodeId: node.id,
                                                       parentId: move.previous.parentId, position: move.previous.position } }] });
                } else {
                    const originalParent = findParentList(project.tree || [], node.id) ? null : null;
                    await callApi('/api/inbox/move', 'POST',
                        { nodeId: node.id, fromProjectId: project.id, toProjectId, parentId, position });
                    pushUndoStep({ label: `移动到其他项目`,
                                   ops: [{ kind: 'http', path: '/api/inbox/move', method: 'POST',
                                           body: { nodeId: node.id, fromProjectId: project.id, toProjectId, parentId, position },
                                           undoOnly: { path: '/api/inbox/move', method: 'POST',
                                                       body: { nodeId: node.id, fromProjectId: toProjectId,
                                                               toProjectId: project.id, parentId: originalParent, position: null } } }] });
                }
                closeUtilityModal();
                await loadProjects();
                if (currentProjectId) renderDetail();
                showToast('已移动', undoAction());
            } catch (error) {
                showToast(error.message || '移动失败，请重试');
            }
        });
        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'utility-secondary-btn';
        cancel.textContent = '取消';
        cancel.addEventListener('click', closeUtilityModal);
        actions.append(confirm, cancel);
        form.appendChild(actions);
        utilityBody.appendChild(form);
    }

    function summariesCache() {
        return projects.map(entry => ({ id: entry.id, name: entry.name }))
            .filter(entry => !entry.archived)
            .concat(projects.some(entry => entry.id === 'inbox') ? [] : [])
            .sort((left, right) => String(left.name).localeCompare(String(right.name), 'zh'));
    }

    async function verifyDeleteImpact(projectId, nodeId) {
        const response = await apiFetch(
            `/api/node/delete-impact?projectId=${encodeURIComponent(projectId)}&nodeId=${encodeURIComponent(nodeId)}`,
            { cache: 'no-store' });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.error || '读取删除影响面失败');
        return payload.impact;
    }

    function describeImpact(impact) {
        if (!impact) return '';
        const parts = [];
        if (impact.descendantCount > 0) parts.push(`包含 ${impact.descendantCount} 个子节点`);
        if (impact.itemCount > 0) parts.push(`共 ${impact.itemCount} 个任务`);
        if (impact.completedCount > 0) parts.push(`其中 ${impact.completedCount} 个已完成`);
        if (impact.estimateMinutes > 0) parts.push(`预计耗时合计 ${impact.estimateMinutes} 分钟`);
        return parts.length ? parts.join('，') : '没有子任务';
    }

    function renderDetail() {
        const project = getCurrentProject();
        if (!project) {
            // 没有"当前项目"时不要擅自切视图：工作台/复习队列里保存任务详情也会走到这里，
            // 切回项目列表等于把用户踢出当前视图。只有"当前项目已被删掉"才回列表。
            if (currentProjectId) {
                currentProjectId = null;
                showProjectsView();
            }
            return;
        }
        ensureProjectCaches(project);
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
        treeRoot.replaceChildren();
        if (!project.tree || project.tree.length === 0) {
            emptyTreeTip.textContent = '还没有内容，添加第一周开始吧';
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
        emptyTreeTip.textContent = '还没有内容，添加第一周开始吧';
        emptyTreeTip.classList.add('hidden');
        const projectCreatedAt = project.createdAt || '';
        const treeFragment = document.createDocumentFragment();
        visibleTree.forEach(week => {
            treeFragment.appendChild(renderNode(week, projectCreatedAt, filtering));
        });
        treeRoot.replaceChildren(treeFragment);
        const allExpanded = (project.tree || []).every(w => w.expanded);
        expandAllBtn.textContent = allExpanded ? '收起全部' : '展开全部';
        if (projectArchiveBtn) {
            const isInbox = String(project.id) === INBOX_PROJECT_ID;
            projectArchiveBtn.textContent = project.archived ? '取消归档' : '归档';
            projectArchiveBtn.classList.toggle('active', Boolean(project.archived));
            projectArchiveBtn.disabled = isInbox;
            projectArchiveBtn.title = isInbox ? '收集箱是快速添加的落点，不能归档' : '';
        }
        renderBatchToolbar();
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
        if (node.type === 'item') {
            const metaBadges = createNodeMetaBadges(node);
            if (metaBadges) row.appendChild(metaBadges);
        }
        const dateSpan = document.createElement('span');
        dateSpan.className = 'node-date';
        dateSpan.textContent = node.createdAt || projectCreatedAt;
        const actions = document.createElement('span');
        actions.className = 'node-actions';
        if (node.type === 'week' || node.type === 'day') {
            const addBtn = document.createElement('button');
            addBtn.className = 'add-btn';
            addBtn.textContent = '+';
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
            reviewBtn.textContent = '○';
            reviewBtn.title = '安排复习';
            reviewBtn.setAttribute('aria-label', '安排复习');
            reviewBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                openScheduleReview(node);
            });
            actions.appendChild(reviewBtn);
        }
        if (node.type === 'item') {
            const metaBtn = document.createElement('button');
            metaBtn.className = 'meta-btn';
            metaBtn.textContent = '⋯';
            metaBtn.title = '优先级 / 截止 / 标签 / 耗时 / 备注 / 链接';
            metaBtn.setAttribute('aria-label', metaBtn.title);
            metaBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                openNodeMeta(node);
            });
            actions.appendChild(metaBtn);
        }
        const editBtn = document.createElement('button');
        editBtn.className = 'edit-btn';
        editBtn.textContent = '✎';
        editBtn.title = '编辑';
        editBtn.setAttribute('aria-label', '编辑');
        editBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            startEditNode(node, textSpan, row);
        });
        actions.appendChild(editBtn);
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'delete-btn';
        deleteBtn.textContent = '✕';
        deleteBtn.title = '删除';
        deleteBtn.setAttribute('aria-label', '删除');
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteNode(node, row);
        });
        actions.appendChild(deleteBtn);
        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.textContent = '⧉';
        copyBtn.title = '复制这个节点（可选是否带走子任务 / 完成状态 / AI 历史 / 复习）';
        copyBtn.setAttribute('aria-label', copyBtn.title);
        copyBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            duplicateNodeWithOptions(node);
        });
        actions.appendChild(copyBtn);
        const moveBtn = document.createElement('button');
        moveBtn.className = 'move-btn';
        moveBtn.textContent = '⇄';
        moveBtn.title = '移动到其他周 / 学习单元 / 项目（也可以直接拖拽）';
        moveBtn.setAttribute('aria-label', moveBtn.title);
        moveBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            openMoveNodeDialog(node);
        });
        actions.appendChild(moveBtn);
        row.appendChild(arrow);
        row.appendChild(checkbox);
        row.appendChild(textSpan);
        if (optionalBadge) row.appendChild(optionalBadge);
        if (assessmentBadge) row.appendChild(assessmentBadge);
        if (node.type === 'item' && node.review && node.review.due) {
            if (node.review.learning) {
                const learningBadge = document.createElement('span');
                learningBadge.className = 'node-learning-badge';
                learningBadge.textContent = '需重学';
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
        if (batchState.active && node.type === 'item') {
            const key = batchKey(getCurrentProject() ? getCurrentProject().id : '', node.id);
            li.classList.add('batch-mode');
            if (batchState.selected.has(key)) li.classList.add('batch-selected');
        }
        li.appendChild(row);
        if (node.type !== 'item') {
            const childrenUl = document.createElement('ul');
            childrenUl.className = 'children';
            if (node.expanded || filtering) childrenUl.classList.add('expanded');
            const visibleChildren = filtering
                ? (node.children || []).filter(nodeHasVisibleMatch)
                : (node.children || []);
            if ((node.expanded || filtering) && visibleChildren.length > 0) {
                const childFragment = document.createDocumentFragment();
                visibleChildren.forEach(child => {
                    childFragment.appendChild(renderNode(child, projectCreatedAt, filtering));
                });
                childrenUl.appendChild(childFragment);
            }
            li.appendChild(childrenUl);
            row.addEventListener('click', (e) => {
                if (e.target.closest('.node-actions') || e.target.closest('.checkbox')) return;
                updateBranch(node, li);
            });
        } else {
            row.addEventListener('click', (e) => {
                if (e.target.closest('.node-actions')) return;
                if (batchState.active) {
                    e.stopPropagation();
                    toggleBatchSelection(node, li);
                    return;
                }
                if (e.target.closest('.checkbox')) return;
                toggleNodeCompleted(node);
            });
        }
        checkbox.addEventListener('click', (e) => {
            e.stopPropagation();
            if (batchState.active) {
                toggleBatchSelection(node, li);
                return;
            }
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
        attachDragHandlers(li, row, node);
        return li;
    }

    // ---------- 任务元数据：徽标 + 编辑弹窗（第 1~4、6 项） ----------

    function formatEstimate(minutes) {
        const value = Math.max(0, Number(minutes) || 0);
        if (value === 0) return '';
        if (value < 60) return `${value} 分`;
        const hours = value / 60;
        return Number.isInteger(hours) ? `${hours} 小时` : `${value} 分`;
    }

    function dueBadgeInfo(node) {
        if (!node.dueDate) return null;
        const today = todayStr();
        const days = daysBetween(today, node.dueDate);
        if (days === null) return null;
        if (days < 0) return { text: `逾期 ${-days} 天`, className: 'due-overdue' };
        if (days === 0) return { text: '今天到期', className: 'due-today' };
        if (days === 1) return { text: '明天到期', className: 'due-soon' };
        if (days <= 7) return { text: `${days} 天后到期`, className: 'due-soon' };
        return { text: node.dueDate.slice(5) + ' 到期', className: '' };
    }

    function createNodeMetaBadges(node) {
        const badges = [];
        if (node.priority) {
            const labels = { high: '高', mid: '中', low: '低' };
            badges.push({ text: labels[node.priority], className: `priority-badge priority-${node.priority}` });
        }
        const due = dueBadgeInfo(node);
        if (due) badges.push({ text: due.text, className: `due-badge ${due.className}` });
        (node.tags || []).slice(0, 2).forEach(tag => badges.push({ text: `#${tag}`, className: 'tag-badge' }));
        if ((node.tags || []).length > 2) badges.push({ text: `+${node.tags.length - 2}`, className: 'tag-badge' });
        const repeatText = describeRepeat(node.repeat);
        if (repeatText) badges.push({ text: `↻ ${repeatText}`, className: 'repeat-badge' });
        const estimate = formatEstimate(node.estimateMinutes);
        if (estimate) badges.push({ text: estimate, className: 'estimate-badge' });
        if (node.note) badges.push({ text: '备注', className: 'note-badge', title: node.note.slice(0, 200) });
        if ((node.links || []).length > 0) badges.push({ text: `链接 ${node.links.length}`, className: 'link-badge' });
        if (badges.length === 0) return null;
        const wrap = document.createElement('span');
        wrap.className = 'node-meta';
        wrap.title = '点击编辑优先级 / 截止 / 标签 / 耗时 / 备注 / 链接';
        badges.forEach(badge => {
            const span = document.createElement('span');
            span.className = `meta-badge ${badge.className}`.trim();
            span.textContent = badge.text;
            if (badge.title) span.title = badge.title;
            wrap.appendChild(span);
        });
        wrap.addEventListener('click', (event) => {
            event.stopPropagation();
            openNodeMeta(node);
        });
        return wrap;
    }

    // 任务详情弹窗对"当前项目"和"工作台/搜索结果里的项目"都要标脏：
    // 工作台/复习队列打开时 currentProjectId 为 null，只靠最后保存时的 JSON 差集兜底太脆弱。
    function owningProjectOfNode(node) {
        if (!node || node.id == null) return getCurrentProject();
        const current = getCurrentProject();
        if (current && Array.isArray(current.tree) && findNodeById(current.tree, node.id)) return current;
        return projects.find(project => Array.isArray(project.tree) && findNodeById(project.tree, node.id)) || current;
    }

    function applyNodeMeta(node, meta) {
        const cleaned = normalizeNodeMeta(meta);
        node.priority = cleaned.priority;
        node.dueDate = cleaned.dueDate;
        node.estimateMinutes = cleaned.estimateMinutes;
        node.tags = cleaned.tags;
        node.note = cleaned.note;
        node.links = cleaned.links;
        node.repeat = cleaned.repeat;
        markProjectDirty(owningProjectOfNode(node));
    }

    function openNodeMeta(node, options) {
        if (!node || node.type !== 'item') return;
        const draft = normalizeNodeMeta(node);
        showUtilityModal('任务详情', '优先级 · 截止 · 标签 · 耗时 · 备注 · 链接');
        utilityBody.innerHTML = '';
        const form = document.createElement('div');
        form.className = 'meta-form';
        const hint = document.createElement('p');
        hint.className = 'utility-hint';
        hint.textContent = '这些信息只用于筛选、工作台和提醒，不影响任务原有的完成/验收逻辑。';
        form.appendChild(hint);

        const addField = (label, control) => {
            const field = document.createElement('label');
            field.className = 'meta-field';
            const caption = document.createElement('span');
            caption.textContent = label;
            field.append(caption, control);
            form.appendChild(field);
            return field;
        };

        const prioritySelect = document.createElement('select');
        [['', '无'], ['high', '高'], ['mid', '中'], ['low', '低']].forEach(([value, text]) => {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = text;
            prioritySelect.appendChild(option);
        });
        prioritySelect.value = draft.priority;
        addField('优先级', prioritySelect);

        const dueInput = document.createElement('input');
        dueInput.type = 'date';
        dueInput.value = draft.dueDate;
        const dueField = addField('截止日期', dueInput);
        const dueShortcuts = document.createElement('div');
        dueShortcuts.className = 'meta-shortcuts';
        [['今天', 0], ['明天', 1], ['3 天后', 3], ['下周', 7], ['清除', null]].forEach(([text, offset]) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'utility-secondary-btn';
            button.textContent = text;
            button.addEventListener('click', () => {
                dueInput.value = offset === null ? '' : addDaysToIso(todayStr(), offset);
            });
            dueShortcuts.appendChild(button);
        });
        dueField.appendChild(dueShortcuts);

        const estimateInput = document.createElement('input');
        estimateInput.type = 'number';
        estimateInput.min = '0';
        estimateInput.max = String(MAX_ESTIMATE_MINUTES);
        estimateInput.step = '5';
        estimateInput.value = String(draft.estimateMinutes || '');
        estimateInput.placeholder = '分钟';
        const estimateField = addField('预计耗时（分钟）', estimateInput);
        const estimateShortcuts = document.createElement('div');
        estimateShortcuts.className = 'meta-shortcuts';
        [15, 30, 60, 120].forEach(minutes => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'utility-secondary-btn';
            button.textContent = formatEstimate(minutes);
            button.addEventListener('click', () => { estimateInput.value = String(minutes); });
            estimateShortcuts.appendChild(button);
        });
        estimateField.appendChild(estimateShortcuts);

        const repeatField = document.createElement('label');
        repeatField.className = 'meta-field';
        const repeatCaption = document.createElement('span');
        repeatCaption.textContent = '周期';
        const repeatSelect = document.createElement('select');
        [['', '不重复'], ['daily', '每天'], ['weekday', '每个工作日'], ['weekly', '每周'], ['monthly', '每月']]
            .forEach(([value, text]) => {
                const option = document.createElement('option');
                option.value = value;
                option.textContent = text;
                repeatSelect.appendChild(option);
            });
        repeatSelect.value = draft.repeat ? draft.repeat.freq : '';
        const intervalInput = document.createElement('input');
        intervalInput.type = 'number';
        intervalInput.min = '1';
        intervalInput.max = '365';
        intervalInput.value = String((draft.repeat && draft.repeat.interval) || 1);
        intervalInput.placeholder = '每几天';
        const repeatHint = document.createElement('span');
        repeatHint.className = 'utility-hint';
        const initialDueDate = dueInput.value;
        const repeatAnchorChanged = () => dueInput.value !== initialDueDate;
        const currentRepeatRule = () => buildRepeatRule(
            repeatSelect.value, dueInput.value, draft.repeat,
            { interval: intervalInput.value, anchorChanged: repeatAnchorChanged() }
        );
        const updateRepeatHint = () => {
            if (!repeatSelect.value) {
                repeatHint.textContent = '设为周期后，完成后会自动生成下一次';
                return;
            }
            const rule = currentRepeatRule();
            const base = dueInput.value || todayStr();
            const next = rule ? nextRepeatDue(rule, base) : '';
            repeatHint.textContent = next
                ? `下一次：${next}（${describeRepeat(rule)}）`
                : '按这个规则不会有下一次（已超过结束时间）';
        };
        repeatSelect.addEventListener('change', () => {
            intervalInput.hidden = repeatSelect.value !== 'daily';
            updateRepeatHint();
        });
        dueInput.addEventListener('change', updateRepeatHint);
        intervalInput.hidden = repeatSelect.value !== 'daily';
        intervalInput.addEventListener('input', updateRepeatHint);
        const repeatRow = document.createElement('div');
        repeatRow.className = 'meta-shortcuts';
        repeatRow.append(intervalInput, repeatHint);
        repeatField.append(repeatCaption, repeatSelect, repeatRow);
        updateRepeatHint();

        const tagsInput = document.createElement('input');
        tagsInput.type = 'text';
        tagsInput.value = draft.tags.join(', ');
        tagsInput.placeholder = '用逗号分隔，例如：Python, 复习';
        addField('标签', tagsInput);

        const noteInput = document.createElement('textarea');
        noteInput.rows = 4;
        noteInput.value = draft.note;
        noteInput.placeholder = '备注、思路、命令片段…';
        addField('备注', noteInput);

        const linksBox = document.createElement('div');
        linksBox.className = 'meta-links';
        const renderLinks = () => {
            linksBox.replaceChildren();
            draft.links.forEach((link, index) => {
                const rowBox = document.createElement('div');
                rowBox.className = 'meta-link-row';
                const labelInput = document.createElement('input');
                labelInput.type = 'text';
                labelInput.placeholder = '名称';
                labelInput.value = link.label;
                labelInput.addEventListener('input', () => { draft.links[index].label = labelInput.value; });
                const urlInput = document.createElement('input');
                urlInput.type = 'url';
                urlInput.placeholder = 'https://…';
                urlInput.value = link.url;
                urlInput.addEventListener('input', () => { draft.links[index].url = urlInput.value; });
                const remove = document.createElement('button');
                remove.type = 'button';
                remove.className = 'utility-secondary-btn';
                remove.textContent = '移除';
                remove.addEventListener('click', () => {
                    draft.links.splice(index, 1);
                    renderLinks();
                });
                rowBox.append(labelInput, urlInput, remove);
                linksBox.appendChild(rowBox);
            });
            const add = document.createElement('button');
            add.type = 'button';
            add.className = 'utility-secondary-btn';
            add.textContent = '添加链接';
            add.addEventListener('click', () => {
                if (draft.links.length >= MAX_LINKS) {
                    showToast(`最多 ${MAX_LINKS} 个链接`);
                    return;
                }
                draft.links.push({ label: '', url: '' });
                renderLinks();
            });
            linksBox.appendChild(add);
        };
        renderLinks();
        addField('资料链接', linksBox);

        const actions = document.createElement('div');
        actions.className = 'utility-actions';
        const save = document.createElement('button');
        save.type = 'button';
        save.className = 'utility-primary-btn';
        save.textContent = '保存';
        save.addEventListener('click', async () => {
            const tags = tagsInput.value.split(/[,，\s]+/).map(item => item.trim()).filter(Boolean);
            // 保留原规则的锚点（每周几 / 每月几号）和结束时间，只有改了截止日期才重算。
            const repeat = currentRepeatRule();
            const metaOwner = owningProjectOfNode(node);
            // 判定要在改动之前（见 canUseNodePatch）：否则一个节点的元数据改动也要整棵树重写
            const metaPatchSafe = canUseNodePatch(metaOwner);
            try {
                applyNodeMeta(node, {
                    priority: prioritySelect.value,
                    dueDate: dueInput.value,
                    estimateMinutes: estimateInput.value,
                    tags,
                    note: noteInput.value,
                    links: draft.links.filter(link => String(link.url || '').trim()),
                    repeat,
                });
            } catch (error) {
                showToast(error.message || '链接格式不正确');
                return;
            }
            persistNodeFields(metaOwner, node, nodeMetaFields(node), metaPatchSafe);
            // 只在真正处于某个项目的详情页时重画详情；工作台里打开这个弹窗时
            // renderDetail() 会把视图切回项目列表（退不出工作台的同类 bug）。
            if (getCurrentProject()) renderDetail();
            closeUtilityModal();
            showToast('已保存任务信息');
            const refreshAfterSave = options && options.onSaved;
            if (typeof refreshAfterSave === 'function') {
                try {
                    await settleSaves();   // patch 或整项目保存都算落库
                } catch (error) {
                    // 保存失败/冲突由保存管线提示，这里不刷新，改动仍留在内存里。
                    return;
                }
                refreshAfterSave();
            }
        });
        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'utility-secondary-btn';
        cancel.textContent = '取消';
        cancel.addEventListener('click', closeUtilityModal);
        actions.append(save, cancel);
        form.appendChild(actions);
        utilityBody.appendChild(form);
    }

    function toggleNodeCompleted(node) {
        // 先判断能不能走节点级 patch（此时还没改动，JSON 与基线可比）
        const patchSafe = canUseNodePatch(owningProjectOfNode(node));
        if (node.type === 'item') {
            if (node.assessmentRequired && !node.completed) {
                openAssessment(node);
                return;
            }
            const outcome = setNodeCompleted(node, !node.completed);
            if (node.assessmentRequired && !node.completed) {
                // Canceling a passed task invalidates both stages; it must be earned again.
                if (node.assessment && node.assessment.passed) {
                    node.assessmentHistory = (Number(node.assessmentHistory) || 0) + 1;
                }
                node.assessment = null;
            }
            const owner = outcome.project || owningProjectOfNode(node);
            markProjectDirty(owner);
            if (patchSafe && owner) {
                const ops = [{ op: 'update', nodeId: node.id, fields: nodeStateFields(node) }];
                if (outcome.spawned) {
                    ops.push({ op: 'append', parentId: findNodeParentIdIn(owner, node.id),
                               node: outcome.spawned });
                }
                saveNodeChange(owner, ops, () => saveProjects()).then(() => {
                    // patch 路径下服务端已完成，重绘一次让统计/父节点状态跟上
                    refreshAfterToggle(owner, node);
                    if (node.completed) maybeGenerateReviewItems(owner, node);
                });
            } else {
                saveProjects();
                refreshAfterToggle(owner, node);
                if (node.completed) maybeGenerateReviewItems(owner, node);
            }
            return;
        }
        if (subtreeRequiresAssessment(node)) {
            showToast('课程任务需逐项验收，不能批量完成');
            return;
        }
        toggleAllChildren(node, getNodeCompletionState(node) !== 'completed');
        // 分组完成会影响一整棵子树：改动多，直接整项目保存更稳妥
        markProjectDirty(owningProjectOfNode(node));
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
                markProjectDirty(owningProjectOfNode(node));
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
        input.placeholder = parentNode.type === 'week' ? '输入学习单元名称…' : '输入验收任务…';
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
                markProjectDirty(owningProjectOfNode(parentNode));
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

    async function deleteNodeToTrash(projectId, nodeId) {
        const project = await ensureProjectLoaded(projectId);
        const snapshot = snapshotNodeForTrash(project.tree || [], nodeId);
        if (!snapshot) throw new Error('节点已不存在');
        const saved = await storeTrashItem({
            kind: 'node',
            projectId,
            title: snapshot.node.text || '未命名任务',
            context: `${project.name || '未命名项目'} · ${snapshot.path || ''}`.trim(),
            parentId: snapshot.parentId,
            position: snapshot.position,
            revision: project._revision || 0,
            payload: snapshot.node,
        });
        // 删除也是"改一个节点"：能走 patch 就不整棵树重传（第六批 item 2）
        const patchSafe = canUseNodePatch(project);
        const removedContainers = [];
        removeNodeById(project.tree, nodeId);
        cleanupEmptyNodes(project.tree, removedContainers);
        if (patchSafe) {
            const ops = [{ op: 'delete', nodeId }];
            removedContainers.forEach(id => ops.push({ op: 'delete', nodeId: id }));
            await saveNodeChange(project, ops, () => {
                markProjectDirty(project);
                return saveProjects();
            });
        } else {
            markProjectDirty(project);
            await saveProjects();
        }
        return saved;
    }

    async function deleteNode(node, row) {
        const project = getCurrentProject();
        if (!project) return;
        if (String(node.id) === REMEDIAL_QUEUE_ID) {
            showToast('补漏队列是固定入口，不能删除；可以继续添加或删除其中的具体任务');
            return;
        }
        // 删除前先问一句"会影响多少东西"（可预览、可撤销）
        let impact = null;
        try {
            impact = await verifyDeleteImpact(project.id, node.id);
        } catch (error) {
            console.warn('读取删除影响面失败', error);
        }
        const detail = describeImpact(impact);
        if (!window.confirm(`确认删除「${node.text || '未命名'}」？\n${detail}\n\n会放进回收站，之后可以恢复（原位或孤立任务箱）。`)) return;
        let savedTrash = null;
        try {
            savedTrash = await deleteNodeToTrash(project.id, node.id);
        } catch (error) {
            showToast(error.message || '删除失败，请重试');
            return;
        }
        const trashId = savedTrash && savedTrash.id;
        pushUndoStep({
            label: `删除「${node.text || '未命名'}」`,
            ops: [{ kind: 'node-delete', projectId: project.id, nodeId: node.id }],
            trashId,
        });
        if (row) {
            row.classList.add('removing');
            setTimeout(() => { if (row.isConnected) row.classList.remove('removing'); }, 400);
        }
        renderDetail();
        showToast(`已删除：${node.text}`, undoAction());
    }

    async function clearCompletedInDetail() {
        const project = getCurrentProject();
        if (!project) return;
        const completedIds = collectCompletedItemIds(project.tree);
        if (completedIds.length === 0) return;
        if (!window.confirm(`确认清空 ${completedIds.length} 项已完成任务？清空前会自动生成一份完整快照，之后可以撤销。`)) return;
        const snapshotName = await createSnapshot('before-clear-completed');
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
        setTimeout(async () => {
            completedIds.forEach(id => removeNodeById(project.tree, id));
            cleanupEmptyNodes(project.tree);
            markProjectDirty(project);
            try {
                await saveProjects();
            } catch (error) {
                showToast(error.message || '清空后保存失败，请重试');
            }
            renderDetail();
            if (snapshotName) {
                // 撤销 = 恢复清空前的完整快照（最稳妥：连 AI 历史、复习安排一起回来）
                pushUndoStep({
                    label: `清空 ${completedIds.length} 项已完成`,
                    ops: [{ kind: 'restore-backup', name: snapshotName }],
                });
            }
            showToast(`已清空 ${completedIds.length} 项`, undoAction());
        }, totalDelay);
    }

    async function showProjectsView(options) {
        // 从详情页回到列表时会把项目对象换成"列表摘要"（tree: null）。
        // 所以没保存成功就绝不能走这一步，否则内存里那份改好的树会被摘要覆盖掉（=丢改动）。
        const force = Boolean(options && options.force === true);
        if (!force) {
            try {
                await settleSaves();
            } catch (error) {
                const conflict = Boolean(saveConflict || pendingConflict);
                showToast(
                    conflict ? '有未解决的版本冲突，请先解决冲突再返回' : '当前修改尚未保存，请先处理保存失败',
                    conflict
                        ? { label: '解决冲突', onClick: () => openConflictPanel() }
                        : { label: '放弃改动并返回', onClick: () => showProjectsView({ force: true }) }
                );
                return;
            }
        } else {
            // 用户明确选择"放弃这次没存进去的改动"，避免被永久困在详情页。
            if (currentProjectId) dirtyProjectIds.delete(String(currentProjectId));
            setSaveStatus('已保存');
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
            forgetProjectBaseline(current.id);
        }
        activateView(projectsView);
        currentProjectId = null;
        renderProjects();
        loadReviewCounts();
    }

    function showDetailView(projectId) {
        currentProjectId = projectId;
        activateView(detailView);
        renderDetail();
    }

    async function openProjectDetail(projectId) {
        if (batchState.active) setBatchMode(false);
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
                markProjectDirty(project);
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

    // 复习页状态（Task 11）：主体按知识点分组，任务级到期单独成组。
    // { summary, items, dueToday, overdue, upcoming, weak, newItems, wrong, mastered, taskDue, taskFuture }
    let reviewQueueState = {
        summary: null, items: [], dueToday: [], overdue: [], upcoming: [], weak: [], newItems: [],
        recentWrong: [], recentMastered: [], taskDue: [], taskFuture: []
    };

    // 把服务端聚合出来的复习条目转成渲染用的形状。
    // node 只带渲染需要的字段；真要改复习计划时再按需加载那一个项目（见 runQueueAction）。
    function reviewEntryToItem(entry) {
        return {
            projectId: entry.projectId,
            projectName: entry.projectName,
            ancestorIds: Array.isArray(entry.ancestorIds) ? entry.ancestorIds : [],
            path: entry.path || '',
            due: entry.due,
            learning: Boolean(entry.learning),
            node: {
                id: entry.nodeId,
                text: entry.text || '未命名任务',
                optional: false,
                review: { due: entry.due, learning: Boolean(entry.learning), log: [] }
            }
        };
    }

    // ---------- 第七批：复习会话（一次一题、先回忆后揭示、五档自评、草稿恢复） ----------
    // 硬不变量：参考答案与历史答案只在 revealReviewAnswer() 里渲染，
    // renderReviewQuestion() 绝不把答案写进 DOM —— 否则"先回忆"就失去意义。
    const GRADE_LABELS = { 1: '完全不会', 2: '看过但说不清', 3: '基本掌握', 4: '可以独立写代码', 5: '可以讲给别人听' };
    // 题型中文名：复习页的"最近答错/最近掌握"是作答记录，必须显示当时用的题型。
    const REVIEW_TYPE_LABELS = { concept: '概念题', predict: '代码预测题', debug: '错误排查题', code_task: '实际编程题' };
    let reviewSessionState = { sessionId: '', items: [], index: 0, startedAt: 0, gradeCounts: {}, revealed: false };
    let reviewDraftTimer = null;
    // 会话级恢复：本地存住"练到哪了"，刷新/退出后再点复习直接接着练，而不是又开一个新会话。
    const REVIEW_SESSION_KEY = 'todo_review_session';

    function reviewDraftKey(code, type) {
        // 草稿 key 不含 sessionId：会话 id 每次都变，含进去等于永远恢复不到。
        // 同一道题（同一题型）再次出现时，未提交的回忆内容要能接上。
        return `todo_review_draft:${code}:${type}`;
    }

    function saveReviewSession() {
        const state = reviewSessionState;
        if (!state.items.length || state.index >= state.items.length) return;
        try {
            localStorage.setItem(REVIEW_SESSION_KEY, JSON.stringify({
                sessionId: state.sessionId, items: state.items, index: state.index,
                startedAt: state.startedAt, gradeCounts: state.gradeCounts,
            }));
        } catch (error) { /* 隐私模式等忽略 */ }
    }

    function clearReviewSession() {
        try { localStorage.removeItem(REVIEW_SESSION_KEY); } catch (error) { /* 忽略 */ }
    }

    function restoreReviewSession() {
        let saved = null;
        try {
            saved = JSON.parse(localStorage.getItem(REVIEW_SESSION_KEY) || 'null');
        } catch (error) { saved = null; }
        if (!saved || !Array.isArray(saved.items) || saved.items.length === 0) return null;
        const index = Number(saved.index) || 0;
        // 已经练完的会话不再恢复（否则永远停在最后一题）。
        if (index >= saved.items.length) return null;
        reviewSessionState = {
            sessionId: String(saved.sessionId || ''), items: saved.items, index: index,
            startedAt: Number(saved.startedAt) || Date.now(),
            gradeCounts: saved.gradeCounts && typeof saved.gradeCounts === 'object' ? saved.gradeCounts : {},
            revealed: false,
        };
        return reviewSessionState;
    }

    // 草稿：切题/退出/提交前都存一次，刷新后还能接上自己的回忆内容。
    function saveReviewDraft() {
        const item = reviewSessionState.items[reviewSessionState.index];
        if (!item || !reviewAnswerInput) return;
        try {
            localStorage.setItem(reviewDraftKey(item.code, item.questionType), reviewAnswerInput.value || '');
        } catch (error) { /* 隐私模式等忽略 */ }
    }

    function restoreReviewDraft(item) {
        reviewAnswerInput.value = '';
        if (!item) return;
        try {
            reviewAnswerInput.value = localStorage.getItem(reviewDraftKey(item.code, item.questionType)) || '';
        } catch (error) { /* 忽略 */ }
    }

    // 用指定的一组题（队列里的一题，或整条今日队列）开一轮复习会话。
    async function startReviewSessionWithItems(items) {
        if (!Array.isArray(items) || items.length === 0) return;
        // 会话 id 失败不阻塞练习：离线也能一题一题过，只是统计不上报。
        let sessionId = '';
        try {
            const started = await callApi('/api/review/session', 'POST', { action: 'start', planned: items.length });
            sessionId = started.sessionId || '';
        } catch (error) { sessionId = ''; }
        reviewSessionState = { sessionId: sessionId, items: items.slice(), index: 0,
            startedAt: Date.now(), gradeCounts: {}, revealed: false };
        saveReviewSession();
        activateView(reviewSessionView);
        renderReviewQuestion();
    }

    async function startReviewSession() {
        // ① 优先接着上次没练完的会话：不重新取队列、也不开新会话。
        if (restoreReviewSession()) {
            activateView(reviewSessionView);
            renderReviewQuestion();
            return;
        }
        let payload;
        try {
            // 继承复习页当前题型/模块筛选（和复习页共用 reviewQueueQuery）：
            // 以前硬编码 ?today=，用户选了题型/模块再点"开始今日复习"会被静默忽略。
            const response = await apiFetch(`/api/review/queue?${reviewQueueQuery()}`, { cache: 'no-store' });
            payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '读取复习队列失败');
        } catch (error) {
            showToast(error.message || '读取复习队列失败，请重试');
            return;
        }
        const items = Array.isArray(payload.items) ? payload.items : [];
        if (items.length === 0) {
            showToast('今天没有要复习的知识点，去知识点库挑一个练也行');
            activateView(reviewView);
            return;
        }
        await startReviewSessionWithItems(items);
    }

    // 题面代码（predict 要预测的、debug 要排查的片段）必须随题渲染：
    // 只在 reveal 里返回的话，用户在"先回忆"阶段根本看不到要作答的代码。
    function reviewBodyBlock(code) {
        if (!code) return null;
        const block = document.createElement('pre');
        block.className = 'review-body-code';
        block.style.fontFamily = 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
        block.style.whiteSpace = 'pre';
        block.style.overflowX = 'auto';
        block.textContent = String(code);
        return block;
    }

    function renderReviewQuestion() {
        const item = reviewSessionState.items[reviewSessionState.index];
        if (!item) { finishReviewSession(); return; }
        reviewSessionState.revealed = false;
        reviewSessionSummary.hidden = true;
        reviewQuestionCard.hidden = false;
        reviewSessionProgress.textContent = `第 ${reviewSessionState.index + 1} / ${reviewSessionState.items.length} 题`;
        reviewQuestionMeta.textContent = `${item.title} · ${item.module || '未分类'} · ${item.minutes} 分钟 · ${item.reason === 'new' ? '新知识点' : '复习'}`;
        const promptBlock = document.createElement('div');
        promptBlock.textContent = item.prompt || '（这道题没有题面）';
        const bodyBlock = reviewBodyBlock(item.body);
        reviewQuestionPrompt.replaceChildren(...(bodyBlock ? [promptBlock, bodyBlock] : [promptBlock]));
        restoreReviewDraft(item);
        reviewAnswerPanel.hidden = true;
        reviewAnswerPanel.replaceChildren();
        reviewGradeButtons.hidden = true;
        reviewRevealBtn.disabled = false;
    }

    async function revealReviewAnswer() {
        const item = reviewSessionState.items[reviewSessionState.index];
        if (!item || reviewSessionState.revealed) return;
        reviewRevealBtn.disabled = true;
        saveReviewDraft();
        let data;
        try {
            data = await callApi('/api/review/reveal', 'POST', { code: item.code, type: item.questionType });
        } catch (error) {
            reviewRevealBtn.disabled = false;
            showToast(error.message || '读取答案失败，请重试');
            return;
        }
        reviewSessionState.revealed = true;
        const parts = [];
        // 题面代码再渲染一次（只在这里，且标题明确写"题面代码"）：
        // 揭示后的答案面板要能对照着看，但绝不能和"参考答案"混在一起。
        const revealedBody = reviewBodyBlock(data.code);
        if (revealedBody) {
            const bodyTitle = document.createElement('h4');
            bodyTitle.textContent = '题面代码';
            parts.push(bodyTitle, revealedBody);
        }
        const heading = document.createElement('h4');
        heading.textContent = '参考答案';
        parts.push(heading);
        const expected = Array.isArray(data.expected) ? data.expected : [];
        const answerLines = Array.isArray(data.answer) ? data.answer : [];
        [].concat(answerLines, expected).forEach(line => {
            const block = document.createElement('div');
            block.className = 'expected-answer';
            block.textContent = String(line);
            parts.push(block);
        });
        if (data.explain) {
            const explain = document.createElement('div');
            explain.textContent = `解释：${data.explain}`;
            parts.push(explain);
        }
        if (data.rootCause) {
            const cause = document.createElement('div');
            cause.textContent = `根因：${data.rootCause}（修法：${data.fix || ''}）`;
            parts.push(cause);
        }
        if (data.reference) {
            const reference = document.createElement('div');
            reference.textContent = `参考实现：${data.reference}`;
            parts.push(reference);
        }
        if (Array.isArray(data.pitfalls) && data.pitfalls.length > 0) {
            const pitfallTitle = document.createElement('h4');
            pitfallTitle.textContent = '易错点';
            parts.push(pitfallTitle);
            data.pitfalls.forEach(text => {
                const line = document.createElement('div');
                line.textContent = `· ${text}`;
                parts.push(line);
            });
        }
        const history = Array.isArray(data.history) ? data.history : [];
        if (history.length > 0) {
            const historyTitle = document.createElement('h4');
            historyTitle.textContent = '历史答案';
            parts.push(historyTitle);
            history.slice(0, 5).forEach(entry => {
                const line = document.createElement('div');
                line.textContent = `${entry.reviewedOn} · ${GRADE_LABELS[entry.grade] || entry.grade} · ${entry.answer || '（没写）'}`;
                parts.push(line);
            });
        }
        reviewAnswerPanel.replaceChildren(...parts);
        reviewAnswerPanel.hidden = false;
        reviewGradeButtons.hidden = false;
    }

    async function gradeReviewQuestion(grade) {
        const item = reviewSessionState.items[reviewSessionState.index];
        if (!item || !reviewSessionState.revealed) return;
        const answer = reviewAnswerInput.value || '';
        try {
            await callApi('/api/review/answer', 'POST', {
                code: item.code, type: item.questionType, grade: grade, answer: answer,
                durationMs: Date.now() - reviewSessionState.startedAt,
                sessionId: reviewSessionState.sessionId,
                taskId: item.taskId || '', projectId: item.projectId || '',
                today: todayStr(),
            });
        } catch (error) {
            // 保存失败就停在当前题：答案还留在输入框里，重选档位即可重试。
            showToast(error.message || '保存作答失败，答案还留在输入框里');
            return;
        }
        try { localStorage.removeItem(reviewDraftKey(item.code, item.questionType)); } catch (error) { /* 忽略 */ }
        // 作答会改变 due/weak（知识点库展示的正是这两个字段），缓存随之作废，下次进库重新拉。
        knowledgePoints = [];
        reviewSessionState.gradeCounts[grade] = (reviewSessionState.gradeCounts[grade] || 0) + 1;
        reviewSessionState.index += 1;
        // 进度落盘：刷新/换页回来还能接着练（最后一题评完就由 finishReviewSession 清掉）。
        saveReviewSession();
        if (reviewSessionState.index >= reviewSessionState.items.length) finishReviewSession();
        else renderReviewQuestion();
        loadReviewCounts();
    }

    async function finishReviewSession() {
        // 练完了就把会话进度清掉：下次点复习要重新取队列，而不是又回到这一轮。
        clearReviewSession();
        const counts = reviewSessionState.gradeCounts;
        const answered = Object.values(counts).reduce((sum, value) => sum + value, 0);
        try {
            await callApi('/api/review/session', 'POST', {
                action: 'finish', sessionId: reviewSessionState.sessionId, answered: answered,
                gradeCounts: counts, durationMs: Date.now() - reviewSessionState.startedAt,
            });
        } catch (error) { /* 总结照常展示 */ }
        reviewQuestionCard.hidden = true;
        reviewSessionSummary.hidden = false;
        const lines = ['本次复习完成'];
        lines.push(`共 ${answered} 题，用时 ${Math.round((Date.now() - reviewSessionState.startedAt) / 60000 * 10) / 10} 分钟`);
        Object.keys(GRADE_LABELS).forEach(grade => {
            const count = counts[grade] || 0;
            if (count) lines.push(`${GRADE_LABELS[grade]}：${count} 题`);
        });
        const summary = document.createElement('div');
        const title = document.createElement('h3');
        title.textContent = lines[0];
        summary.appendChild(title);
        lines.slice(1).forEach(line => {
            const block = document.createElement('div');
            block.textContent = line;
            summary.appendChild(block);
        });
        reviewSessionSummary.replaceChildren(summary);
    }

    // 复习页查询串：题型/模块真的作为查询参数传给后端（/api/review/queue 已支持）。
    function reviewQueueQuery() {
        const params = [`today=${encodeURIComponent(todayStr())}`];
        const type = (reviewTypeFilter && reviewTypeFilter.value) || '';
        const moduleName = (reviewModuleFilter && reviewModuleFilter.value) || '';
        if (type) params.push(`type=${encodeURIComponent(type)}`);
        if (moduleName) params.push(`module=${encodeURIComponent(moduleName)}`);
        return params.join('&');
    }

    // 顶部统计口径必须和下方列表一致：题型/模块筛选会真的收窄服务端队列，
    // 数字就改用筛后 items 派生；范围筛选只收窄分组、不改队列，数字仍是全量并明确标注。
    function reviewSublineText(summary, items) {
        const type = (reviewTypeFilter && reviewTypeFilter.value) || '';
        const moduleName = (reviewModuleFilter && reviewModuleFilter.value) || '';
        const scope = (reviewScopeFilter && reviewScopeFilter.value) || '';
        const narrowed = Boolean(type || moduleName);
        const countOf = reason => items.filter(item => item.reason === reason).length;
        const parts = [
            `今日必复 ${narrowed ? countOf('today') : Number(summary.dueToday || 0)}`,
            `逾期 ${narrowed ? countOf('overdue') : Number(summary.overdue || 0)}`,
            `薄弱 ${narrowed ? countOf('weak') : Number(summary.weak || 0)}`,
            `连续 ${summary.streakDays || 0} 天`,
        ];
        if (narrowed) parts.push('按题型/模块筛选后');
        if (scope) parts.push('范围筛选只收窄分组，数字为全量');
        return parts.join(' · ');
    }

    // 模块下拉的选项来自知识点库（/api/review/points），每次整体重建但保留当前选择。
    // 复习页与知识点库各有一个下拉、共用同一份数据，所以这里收一个 target 参数而不是写死。
    function populateModuleFilter(select, modules) {
        if (!select) return;
        const current = select.value || '';
        const all = document.createElement('option');
        all.value = '';
        all.textContent = '全部模块';
        const options = [all];
        modules.forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            options.push(option);
        });
        select.replaceChildren(...options);
        select.value = modules.includes(current) ? current : '';
    }

    async function showReviewQueue() {
        try {
            await settleSaves();
        } catch (error) {
            showToast('当前修改尚未保存，请先解决保存失败');
            return;
        }
        activateView(reviewView);
        reviewSubline.textContent = '';
        renderReviewMessage(listStatusText('review', 'loading'), false);
        const query = `today=${encodeURIComponent(todayStr())}`;
        const queueQuery = reviewQueueQuery();
        let summary = null;
        let queue = null;
        let taskPayload = null;
        let pointsPayload = null;
        try {
            // 任务级到期单独成组：数据仍来自旧的 /api/reviews（保留 review_due），
            // 与知识点队列 /api/review/queue 互不影响。
            const [summaryResponse, queueResponse, taskResponse, pointsResponse] = await Promise.all([
                apiFetch(`/api/review/summary?${query}`, { cache: 'no-store' }),
                apiFetch(`/api/review/queue?${queueQuery}`, { cache: 'no-store' }),
                apiFetch(`/api/reviews?${query}`, { cache: 'no-store' }),
                apiFetch('/api/review/points?limit=500', { cache: 'no-store' }),
            ]);
            summary = await summaryResponse.json().catch(() => ({}));
            queue = await queueResponse.json().catch(() => ({}));
            taskPayload = await taskResponse.json().catch(() => ({}));
            pointsPayload = await pointsResponse.json().catch(() => ({}));
            if (!summaryResponse.ok || !queueResponse.ok) {
                throw new Error(summary.error || queue.error || '读取复习队列失败');
            }
        } catch (error) {
            const message = listStatusText('review', 'failed', error && error.message);
            renderReviewMessage(message, true);
            showToast(message);
            return;
        }
        const items = Array.isArray(queue.items) ? queue.items : [];
        const points = Array.isArray(pointsPayload.points) ? pointsPayload.points : [];
        // 顺手存进共享缓存：进知识点库时复用这份数据，不再重复请求 /api/review/points。
        knowledgePoints = points;
        populateModuleFilter(reviewModuleFilter, knowledgeModuleNames());
        reviewQueueState = {
            summary: summary,
            items: items,
            dueToday: items.filter(item => item.reason === 'today'),
            overdue: items.filter(item => item.reason === 'overdue'),
            upcoming: items.filter(item => item.reason === 'upcoming'),
            weak: items.filter(item => item.reason === 'weak'),
            newItems: items.filter(item => item.reason === 'new'),
            // 最近答错/最近掌握是真实作答记录（summary.recentWrong/recentMastered，grade<=2 / >=4），
            // 不再用知识点库的 points.lastGrade 冒充：那是"知识点最新档位"，不是一次作答。
            recentWrong: Array.isArray(summary.recentWrong) ? summary.recentWrong : [],
            recentMastered: Array.isArray(summary.recentMastered) ? summary.recentMastered : [],
            taskDue: (Array.isArray(taskPayload.due) ? taskPayload.due : []).map(reviewEntryToItem),
            taskFuture: (Array.isArray(taskPayload.future) ? taskPayload.future : []).map(reviewEntryToItem),
        };
        reviewSubline.textContent = reviewSublineText(summary, items);
        renderReviewGroups();
        if (queue.truncated) {
            showToast(`复习条目较多，仅显示前 ${queue.limit} 条`);
        }
        loadReviewCounts();
    }

    // ---------- 第七批 Task 12：知识点库（按模块/层级筛选 + 立即练一次） ----------
    // points 里只有元数据（title/module/level/due/weak），题面与题型要按 code 单点取（见 practicePoint）。
    function knowledgeModuleNames() {
        return Array.from(new Set(knowledgePoints.map(point => point.module).filter(Boolean)));
    }

    // 知识点库与复习页共用 /api/review/points 的结果：复习页刚拉过就直接复用缓存，
    // 只有缓存为空（首次打开、或刚作答过导致缓存作废）才重新请求，避免重复拉同一份清单。
    async function showKnowledgeLibrary() {
        activateView(knowledgeView);
        if (knowledgePoints.length === 0) {
            try {
                const response = await apiFetch('/api/review/points?limit=500', { cache: 'no-store' });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(payload.error || '读取知识点库失败');
                knowledgePoints = Array.isArray(payload.points) ? payload.points : [];
            } catch (error) {
                showToast(error.message || '读取知识点库失败，请重试');
                knowledgePoints = [];
            }
        }
        populateModuleFilter(knowledgeModuleFilter, knowledgeModuleNames());
        renderKnowledgeList();
    }

    function renderKnowledgeList() {
        const query = (knowledgeSearch.value || '').trim().toLowerCase();
        const module = knowledgeModuleFilter.value || '';
        const level = knowledgeLevelFilter.value || '';
        const list = knowledgePoints.filter(point =>
            (!module || point.module === module) && (!level || point.level === level)
            && (!query || `${point.title} ${point.code}`.toLowerCase().includes(query)));
        // 用 replaceChildren 而不是 innerHTML = ''：真实 DOM 里两者等价，
        // 但 DOM 桩只实现了 replaceChildren，innerHTML 清不掉旧卡片，会让筛选断言失真。
        knowledgeList.replaceChildren();
        if (list.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'utility-empty';
            empty.textContent = '没有匹配的知识点';
            knowledgeList.appendChild(empty);
            return;
        }
        list.forEach(point => {
            const card = document.createElement('div');
            card.className = 'knowledge-item';
            const title = document.createElement('div');
            title.className = 'knowledge-title';
            title.textContent = `${point.title}（${point.minutes} 分钟）`;
            const meta = document.createElement('small');
            meta.textContent = `${point.module || '未分类'} · ${point.level} · ${point.weak ? '薄弱' : (point.due ? `下次 ${point.due}` : '还没学过')}`;
            const practice = document.createElement('button');
            practice.type = 'button';
            practice.className = 'utility-secondary-btn';
            practice.textContent = '立即练一次';
            practice.addEventListener('click', () => { practicePoint(point.code); });
            card.append(title, meta, practice);
            knowledgeList.appendChild(card);
        });
    }

    // 知识点库的「立即练一次」：只练选中的这一个知识点。
    // 会话状态与渲染全部复用复习会话那一套（startReviewSessionWithItems），不另造一套。
    async function practicePoint(code) {
        const point = knowledgePoints.find(entry => entry.code === code);
        if (!point) return;
        let item = null;
        // points 接口只有元数据、没有题面：用 queue 的 code 过滤精确拿这一题的题面。
        // newPerDay=1 是必要的：新知识点默认受"每日新增名额"限制，名额用完时单点练习
        // 会被配额丢掉 —— 点了"立即练一次"却没题可做。
        try {
            const response = await apiFetch(
                `/api/review/queue?today=${encodeURIComponent(todayStr())}&code=${encodeURIComponent(code)}&newPerDay=1`,
                { cache: 'no-store' });
            const payload = await response.json().catch(() => ({}));
            const items = Array.isArray(payload.items) ? payload.items : [];
            item = items.find(entry => entry.code === code) || null;
        } catch (error) { item = null; }
        if (!item) {
            // 取题失败/题库没配题面时用知识点元数据兜底，保证"立即练一次"仍能进会话。
            item = { code: point.code, title: point.title, minutes: point.minutes,
                module: point.module, level: point.level, questionType: '',
                prompt: '', body: '', reason: 'practice', due: point.due };
        }
        await startReviewSessionWithItems([item]);
    }

    // ---------- 批次 4：周期任务 / 自然语言快速添加 / 提醒 ----------

    const REPEAT_LABELS = { daily: '每天', weekday: '工作日', weekly: '每周', monthly: '每月' };
    const WEEKDAY_NAMES = ['日', '一', '二', '三', '四', '五', '六'];

    function cleanRepeat(value) {
        if (!value || typeof value !== 'object') return null;
        const freq = String(value.freq || '').trim().toLowerCase();
        if (!['daily', 'weekday', 'weekly', 'monthly'].includes(freq)) return null;
        const rule = { freq };
        if (freq === 'weekly') {
            const weekday = Number(value.weekday);
            if (!Number.isInteger(weekday) || weekday < 0 || weekday > 6) return null;
            rule.weekday = weekday;
        }
        if (freq === 'monthly') {
            const day = Number(value.day);
            if (!Number.isInteger(day) || day < 1 || day > 31) return null;
            rule.day = day;
        }
        if (freq === 'daily') {
            const interval = Number(value.interval);
            rule.interval = Number.isInteger(interval) && interval >= 1 ? Math.min(365, interval) : 1;
        }
        const until = String(value.until || '').slice(0, 10);
        if (/^\d{4}-\d{2}-\d{2}$/.test(until) && isValidIsoDate(until)) rule.until = until;
        return rule;
    }

    function describeRepeat(rule) {
        const cleaned = cleanRepeat(rule);
        if (!cleaned) return '';
        if (cleaned.freq === 'daily') return cleaned.interval > 1 ? `每 ${cleaned.interval} 天` : '每天';
        if (cleaned.freq === 'weekday') return '每个工作日';
        if (cleaned.freq === 'weekly') return `每周${WEEKDAY_NAMES[cleaned.weekday]}`;
        return `每月 ${cleaned.day} 日`;
    }

    // 表单（任务详情 / 快速添加预览）构造周期规则。
    // 关键点：weekly.weekday / monthly.day 是规则的锚点，不能每次保存都按当时选中的
    // 截止日期重算——那样"每周三"的任务只要截止日期不是周三就会在保存时被改成别的星期。
    // 只有用户改了基准日期（anchorChanged）或换了频率时，才按基准日期重新推算锚点。
    // weekday 用 JS getDay()：0=周日（与 storage.next_repeat_due 的约定一致）。
    function buildRepeatRule(freq, baseDate, previous, options) {
        const opts = options || {};
        const prev = cleanRepeat(previous) || null;
        if (!freq) return null;
        const until = prev && prev.until ? { until: prev.until } : {};
        if (freq === 'daily') {
            const interval = Number(opts.interval);
            const safe = Number.isInteger(interval) && interval >= 1 ? Math.min(365, interval) : 1;
            return { freq: 'daily', interval: safe, ...until };
        }
        if (freq === 'weekday') return { freq: 'weekday', ...until };
        const base = /^\d{4}-\d{2}-\d{2}$/.test(String(baseDate || '')) ? String(baseDate) : todayStr();
        const parsed = new Date(`${base}T00:00:00`);
        const valid = !Number.isNaN(parsed.getTime());
        const keep = !opts.anchorChanged && prev && prev.freq === freq;
        if (freq === 'weekly') {
            const weekday = keep && Number.isInteger(prev.weekday) ? prev.weekday : (valid ? parsed.getDay() : 1);
            return { freq: 'weekly', weekday, ...until };
        }
        if (freq === 'monthly') {
            const day = keep && Number.isInteger(prev.day) ? prev.day : (valid ? parsed.getDate() : 1);
            return { freq: 'monthly', day, ...until };
        }
        return null;
    }

    // 纯函数：按周期规则算下一次到期日（与服务端 storage.next_repeat_due 同规则）
    function nextRepeatDue(rule, fromDate) {
        const cleaned = cleanRepeat(rule);
        if (!cleaned) return '';
        const base = /^\d{4}-\d{2}-\d{2}$/.test(String(fromDate || '')) ? String(fromDate) : todayStr();
        const start = new Date(`${base}T00:00:00`);
        if (Number.isNaN(start.getTime())) return '';
        let candidate = null;
        if (cleaned.freq === 'daily') {
            candidate = new Date(start.getTime());
            candidate.setDate(candidate.getDate() + (cleaned.interval || 1));
        } else if (cleaned.freq === 'weekday') {
            candidate = new Date(start.getTime());
            do { candidate.setDate(candidate.getDate() + 1); } while (candidate.getDay() === 0 || candidate.getDay() === 6);
        } else if (cleaned.freq === 'weekly') {
            candidate = new Date(start.getTime());
            do { candidate.setDate(candidate.getDate() + 1); } while (candidate.getDay() !== cleaned.weekday);
        } else {
            const day = cleaned.day;
            for (let step = 1; step <= 24 && !candidate; step += 1) {
                const probe = new Date(start.getFullYear(), start.getMonth() + step, 1);
                const lastDay = new Date(probe.getFullYear(), probe.getMonth() + 1, 0).getDate();
                if (day <= lastDay) candidate = new Date(probe.getFullYear(), probe.getMonth(), day);
            }
        }
        if (!candidate) return '';
        const pad = value => String(value).padStart(2, '0');
        const iso = `${candidate.getFullYear()}-${pad(candidate.getMonth() + 1)}-${pad(candidate.getDate())}`;
        if (cleaned.until && iso > cleaned.until) return '';
        return iso;
    }

    // 纯函数：把"明天复习 Python 装饰器 #Python !高 30分钟 @某项目 每天"解析成草稿
    function parseQuickAdd(text, context) {
        const source = String(text || '').trim();
        const today = (context && context.today) || todayStr();
        const projects = (context && context.projects) || [];
        const matched = [];
        const warnings = [];
        const draft = {
            text: '', dueDate: '', priority: '', tags: [], estimateMinutes: 0,
            projectId: null, projectName: '', repeat: null, matched: [], warnings: [],
        };
        let rest = source;
        const eat = (pattern, handler) => {
            rest = rest.replace(pattern, (...args) => {
                const result = handler(...args);
                if (result === false) return args[0];
                matched.push(args[0]);
                return ' ';
            });
        };
        // 优先级：!高 / !中 / !低 / !! / !!! / !1 !2 !3
        eat(/!(高|中|低)/g, (all, level) => {
            draft.priority = level === '高' ? 'high' : level === '中' ? 'mid' : 'low';
        });
        eat(/!(1|2|3)(?=\s|$)/g, (all, level) => {
            draft.priority = ['high', 'mid', 'low'][Number(level) - 1];
        });
        eat(/(!{2,3})(?=\s|$)/g, all => {
            draft.priority = all.length === 2 ? 'high' : 'mid';
        });
        // 标签 #tag：只认"行首或空白/分隔符之后"的 #，并且标签本身不放标点，
        // 否则 "学习C#语言基础" 会被吃成标题"学习C"+标签"语言基础"。
        eat(/(^|[\s，。！？、；：,;:!?（()【】\[\]])#([A-Za-z0-9_\u4e00-\u9fa5-]{1,20})/g, (all, _lead, tag) => {
            const cleaned = String(tag).trim().slice(0, MAX_TAG_CHARS);
            if (cleaned && !draft.tags.includes(cleaned)) draft.tags.push(cleaned);
        });
        // 项目 @名称
        eat(/@([^\s#@!]+)/g, (all, name) => {
            const squeeze = value => String(value || '').toLowerCase().replace(/\s+/g, '');
            const needle = squeeze(name);
            const found = projects.find(entry => squeeze(entry.name) === needle)
                || projects.find(entry => squeeze(entry.name).includes(needle));
            if (!found) {
                warnings.push(`没找到项目“${name}”，已留在标题里`);
                return false;
            }
            draft.projectId = found.id;
            draft.projectName = found.name;
        });
        // 周期。多条规则同时出现时只保留最后匹配到的那一条，
        // 并且 matched 里也只留对应的那一条（否则"识别到"和实际写入会不一致）。
        let repeatMatchIndex = -1;
        const eatRepeat = (pattern, build) => {
            rest = rest.replace(pattern, (...args) => {
                const rule = cleanRepeat(build(...args));
                if (!rule) return args[0];
                if (repeatMatchIndex >= 0) matched.splice(repeatMatchIndex, 1);
                draft.repeat = rule;
                matched.push(args[0]);
                repeatMatchIndex = matched.length - 1;
                return ' ';
            });
        };
        eatRepeat(/每(个)?工作日/g, () => ({ freq: 'weekday' }));
        eatRepeat(/每(天|日)/g, () => (draft.repeat ? null : { freq: 'daily' }));
        eatRepeat(/每(周|星期|礼拜)([一二三四五六日天])/g, (all, _unit, dayName) => {
            const index = '一二三四五六日天'.indexOf(dayName);
            // 天 在下标 7，和 日 一样表示周日，不能只特判 6。
            return { freq: 'weekly', weekday: index >= 6 ? 0 : index + 1 };
        });
        eatRepeat(/每(个)?月(\d{1,2})[号日]/g, (all, _unit, day) => ({ freq: 'monthly', day: Number(day) }));
        // 耗时：30分钟 / 2小时 / 1.5h / 90m
        // 中文单位不能用词边界排除数字（"1小时2分钟"很常见），英文缩写必须排除紧跟的字母/数字
        // （否则 "1h2o" 会被吃成 1 小时、"3hours" 会剩下 "ours"）。
        eat(/(\d+(?:\.\d+)?)\s*小时/g, (all, value) => {
            draft.estimateMinutes = Math.round(Number(value) * 60);
            if (!draft.estimateMinutes) return false;
        });
        eat(/(\d+(?:\.\d+)?)\s*[hH](?![\w\u4e00-\u9fa5])/g, (all, value) => {
            draft.estimateMinutes = Math.round(Number(value) * 60);
            if (!draft.estimateMinutes) return false;
        });
        eat(/(\d+)\s*(分钟|分(?![\u4e00-\u9fa5]))/g, (all, value) => {
            draft.estimateMinutes = Number(value);
        });
        eat(/(\d+)\s*[mM](?![\w\u4e00-\u9fa5])/g, (all, value) => {
            draft.estimateMinutes = Number(value);
        });
        // 日期
        eat(/(\d{4})-(\d{1,2})-(\d{1,2})/g, (all, year, month, day) => {
            const iso = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            if (!isValidIsoDate(iso)) return false;
            draft.dueDate = iso;
        });
        eat(/(\d{1,2})月(\d{1,2})[日号]/g, (all, month, day) => {
            const now = new Date(`${today}T00:00:00`);
            let candidate = `${now.getFullYear()}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            if (!isValidIsoDate(candidate)) return false;
            if (candidate < today) candidate = `${now.getFullYear() + 1}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            draft.dueDate = candidate;
        });
        // 日期。1-2 这种要前面是行首/空白/分隔符才算日期，
        // 否则 "第1-2章的习题"、"买3-5个苹果" 会被吃成日期加标题残渣。
        eat(/(^|[\s，。！？、；：,;:!?（()【】\[\]])(\d{1,2})-(\d{1,2})(?!\d)/g, (all, _lead, month, day) => {
            const now = new Date(`${today}T00:00:00`);
            let candidate = `${now.getFullYear()}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            if (!isValidIsoDate(candidate)) return false;
            if (candidate < today) candidate = `${now.getFullYear() + 1}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            draft.dueDate = candidate;
        });
        eat(/(\d+)\s*天(后|之后)/g, (all, days) => {
            draft.dueDate = addDaysToIso(today, Number(days));
        });
        eat(/大后天/g, () => { draft.dueDate = addDaysToIso(today, 3); });
        eat(/后天/g, () => { draft.dueDate = addDaysToIso(today, 2); });
        eat(/(明天|明日)/g, () => { draft.dueDate = addDaysToIso(today, 1); });
        eat(/(今天|今日)/g, () => { draft.dueDate = today; });
        // 周X / 下周X / 本周X
        eat(/(下|本|这)?(周|星期|礼拜)([一二三四五六日天])/g, (all, prefix, _unit, dayName) => {
            const index = '一二三四五六日天'.indexOf(dayName);
            const target = index >= 6 ? 0 : index + 1;   // "天" 在下标 7，和 "日" 一样是周日
            const baseDate = new Date(`${today}T00:00:00`);
            const currentAdj = baseDate.getDay() === 0 ? 7 : baseDate.getDay();   // 周一=1 … 周日=7
            const targetAdj = target === 0 ? 7 : target;
            // 下周X = 下一个 ISO 周的 X；本周X/周X = 今天或之后最近的 X
            const delta = prefix === '下'
                ? (7 - currentAdj) + targetAdj
                : ((targetAdj - currentAdj) + 7) % 7;
            draft.dueDate = addDaysToIso(today, delta);
        });
        draft.text = rest.replace(/\s+/g, ' ').trim();
        draft.matched = matched;
        draft.warnings = warnings;
        return draft;
    }

    function findParentList(nodes, targetId, parent = null) {
        for (const node of nodes || []) {
            if (String(node.id) === String(targetId)) return parent || nodes;
            const found = findParentList(node.children || [], targetId, node.children || []);
            if (found) return found;
        }
        return null;
    }

    function spawnNextOccurrence(project, node) {
        const rule = cleanRepeat(node.repeat);
        if (!rule) return null;
        const nextDue = nextRepeatDue(rule, node.dueDate || todayStr());
        if (!nextDue) return null;
        const siblings = findParentList(project.tree || [], node.id);
        if (!siblings) return null;
        const clone = cloneData(node);
        clone.id = generateId();
        clone.completed = false;
        clone.completedAt = null;
        clone.dueDate = nextDue;
        clone.assessment = null;
        clone.assessmentHistory = 0;
        delete clone.review;
        clone.children = [];
        siblings.push(clone);
        return clone;
    }

    // ---------- 批次 3：归档 / 筛选视图 / 批量编辑 ----------

    function batchKey(projectId, nodeId) {
        return `${projectId}::${nodeId}`;
    }

    function toggleBatchSelection(node, li) {
        const project = getCurrentProject();
        if (!project) return;
        const key = batchKey(project.id, node.id);
        if (batchState.selected.has(key)) {
            batchState.selected.delete(key);
            li.classList.remove('batch-selected');
        } else {
            batchState.selected.add(key);
            li.classList.add('batch-selected');
        }
        renderBatchToolbar();
    }

    function setBatchMode(active) {
        batchState.active = Boolean(active);
        if (!batchState.active) batchState.selected.clear();
        batchToggleBtn.textContent = batchState.active ? '退出批量' : '批量选择';
        batchToggleBtn.classList.toggle('active', batchState.active);
        renderDetail();
    }

    function renderBatchToolbar() {
        const toolbar = document.getElementById('batchToolbar');
        if (!toolbar) return;
        if (!batchState.active) {
            toolbar.hidden = true;
            toolbar.replaceChildren();
            return;
        }
        toolbar.hidden = false;
        toolbar.replaceChildren();
        const count = document.createElement('span');
        count.className = 'batch-count';
        count.textContent = `已选 ${batchState.selected.size} 项`;
        toolbar.appendChild(count);
        const addButton = (label, handler, className = 'utility-secondary-btn') => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = className;
            button.textContent = label;
            button.addEventListener('click', handler);
            toolbar.appendChild(button);
            return button;
        };
        if (batchState.selected.size === 0) {
            const hint = document.createElement('span');
            hint.className = 'utility-hint';
            hint.textContent = '点任务行选中；可一次设置优先级 / 标签 / 截止 / 完成 / 移动';
            toolbar.appendChild(hint);
            return;
        }
        addButton('高', () => runBatch('set-priority', 'high'), 'utility-secondary-btn batch-quick');
        addButton('中', () => runBatch('set-priority', 'mid'), 'utility-secondary-btn batch-quick');
        addButton('低', () => runBatch('set-priority', 'low'), 'utility-secondary-btn batch-quick');
        addButton('清除优先级', () => runBatch('set-priority', ''));
        addButton('加标签…', () => {
            const input = window.prompt('要添加的标签（逗号分隔）：');
            if (input === null) return;
            runBatch('add-tags', input.split(/[,，\s]+/).filter(Boolean));
        });
        addButton('移标签…', () => {
            const input = window.prompt('要移除的标签（逗号分隔）：');
            if (input === null) return;
            runBatch('remove-tags', input.split(/[,，\s]+/).filter(Boolean));
        });
        addButton('设截止…', () => {
            const input = window.prompt('截止日期（YYYY-MM-DD，留空=清除）：', todayStr());
            if (input === null) return;
            const value = input.trim();
            // 非空但格式不对不能当成"清除"：那会把所有选中任务的截止日期静默抹掉。
            if (value && !isValidIsoDate(value)) {
                showToast('日期格式不对，请用 YYYY-MM-DD（要清除截止日期请留空）');
                return;
            }
            runBatch('set-due', value);
        });
        addButton('延期 +1 天', () => runBatch('shift-due', 1));
        addButton('延期 +7 天', () => runBatch('shift-due', 7));
        addButton('标为完成', () => {
            if (!window.confirm(`确认把选中的 ${batchState.selected.size} 项标为完成？（需要 AI 验收的任务会被跳过）`)) return;
            runBatch('complete', null);
        }, 'utility-primary-btn');
        addButton('取消完成', () => {
            if (!window.confirm(`确认取消选中 ${batchState.selected.size} 项的完成状态？`)) return;
            runBatch('uncomplete', null);
        });
        addButton('移动到项目…', openBatchMovePicker);
        addButton('清除选择', () => {
            batchState.selected.clear();
            renderDetail();
        });
    }

    function selectedTargets() {
        return [...batchState.selected].map(key => {
            const [projectId, nodeId] = key.split('::');
            return { projectId, nodeId };
        });
    }

    async function reloadProjectFromServer(projectId) {
        const payload = await readStoredProject(projectId);
        const project = normalizeProjects([payload.project])[0];
        if (!project) return null;
        project._revision = Math.max(0, Number(payload.revision) || 0);
        const index = projects.findIndex(item => String(item.id) === String(projectId));
        if (index >= 0) {
            project.stats = projects[index].stats;
            projects[index] = project;
        }
        // 批量操作改的是服务端数据，统计缓存必须失效，
        // 否则"主线剩余 N 项"和父节点完成态会停在旧值（要重进项目才对）。
        refreshProjectCaches(project);
        rememberProjectBaseline(project);
        dirtyProjectIds.delete(String(projectId));
        return project;
    }

    const BATCH_FIELD_KEYS = ['priority', 'dueDate', 'estimateMinutes', 'tags', 'note', 'links', 'repeat', 'completed', 'completedAt', 'review'];

    function captureBatchFields(targets) {
        const captured = [];
        for (const target of targets) {
            const project = projects.find(entry => String(entry.id) === String(target.projectId));
            if (!project || !Array.isArray(project.tree)) continue;
            const node = findNodeById(project.tree, target.nodeId);
            if (!node) continue;
            const fields = {};
            BATCH_FIELD_KEYS.forEach(key => { fields[key] = key in node ? cloneData(node[key]) : null; });
            captured.push({ projectId: String(target.projectId), id: node.id, fields });
        }
        return captured;
    }

    async function runBatch(action, value) {
        const targets = selectedTargets();
        if (targets.length === 0) return;
        const projectId = getCurrentProject() ? getCurrentProject().id : null;
        const beforeFields = captureBatchFields(targets);
        const batchLabel = (document.querySelector(`#batchToolbar [data-batch-action="${action}"]`) || {}).textContent;
        try {
            const response = await apiFetch('/api/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action, targets, value })
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '批量修改失败，请重试');
            if (Array.isArray(payload.projects)) {
                for (const summary of payload.projects) {
                    const index = projects.findIndex(item => String(item.id) === String(summary.id));
                    if (index >= 0) projects[index].stats = summary.stats;
                }
            }
            const failed = payload.failed || [];
            const changed = Number(payload.changed) || 0;
            batchState.selected.clear();
            if (projectId) await reloadProjectFromServer(projectId);
            renderDetail();
            renderBatchToolbar();
            // 记下"改完是什么样"，撤销时把字段写回去（可逆、可重做）
            const afterFields = captureBatchFields(targets);
            if (changed > 0 && beforeFields.length > 0) {
                const grouped = new Map();
                const collect = (entries, key) => {
                    entries.forEach(entry => {
                        if (!grouped.has(entry.projectId)) grouped.set(entry.projectId, { before: [], after: [] });
                        grouped.get(entry.projectId)[key].push({ id: entry.id, fields: entry.fields });
                    });
                };
                collect(beforeFields, 'before');
                collect(afterFields, 'after');
                const ops = [];
                grouped.forEach((lists, projectKey) => {
                    ops.push({ kind: 'node-fields', projectId: projectKey,
                               before: lists.before, after: lists.after });
                });
                pushUndoStep({ label: `批量${batchLabel ? batchLabel : action}`, ops });
            }
            if (failed.length > 0) {
                showToast(`已修改 ${changed} 项，${failed.length} 项被跳过：${failed[0].error}`, undoAction());
            } else {
                showToast(`已修改 ${changed} 项`, undoAction());
            }
        } catch (error) {
            showToast(error.message || '批量修改失败，请重试');
        }
    }

    async function openBatchMovePicker() {
        const targets = selectedTargets();
        if (targets.length === 0) return;
        const current = getCurrentProject();
        if (!current) return;
        showUtilityModal('批量移动', '移动到其他项目');
        renderUtilityMessage('正在读取项目…');
        let summaries = [];
        try {
            const response = await apiFetch('/api/projects', { cache: 'no-store' });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '读取项目失败，请重试');
            summaries = (payload.projects || []).filter(entry => String(entry.id) !== String(current.id) && !entry.archived);
        } catch (error) {
            renderUtilityMessage(error.message || '读取项目失败，请重试');
            return;
        }
        if (summaries.length === 0) {
            renderUtilityMessage('没有其他可移动到的项目');
            return;
        }
        utilityBody.innerHTML = '';
        const form = document.createElement('div');
        form.className = 'meta-form';
        const hint = document.createElement('p');
        hint.className = 'utility-hint';
        hint.textContent = `把选中的 ${targets.length} 项移动到：`;
        form.appendChild(hint);
        const projectSelect = document.createElement('select');
        summaries.forEach(entry => {
            const option = document.createElement('option');
            option.value = entry.id;
            option.textContent = entry.name;
            projectSelect.appendChild(option);
        });
        const parentSelect = document.createElement('select');
        const projectField = document.createElement('label');
        projectField.className = 'meta-field';
        const projectCaption = document.createElement('span');
        projectCaption.textContent = '目标项目';
        projectField.append(projectCaption, projectSelect);
        const parentField = document.createElement('label');
        parentField.className = 'meta-field';
        const parentCaption = document.createElement('span');
        parentCaption.textContent = '放到哪一周 / 单元';
        parentField.append(parentCaption, parentSelect);
        form.append(projectField, parentField);
        const loadParents = async () => {
            parentSelect.replaceChildren();
            try {
                const project = await ensureProjectLoaded(projectSelect.value);
                parentSelect.replaceChildren();
                flattenParentOptions(project).forEach(entry => {
                    const option = document.createElement('option');
                    option.value = entry.id === null ? '' : String(entry.id);
                    option.textContent = entry.label;
                    parentSelect.appendChild(option);
                });
            } catch (error) {
                parentSelect.replaceChildren();
                const failed = document.createElement('option');
                failed.textContent = '读取失败，请重试';
                parentSelect.appendChild(failed);
            }
        };
        projectSelect.addEventListener('change', loadParents);
        await loadParents();
        const actions = document.createElement('div');
        actions.className = 'utility-actions';
        const confirm = document.createElement('button');
        confirm.type = 'button';
        confirm.className = 'utility-primary-btn';
        confirm.textContent = '确认移动';
        confirm.addEventListener('click', async () => {
            confirm.disabled = true;
            const toProjectId = projectSelect.value;
            const parentId = parentSelect.value || null;
            let moved = 0;
            const failures = [];
            for (const target of targets) {
                try {
                    const response = await apiFetch('/api/inbox/move', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ nodeId: target.nodeId, fromProjectId: target.projectId,
                                               toProjectId, parentId })
                    });
                    const payload = await response.json().catch(() => ({}));
                    if (!response.ok) throw new Error(payload.error || '移动失败');
                    moved += 1;
                } catch (error) {
                    failures.push(error.message || '移动失败');
                }
            }
            batchState.selected.clear();
            if (failures.length === 0) {
                closeUtilityModal();
                showToast(`已移动 ${moved} 项`);
            } else {
                showToast(`已移动 ${moved} 项，${failures.length} 项失败：${failures[0]}`);
            }
            try {
                const response = await apiFetch('/api/projects', { cache: 'no-store' });
                const payload = await response.json().catch(() => ({}));
                if (Array.isArray(payload.projects)) projects = payload.projects.map(normalizeProjectSummary);
            } catch (error) {
                console.error('刷新项目列表失败', error);
            }
            savedProjectJsonById.clear();
            if (moved > 0 && failures.length === 0) {
                renderProjects();
                await showProjectsView();
            } else {
                await reloadProjectFromServer(current.id);
                renderDetail();
                renderBatchToolbar();
            }
        });
        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'utility-secondary-btn';
        cancel.textContent = '取消';
        cancel.addEventListener('click', closeUtilityModal);
        actions.append(confirm, cancel);
        form.appendChild(actions);
        utilityBody.appendChild(form);
    }

    async function toggleProjectArchived(projectId) {
        if (String(projectId) === INBOX_PROJECT_ID) {
            // 收集箱是快速添加的落点，归档后工作台里看不到它，任务会像丢了一样。
            showToast('收集箱是快速添加的落点，不能归档');
            return;
        }
        try {
            const project = await ensureProjectLoaded(projectId);
            project.archived = !project.archived;
            markProjectDirty(project);
            await saveProjects();
            renderProjects();
            if (currentProjectId && String(currentProjectId) === String(projectId)) {
                projectArchiveBtn.textContent = project.archived ? '取消归档' : '归档';
                projectArchiveBtn.classList.toggle('active', project.archived);
            }
            showToast(project.archived ? '已归档，默认列表不再显示（可用状态筛选查看）' : '已取消归档');
        } catch (error) {
            showToast(error.message || '归档失败，请重试');
        }
    }

    async function loadSavedViews() {
        try {
            const response = await apiFetch('/api/views', { cache: 'no-store' });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '读取筛选视图失败');
            savedViews = payload.views || [];
            savedViewsError = '';
        } catch (error) {
            savedViews = [];
            savedViewsError = (error && error.message) || '读取筛选视图失败';
            console.warn('读取筛选视图失败', error);
        }
        renderViewChips();
    }

    function renderViewChips() {
        if (!viewChips) return;
        viewChips.replaceChildren();
        if (savedViewsError) {
            const failed = document.createElement('span');
            failed.className = 'view-empty';
            failed.textContent = `读取筛选视图失败：${savedViewsError}`;
            viewChips.appendChild(failed);
            viewChips.appendChild(createRetryButton('重试', () => loadSavedViews()));
            return;
        }
        if (savedViews.length === 0) {
            const empty = document.createElement('span');
            empty.className = 'view-empty';
            empty.textContent = '还没有保存的视图：设置好筛选后点右侧保存';
            viewChips.appendChild(empty);
            return;
        }
        const fragment = document.createDocumentFragment();
        savedViews.forEach(view => {
            const chip = document.createElement('span');
            chip.className = 'view-chip';
            const apply = document.createElement('button');
            apply.type = 'button';
            apply.className = 'view-chip-apply';
            apply.textContent = view.name;
            apply.title = '应用这个筛选视图';
            apply.addEventListener('click', () => applySavedView(view));
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'view-chip-remove';
            remove.textContent = '×';
            remove.title = `删除视图 ${view.name}`;
            remove.addEventListener('click', async (event) => {
                event.stopPropagation();
                if (!window.confirm(`确认删除筛选视图“${view.name}”？`)) return;
                try {
                    const response = await apiFetch(`/api/views?id=${encodeURIComponent(view.id)}`, { method: 'DELETE' });
                    const payload = await response.json().catch(() => ({}));
                    if (!response.ok) throw new Error(payload.error || '删除失败');
                    savedViews = payload.views || [];
                    renderViewChips();
                    showToast('已删除视图');
                } catch (error) {
                    showToast(error.message || '删除视图失败，请重试');
                }
            });
            chip.append(apply, remove);
            fragment.appendChild(chip);
        });
        viewChips.appendChild(fragment);
    }

    function currentFilterSnapshot() {
        return {
            projectFilters: { query: projectFilters.query, status: projectFilters.status },
            nodeFilters: {
                query: nodeFilters.query, status: nodeFilters.status,
                priority: nodeFilters.priority, due: nodeFilters.due, tag: nodeFilters.tag,
            },
        };
    }

    async function saveCurrentView() {
        const suggested = projectFilters.query || nodeFilters.query || nodeFilters.tag || '我的筛选';
        const name = window.prompt('给这个筛选视图起个名字：', suggested);
        if (name === null || !name.trim()) return;
        try {
            const response = await apiFetch('/api/views', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name.trim(), payload: currentFilterSnapshot() })
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '保存视图失败');
            savedViews = payload.views || [];
            renderViewChips();
            showToast('已保存筛选视图');
        } catch (error) {
            showToast(error.message || '保存视图失败，请重试');
        }
    }

    function applySavedView(view) {
        const payload = view.payload || {};
        const projectPart = payload.projectFilters || {};
        const nodePart = payload.nodeFilters || {};
        projectFilters.query = String(projectPart.query || '');
        projectFilters.status = String(projectPart.status || 'all');
        nodeFilters.query = String(nodePart.query || '');
        nodeFilters.status = String(nodePart.status || 'all');
        nodeFilters.priority = String(nodePart.priority || 'all');
        nodeFilters.due = String(nodePart.due || 'all');
        nodeFilters.tag = String(nodePart.tag || '');
        projectSearchInput.value = projectFilters.query;
        projectStatusFilter.value = projectFilters.status;
        nodeSearchInput.value = nodeFilters.query;
        nodeStatusFilter.value = nodeFilters.status;
        nodePriorityFilter.value = nodeFilters.priority;
        nodeDueFilter.value = nodeFilters.due;
        nodeTagFilter.value = nodeFilters.tag;
        renderProjects();
        if (currentProjectId) renderDetail();
        showToast(`已应用视图：${view.name}`);
    }

    // ---------- 批次 2：今日工作台 / 收集箱 / 最近入口 ----------

    const WORKBENCH_GROUP_TITLES = {
        overdue: '逾期',
        today: '今天到期',
        next7: '未来 7 天',
        reviewToday: '今天要复习',
        inbox: '收集箱（待归类）',
    };

    async function showWorkbench() {
        activateView(workbenchView);
        workbenchSubline.textContent = '';
        renderReviewMessageInto(workbenchBody, listStatusText('review', 'loading').replace('复习队列', '今日工作台'), false);
        try {
            const response = await apiFetch(`/api/workbench?today=${encodeURIComponent(todayStr())}`, { cache: 'no-store' });
            const board = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(board.error || '读取今日工作台失败，请重试');
            renderWorkbench(board);
        } catch (error) {
            renderReviewMessageInto(workbenchBody, error.message || '读取今日工作台失败，请重试', true, showWorkbench);
        }
    }

    function renderReviewMessageInto(container, text, withRetry, retryHandler) {
        container.replaceChildren();
        const message = document.createElement('p');
        message.className = 'review-empty';
        message.textContent = text;
        container.appendChild(message);
        if (withRetry) container.appendChild(createRetryButton('重试', retryHandler || showWorkbench));
    }

    function renderWorkbench(board) {
        const groups = board.groups || {};
        const totals = board.totals || {};
        workbenchSubline.textContent = `今天 ${totals.today || 0} · 逾期 ${totals.overdue || 0} · 未来 7 天 ${totals.next7 || 0}`
            + ` · 待复习 ${totals.reviewToday || 0} · 收集箱 ${totals.inbox || 0}`;
        workbenchBody.replaceChildren();
        const order = ['overdue', 'today', 'next7', 'reviewToday', 'inbox'];
        const fragment = document.createDocumentFragment();
        for (const key of order) {
            const items = groups[key] || [];
            const group = document.createElement('div');
            group.className = 'review-group';
            const head = document.createElement('div');
            head.className = 'review-group-title';
            const label = document.createElement('span');
            label.textContent = WORKBENCH_GROUP_TITLES[key] || key;
            const count = document.createElement('span');
            count.className = 'gcount';
            count.textContent = String(items.length);
            head.append(label, count);
            group.appendChild(head);
            if (items.length === 0) {
                const empty = document.createElement('p');
                empty.className = 'review-empty';
                empty.textContent = key === 'inbox' ? '收集箱是空的' : '没有需要处理的';
                group.appendChild(empty);
            } else {
                items.forEach(item => group.appendChild(createWorkbenchRow(item, key)));
            }
            fragment.appendChild(group);
        }
        workbenchBody.appendChild(fragment);
    }

    function createWorkbenchRow(item, groupKey) {
        const row = document.createElement('div');
        row.className = 'review-item';
        const main = document.createElement('div');
        main.className = 'review-item-main';
        const pathSpan = document.createElement('span');
        pathSpan.className = 'review-item-path';
        pathSpan.textContent = item.path ? `${item.projectName} · ${item.path}` : item.projectName;
        const text = document.createElement('div');
        text.className = 'review-item-text';
        text.textContent = item.text || '未命名任务';
        text.title = item.text || '';
        main.append(pathSpan, text);
        const metaWrap = createNodeMetaBadges(item);
        if (metaWrap) main.appendChild(metaWrap);
        if (groupKey === 'overdue' && item.daysOverdue) {
            const tag = document.createElement('span');
            tag.className = 'review-tag overdue';
            tag.textContent = `逾期 ${item.daysOverdue} 天`;
            main.appendChild(tag);
        }
        if (groupKey === 'reviewToday' && item.reviewDue) {
            const tag = document.createElement('span');
            tag.className = 'review-tag today';
            tag.textContent = item.reviewDue === todayStr() ? '今天复习' : `复习逾期 ${item.daysOverdue || 1} 天`;
            main.appendChild(tag);
        }
        const actions = document.createElement('div');
        actions.className = 'review-actions';
        if (groupKey !== 'reviewToday') {
            const done = document.createElement('button');
            done.type = 'button';
            done.className = 'review-btn easy';
            done.textContent = '完成';
            done.addEventListener('click', () => completeWorkbenchItem(item));
            const tomorrow = document.createElement('button');
            tomorrow.type = 'button';
            tomorrow.className = 'review-btn hard';
            tomorrow.textContent = '延期到明天';
            tomorrow.addEventListener('click', () => postponeWorkbenchItem(item));
            actions.append(done, tomorrow);
        } else {
            const goReview = document.createElement('button');
            goReview.type = 'button';
            goReview.className = 'review-btn easy';
            goReview.textContent = '去复习';
            goReview.addEventListener('click', () => showReviewQueue());
            actions.appendChild(goReview);
        }
        if (groupKey === 'inbox') {
            const fileIt = document.createElement('button');
            fileIt.type = 'button';
            fileIt.className = 'review-btn';
            fileIt.textContent = '归类';
            fileIt.addEventListener('click', () => openInboxMovePicker(item));
            actions.appendChild(fileIt);
        }
        const detail = document.createElement('button');
        detail.type = 'button';
        detail.className = 'review-btn';
        detail.textContent = '详情';
        detail.addEventListener('click', () => openWorkbenchItemMeta(item));
        const open = document.createElement('button');
        open.type = 'button';
        open.className = 'review-btn';
        open.textContent = '打开';
        open.addEventListener('click', () => locateNodeById(item.projectId, item.nodeId));
        actions.append(detail, open);
        row.append(main, actions);
        return row;
    }

    async function withWorkbenchNode(item, callback) {
        const project = await ensureProjectLoaded(item.projectId);
        const node = findNodeById(project.tree || [], item.nodeId);
        if (!node) throw new Error('任务已不存在，请刷新工作台');
        return callback(node);
    }

    async function completeWorkbenchItem(item) {
        try {
            await withWorkbenchNode(item, async (node) => {
                const before = node.completed;
                toggleNodeCompleted(node);
                if (node.completed === before) return;
                // 必须先等这次改动真正落库再重画看板：saveProjects() 只是排 250ms 防抖，
                // 立刻 GET /api/workbench 拿到的还是旧数据，看起来像"点了没反应"。
                await saveProjects();
                showWorkbench();
            });
        } catch (error) {
            showToast(error.message || '完成任务失败，请重试');
        }
    }

    async function postponeWorkbenchItem(item) {
        try {
            await withWorkbenchNode(item, async (node) => {
                node.dueDate = addDaysToIso(todayStr(), 1);
                markProjectDirty(owningProjectOfNode(node));
                await saveProjects();
                showToast('已延期到明天');
                showWorkbench();
            });
        } catch (error) {
            showToast(error.message || '延期失败，请重试');
        }
    }

    async function openWorkbenchItemMeta(item) {
        try {
            await withWorkbenchNode(item, (node) => openNodeMeta(node, { onSaved: () => showWorkbench() }));
        } catch (error) {
            showToast(error.message || '打开任务详情失败，请重试');
        }
    }

    async function locateNodeById(projectId, nodeId) {
        try {
            const project = await ensureProjectLoaded(projectId);
            const findAncestors = (nodes, ancestors) => {
                for (const node of nodes || []) {
                    if (String(node.id) === String(nodeId)) return ancestors;
                    const found = findAncestors(node.children, ancestors.concat(node.id));
                    if (found) return found;
                }
                return null;
            };
            const ancestorIds = findAncestors(project.tree || [], []) || [];
            await locateStudyTask(projectId, { id: nodeId, ancestorIds, path: '', text: '' });
        } catch (error) {
            showToast(error.message || '任务定位失败，请重试');
        }
    }

    async function submitQuickAdd(node, projectId, parentId) {
        const response = await apiFetch('/api/inbox/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ node, projectId: projectId || undefined, parentId: parentId || undefined })
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.error || '添加任务失败，请重试');
        return payload;
    }

    async function quickAddToInbox() {
        const raw = quickAddInput.value.trim();
        if (!raw) {
            quickAddInput.focus();
            return;
        }
        const parsed = parseQuickAdd(raw, { today: todayStr(), projects });
        const hasMeta = Boolean(parsed.dueDate || parsed.priority || parsed.tags.length || parsed.estimateMinutes
            || parsed.projectId || parsed.repeat);
        if (!hasMeta) {
            // 没解析出任何信息：保持"一句话快速记录"的最短路径，不弹预览
            quickAddBtn.disabled = true;
            try {
                await submitQuickAdd({ text: parsed.text || raw }, '');
                quickAddInput.value = '';
                showToast('已加入收集箱');
                await loadProjects();
                showWorkbench();
            } catch (error) {
                showToast(error.message || '加入收集箱失败，请重试');
            } finally {
                quickAddBtn.disabled = false;
                quickAddInput.focus();
            }
            return;
        }
        openQuickAddPreview(raw, parsed);
    }

    function openQuickAddPreview(raw, parsed) {
        showUtilityModal('确认添加', '解析结果预览');
        utilityBody.innerHTML = '';
        const form = document.createElement('div');
        form.className = 'meta-form';
        const hint = document.createElement('p');
        hint.className = 'utility-hint';
        hint.textContent = parsed.matched.length > 0
            ? `原文：${raw}　识别到：${parsed.matched.join(' ')}`
            : `原文：${raw}`;
        form.appendChild(hint);
        if (parsed.warnings.length > 0) {
            const warn = document.createElement('p');
            warn.className = 'utility-hint';
            warn.textContent = parsed.warnings.join('；');
            form.appendChild(warn);
        }
        const addField = (label, control) => {
            const field = document.createElement('label');
            field.className = 'meta-field';
            const caption = document.createElement('span');
            caption.textContent = label;
            field.append(caption, control);
            form.appendChild(field);
            return field;
        };
        const textInput = document.createElement('input');
        textInput.type = 'text';
        textInput.value = parsed.text;
        addField('任务内容', textInput);

        const projectSelect = document.createElement('select');
        const inboxOption = document.createElement('option');
        inboxOption.value = '';
        inboxOption.textContent = '收集箱（稍后归类）';
        projectSelect.appendChild(inboxOption);
        projects.filter(entry => !entry.archived).forEach(entry => {
            const option = document.createElement('option');
            option.value = entry.id;
            option.textContent = entry.name;
            projectSelect.appendChild(option);
        });
        projectSelect.value = parsed.projectId || '';
        addField('放到', projectSelect);

        const prioritySelect = document.createElement('select');
        [['', '无'], ['high', '高'], ['mid', '中'], ['low', '低']].forEach(([value, label]) => {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = label;
            prioritySelect.appendChild(option);
        });
        prioritySelect.value = parsed.priority;
        addField('优先级', prioritySelect);

        const dueInput = document.createElement('input');
        dueInput.type = 'date';
        dueInput.value = parsed.dueDate;
        // 用户没改截止日期时，周期规则的锚点要沿用解析结果
        // （否则 "每周三交周报" 会被写成"每周<今天星期几>"）。
        const initialDueDate = dueInput.value;
        addField('截止日期', dueInput);

        const tagsInput = document.createElement('input');
        tagsInput.type = 'text';
        tagsInput.value = parsed.tags.join(', ');
        addField('标签', tagsInput);

        const estimateInput = document.createElement('input');
        estimateInput.type = 'number';
        estimateInput.min = '0';
        estimateInput.step = '5';
        estimateInput.value = String(parsed.estimateMinutes || '');
        addField('预计耗时（分钟）', estimateInput);

        const repeatSelect = document.createElement('select');
        [['', '不重复'], ['daily', '每天'], ['weekday', '每个工作日'], ['weekly', '每周'], ['monthly', '每月']]
            .forEach(([value, label]) => {
                const option = document.createElement('option');
                option.value = value;
                option.textContent = label;
                repeatSelect.appendChild(option);
            });
        repeatSelect.value = parsed.repeat ? parsed.repeat.freq : '';
        addField('周期', repeatSelect);

        const actions = document.createElement('div');
        actions.className = 'utility-actions';
        const confirm = document.createElement('button');
        confirm.type = 'button';
        confirm.className = 'utility-primary-btn';
        confirm.textContent = '确认添加';
        confirm.addEventListener('click', async () => {
            confirm.disabled = true;
            // 解析出来的"每周三 / 每月15号"是规则的锚点，不能按截止日期重算丢掉。
            const repeat = buildRepeatRule(
                repeatSelect.value, dueInput.value, parsed.repeat,
                { anchorChanged: dueInput.value !== initialDueDate }
            );
            try {
                await submitQuickAdd({
                    text: textInput.value.trim() || '未命名任务',
                    priority: prioritySelect.value,
                    dueDate: dueInput.value,
                    tags: tagsInput.value.split(/[,，\s]+/).map(item => item.trim()).filter(Boolean),
                    estimateMinutes: estimateInput.value,
                    repeat,
                }, projectSelect.value);
                quickAddInput.value = '';
                closeUtilityModal();
                showToast(projectSelect.value ? '已添加到项目' : '已加入收集箱');
                await loadProjects();
                showWorkbench();
            } catch (error) {
                showToast(error.message || '添加失败，请重试');
                confirm.disabled = false;
            }
        });
        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'utility-secondary-btn';
        cancel.textContent = '取消';
        cancel.addEventListener('click', closeUtilityModal);
        actions.append(confirm, cancel);
        form.appendChild(actions);
        utilityBody.appendChild(form);
    }

    // ---------- 提醒（只在页面打开时生效） ----------

    const REMINDER_STORAGE_KEY = 'todo_list_reminders';

    const reminderState = { enabled: false, timer: null, fired: new Set(), permission: 'default' };

    function loadReminderSettings() {
        try {
            const raw = window.localStorage.getItem(REMINDER_STORAGE_KEY);
            if (raw) {
                const parsed = JSON.parse(raw);
                reminderState.enabled = Boolean(parsed.enabled);
                reminderState.fired = new Set(Array.isArray(parsed.fired) ? parsed.fired.slice(-500) : []);
            }
        } catch (error) {
            console.warn('读取提醒设置失败', error);
        }
        if (typeof Notification === 'function') reminderState.permission = Notification.permission;
    }

    function saveReminderSettings() {
        try {
            window.localStorage.setItem(REMINDER_STORAGE_KEY, JSON.stringify({
                enabled: reminderState.enabled,
                fired: [...reminderState.fired].slice(-500),
            }));
        } catch (error) {
            console.warn('保存提醒设置失败', error);
        }
    }

    function renderReminderStatus() {
        if (!reminderStatus) return;
        const parts = [];
        parts.push(reminderState.enabled ? '提醒：已开启（每分钟检查一次）' : '提醒：已关闭');
        if (reminderState.permission === 'granted') parts.push('浏览器通知：已允许');
        else if (reminderState.permission === 'denied') parts.push('浏览器通知：已被浏览器拒绝');
        else parts.push('浏览器通知：未授权');
        parts.push('只在页面开着时生效');
        reminderStatus.textContent = parts.join(' · ');
        if (reminderToggleBtn) reminderToggleBtn.textContent = reminderState.enabled ? '关闭提醒' : '开启提醒';
    }

    async function checkReminders() {
        if (!reminderState.enabled) return;
        let board = null;
        try {
            const response = await apiFetch(`/api/workbench?today=${encodeURIComponent(todayStr())}`, { cache: 'no-store' });
            board = await response.json().catch(() => null);
            if (!response.ok || !board) return;
        } catch (error) {
            return; // 下一次检查再试
        }
        const groups = board.groups || {};
        const pending = [];
        [['overdue', '逾期'], ['today', '今天到期'], ['reviewToday', '待复习']].forEach(([key, label]) => {
            (groups[key] || []).forEach(item => {
                const fireKey = `${todayStr()}:${key}:${item.projectId}:${item.nodeId}`;
                if (reminderState.fired.has(fireKey)) return;
                reminderState.fired.add(fireKey);
                pending.push({ label, item });
            });
        });
        if (pending.length === 0) return;
        saveReminderSettings();
        const head = pending.slice(0, 3).map(entry => `${entry.label}：${entry.item.text}`).join('；');
        showToast(`⏰ ${head}${pending.length > 3 ? ` 等 ${pending.length} 项` : ''}`);
        if (reminderState.permission === 'granted' && typeof Notification === 'function') {
            pending.slice(0, 3).forEach(entry => {
                try {
                    new Notification(`待办提醒 · ${entry.label}`, {
                        body: entry.item.text,
                        tag: `${entry.item.projectId}:${entry.item.nodeId}`,
                    });
                } catch (error) {
                    // 通知失败不影响页内提醒
                }
            });
        }
    }

    function startReminders() {
        if (reminderState.timer) return;
        reminderState.timer = window.setInterval(() => { checkReminders(); }, 60 * 1000);
        window.setTimeout(() => { checkReminders(); }, 3000);
    }

    function stopReminders() {
        if (reminderState.timer) {
            window.clearInterval(reminderState.timer);
            reminderState.timer = null;
        }
    }

    async function toggleReminders() {
        reminderState.enabled = !reminderState.enabled;
        saveReminderSettings();
        if (reminderState.enabled) {
            startReminders();
            if (typeof Notification === 'function' && Notification.permission === 'default') {
                try {
                    reminderState.permission = await Notification.requestPermission();
                } catch (error) {
                    reminderState.permission = Notification.permission;
                }
            }
            showToast('提醒已开启（只在页面开着时生效）');
        } else {
            stopReminders();
            showToast('提醒已关闭');
        }
        renderReminderStatus();
    }

    async function requestNotificationPermission() {
        if (typeof Notification !== 'function') {
            showToast('当前浏览器不支持系统通知，只能页内提醒');
            return;
        }
        try {
            reminderState.permission = await Notification.requestPermission();
        } catch (error) {
            reminderState.permission = Notification.permission;
        }
        renderReminderStatus();
        showToast(reminderState.permission === 'granted' ? '已允许浏览器通知' : '浏览器通知未授权');
    }

    function flattenParentOptions(project) {
        const options = [{ id: null, label: '（项目根目录）' }];
        const walk = (nodes, depth) => {
            for (const node of nodes || []) {
                if (node.type !== 'item') {
                    options.push({ id: node.id, label: `${'　'.repeat(depth)}${node.text || '未命名'}` });
                    walk(node.children, depth + 1);
                }
            }
        };
        walk(project.tree || [], 0);
        return options;
    }

    async function openInboxMovePicker(item) {
        showUtilityModal('归类任务', '从收集箱移到项目');
        renderUtilityMessage('正在读取项目…');
        let summaries = [];
        try {
            const response = await apiFetch('/api/projects', { cache: 'no-store' });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '读取项目失败，请重试');
            summaries = (payload.projects || []).filter(entry => entry.id !== 'inbox' && !entry.archived);
        } catch (error) {
            renderUtilityMessage(error.message || '读取项目失败，请重试');
            return;
        }
        if (summaries.length === 0) {
            renderUtilityMessage('还没有其他项目，先新建一个项目再归类');
            return;
        }
        utilityBody.innerHTML = '';
        const form = document.createElement('div');
        form.className = 'meta-form';
        const hint = document.createElement('p');
        hint.className = 'utility-hint';
        hint.textContent = `把“${item.text}”移到：`;
        form.appendChild(hint);
        const projectSelect = document.createElement('select');
        summaries.forEach(entry => {
            const option = document.createElement('option');
            option.value = entry.id;
            option.textContent = entry.name;
            projectSelect.appendChild(option);
        });
        const parentSelect = document.createElement('select');
        const projectField = document.createElement('label');
        projectField.className = 'meta-field';
        const projectCaption = document.createElement('span');
        projectCaption.textContent = '目标项目';
        projectField.append(projectCaption, projectSelect);
        const parentField = document.createElement('label');
        parentField.className = 'meta-field';
        const parentCaption = document.createElement('span');
        parentCaption.textContent = '放到哪一周 / 单元';
        parentField.append(parentCaption, parentSelect);
        form.append(projectField, parentField);

        const loadParents = async () => {
            parentSelect.replaceChildren();
            const loading = document.createElement('option');
            loading.textContent = '正在读取…';
            parentSelect.appendChild(loading);
            try {
                const project = await ensureProjectLoaded(projectSelect.value);
                parentSelect.replaceChildren();
                flattenParentOptions(project).forEach(entry => {
                    const option = document.createElement('option');
                    option.value = entry.id === null ? '' : String(entry.id);
                    option.textContent = entry.label;
                    parentSelect.appendChild(option);
                });
            } catch (error) {
                parentSelect.replaceChildren();
                const failed = document.createElement('option');
                failed.textContent = '读取失败，请重试';
                parentSelect.appendChild(failed);
            }
        };
        projectSelect.addEventListener('change', loadParents);
        await loadParents();

        const actions = document.createElement('div');
        actions.className = 'utility-actions';
        const confirm = document.createElement('button');
        confirm.type = 'button';
        confirm.className = 'utility-primary-btn';
        confirm.textContent = '确认归类';
        confirm.addEventListener('click', async () => {
            confirm.disabled = true;
            try {
                const response = await apiFetch('/api/inbox/move', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        nodeId: item.nodeId,
                        fromProjectId: item.projectId,
                        toProjectId: projectSelect.value,
                        parentId: parentSelect.value || null
                    })
                });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(payload.error || '归类失败，请重试');
                if (Array.isArray(payload.projects)) projects = payload.projects.map(normalizeProjectSummary);
                savedProjectJsonById.clear();
                closeUtilityModal();
                showToast('已归类');
                renderProjects();
                showWorkbench();
            } catch (error) {
                showToast(error.message || '归类失败，请重试');
                confirm.disabled = false;
            }
        });
        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'utility-secondary-btn';
        cancel.textContent = '取消';
        cancel.addEventListener('click', closeUtilityModal);
        actions.append(confirm, cancel);
        form.appendChild(actions);
        utilityBody.appendChild(form);
    }

    async function showRecent() {
        showUtilityModal('最近', '打开 · 修改 · 完成');
        renderUtilityMessage('正在读取最近记录…');
        let recent;
        try {
            const response = await apiFetch('/api/recent', { cache: 'no-store' });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '读取最近记录失败，请重试');
            recent = payload;
        } catch (error) {
            renderUtilityMessage(error.message || '读取最近记录失败，请重试');
            return;
        }
        utilityBody.innerHTML = '';
        const wrap = document.createElement('div');
        wrap.className = 'conflict-list';
        const addSection = (title, entries, renderRow) => {
            const heading = document.createElement('div');
            heading.className = 'review-group-title';
            heading.textContent = `${title}（${entries.length}）`;
            wrap.appendChild(heading);
            if (entries.length === 0) {
                const empty = document.createElement('p');
                empty.className = 'utility-empty';
                empty.textContent = '还没有记录';
                wrap.appendChild(empty);
                return;
            }
            entries.forEach(entry => wrap.appendChild(renderRow(entry)));
        };
        const projectRow = (entry) => {
            const row = document.createElement('button');
            row.type = 'button';
            row.className = 'search-result';
            const title = document.createElement('strong');
            title.textContent = entry.name + (entry.archived ? '（已归档）' : '');
            const detail = document.createElement('small');
            detail.textContent = String(entry.at || '').slice(0, 16).replace('T', ' ');
            row.append(title, detail);
            row.addEventListener('click', async () => {
                closeUtilityModal();
                await openProjectDetail(entry.id);
            });
            return row;
        };
        const completedRow = (entry) => {
            const row = document.createElement('button');
            row.type = 'button';
            row.className = 'search-result';
            const title = document.createElement('strong');
            title.textContent = entry.text || '未命名任务';
            const detail = document.createElement('small');
            detail.textContent = `${entry.projectName} · ${String(entry.at || '').slice(0, 16).replace('T', ' ')}`;
            row.append(title, detail);
            row.addEventListener('click', async () => {
                closeUtilityModal();
                await locateNodeById(entry.projectId, entry.nodeId);
            });
            return row;
        };
        addSection('最近打开', recent.opened || [], projectRow);
        addSection('最近修改', recent.modified || [], projectRow);
        addSection('最近完成', recent.completed || [], completedRow);
        utilityBody.appendChild(wrap);
    }

    function renderReviewMessage(text, withRetry) {
        reviewBody.innerHTML = '';
        const message = document.createElement('p');
        message.className = 'review-empty';
        message.textContent = text;
        reviewBody.appendChild(message);
        if (withRetry) {
            reviewBody.appendChild(createRetryButton('重试', showReviewQueue));
        }
    }

    // 复习页主体：按知识点分组（今日必须复习 / 即将到期 / 已逾期 / 薄弱知识点 /
    // 新知识点 / 最近答错 / 最近掌握），任务级到期单独成组放在最后。
    // 范围筛选（overdue/weak/new）只是前端分组过滤，不需要重新拉取数据。
    function renderReviewGroups() {
        const state = reviewQueueState;
        const body = reviewBody;
        // 用 replaceChildren 而不是 innerHTML=''：范围筛选会反复重渲染，
        // 必须真的把上一次的分组清掉（DOM 桩里 innerHTML 赋值不会清子节点）。
        body.replaceChildren();
        const scope = (reviewScopeFilter && reviewScopeFilter.value) || '';
        const scopedTitles = { overdue: '已逾期', weak: '薄弱知识点', new: '新知识点' };
        // 题型筛选也要作用于那两组作答记录：记录里带 questionType，可直接按当前题型过滤
        // （它们不属于范围筛选，所以放在 scope 过滤之前）。
        const type = (reviewTypeFilter && reviewTypeFilter.value) || '';
        const matchesType = entry => !type || entry.questionType === type;
        let groups = [
            { title: '今日必须复习', items: state.dueToday || [] },
            { title: '即将到期', items: state.upcoming || [] },
            { title: '已逾期', items: state.overdue || [] },
            { title: '薄弱知识点', items: state.weak || [] },
            { title: '新知识点', items: state.newItems || [] },
            { title: '最近答错', items: (state.recentWrong || []).filter(matchesType), attempt: true },
            { title: '最近掌握', items: (state.recentMastered || []).filter(matchesType), attempt: true },
        ];
        if (scope) {
            groups = groups.filter(entry => entry.title === scopedTitles[scope]);
        }
        let matchedGroups = 0;
        groups.forEach(entry => {
            if (entry.items.length === 0) return;
            matchedGroups += 1;
            body.appendChild(entry.attempt ? renderAttemptGroup(entry.title, entry.items)
                : renderKnowledgeGroup(entry.title, entry.items));
        });
        // 任务组沿用旧 /api/reviews 的行渲染与操作按钮（记住/模糊/忘了/更多/AI）。
        // 它有自己的 due 判断（due / future 两个桶），不受"只看已逾期/薄弱/新知识点"这个
        // 范围筛选影响——以前 scope 非空时整组被隐藏，等于把它也筛掉了。
        if ((state.taskDue || []).length > 0) {
            body.appendChild(renderReviewGroup(scope ? '任务级到期（原来的复习 · 不受范围筛选影响）'
                : '任务级到期（原来的复习）', state.taskDue));
        }
        if ((state.taskFuture || []).length > 0) {
            body.appendChild(renderReviewGroup(scope ? '任务级到期 · 未来安排（不受范围筛选影响）'
                : '任务级到期 · 未来安排', state.taskFuture));
        }
        // 范围筛选下的空态要和"今天完全没有到期"区分开：前者只是这个范围没条目。
        if (scope && matchedGroups === 0) {
            const message = document.createElement('p');
            message.className = 'review-empty';
            message.textContent = `该范围（${scopedTitles[scope]}）没有条目：换一个范围，或点「全部」看今天到期的知识点`;
            body.appendChild(message);
        }
        if (body.childElementCount === 0) {
            const empty = document.createElement('p');
            empty.className = 'review-empty';
            empty.textContent = scope
                ? `该范围（${scopedTitles[scope]}）没有条目：换一个范围，或点「全部」看今天到期的知识点`
                : '今天没有到期的知识点：可以去知识点库挑一个练，或先完成学习任务';
            body.appendChild(empty);
        }
    }

    function renderKnowledgeGroup(title, items) {
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
        items.forEach(item => group.appendChild(createKnowledgeItemElement(item)));
        return group;
    }

    function createKnowledgeItemElement(item) {
        const row = document.createElement('div');
        row.className = 'review-item';
        const main = document.createElement('div');
        main.className = 'review-item-main';
        const path = document.createElement('span');
        path.className = 'review-item-path';
        path.textContent = `${item.module || '未分类'} · ${item.minutes || 0} 分钟`;
        const text = document.createElement('div');
        text.className = 'review-item-text';
        text.textContent = item.title || item.code || '未命名知识点';
        main.append(path, text);
        if (Number(item.lastGrade) > 0) {
            const tag = document.createElement('span');
            tag.className = 'review-tag';
            tag.textContent = GRADE_LABELS[Number(item.lastGrade)] || `档位 ${item.lastGrade}`;
            main.appendChild(tag);
        }
        const actions = document.createElement('div');
        actions.className = 'review-actions';
        // 只有队列里的题才带题型/题面；没有题面的条目只提供历史入口。
        if (item.questionType && item.prompt) {
            const start = document.createElement('button');
            start.type = 'button';
            start.className = 'review-btn easy';
            start.textContent = '开始复习这一题';
            start.addEventListener('click', () => startReviewSessionWithItems([item]));
            actions.appendChild(start);
        }
        const detail = document.createElement('button');
        detail.type = 'button';
        detail.className = 'review-btn';
        detail.textContent = '历史';
        detail.addEventListener('click', () => showReviewHistory(item.code));
        actions.appendChild(detail);
        row.append(main, actions);
        return row;
    }

    // ---- 最近答错 / 最近掌握：渲染的是"作答记录"，不是知识点 ----
    // 记录来自 /api/review/summary 的 recentWrong/recentMastered（grade<=2 / grade>=4），
    // 所以能显示当时用的题型、自评档位、作答日期和我写的答案摘要。
    function reviewAnswerSummary(answer) {
        const text = String(answer == null ? '' : answer).replace(/\s+/g, ' ').trim();
        if (!text) return '（没写答案）';
        return text.length > 60 ? `${text.slice(0, 60)}…` : text;
    }

    function createAttemptItemElement(attempt) {
        const row = document.createElement('div');
        row.className = 'review-item';
        const main = document.createElement('div');
        main.className = 'review-item-main';
        const path = document.createElement('span');
        path.className = 'review-item-path';
        const typeLabel = REVIEW_TYPE_LABELS[attempt.questionType] || attempt.questionType || '未标注题型';
        path.textContent = `${typeLabel} · ${attempt.reviewedOn || '日期未知'}`;
        const text = document.createElement('div');
        text.className = 'review-item-text';
        text.textContent = attempt.title || attempt.code || '未命名知识点';
        const answer = document.createElement('div');
        answer.className = 'review-item-answer';
        answer.textContent = `我写的：${reviewAnswerSummary(attempt.answer)}`;
        main.append(path, text, answer);
        const tag = document.createElement('span');
        tag.className = 'review-tag';
        tag.textContent = `第 ${attempt.grade} 档 · ${GRADE_LABELS[Number(attempt.grade)] || `档位 ${attempt.grade}`}`;
        main.appendChild(tag);
        const actions = document.createElement('div');
        actions.className = 'review-actions';
        // code 用来"立即练一次"：按这个知识点（和当时的题型）取一道题进会话。
        const start = document.createElement('button');
        start.type = 'button';
        start.className = 'review-btn easy';
        start.textContent = '立即练一次';
        start.addEventListener('click', () => startReviewPointNow(attempt.code, attempt.questionType));
        const detail = document.createElement('button');
        detail.type = 'button';
        detail.className = 'review-btn';
        detail.textContent = '历史';
        detail.addEventListener('click', () => showReviewHistory(attempt.code));
        actions.append(start, detail);
        row.append(main, actions);
        return row;
    }

    function renderAttemptGroup(title, attempts) {
        const group = document.createElement('div');
        group.className = 'review-group';
        const head = document.createElement('div');
        head.className = 'review-group-title';
        const label = document.createElement('span');
        label.textContent = title;
        const count = document.createElement('span');
        count.className = 'gcount';
        count.textContent = String(attempts.length);
        head.append(label, count);
        group.appendChild(head);
        attempts.forEach(attempt => group.appendChild(createAttemptItemElement(attempt)));
        return group;
    }

    // 从作答记录直接开练：用 code + 当时的题型取一道题（队列接口支持 code/type）。
    async function startReviewPointNow(code, questionType) {
        try {
            const params = [`today=${encodeURIComponent(todayStr())}`, `code=${encodeURIComponent(code)}`, 'limit=1'];
            if (questionType) params.push(`type=${encodeURIComponent(questionType)}`);
            const response = await apiFetch(`/api/review/queue?${params.join('&')}`, { cache: 'no-store' });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '读取复习题失败');
            const items = Array.isArray(payload.items) ? payload.items : [];
            if (items.length === 0) {
                showToast('这个知识点暂时取不到题目，去知识点库看看');
                return;
            }
            await startReviewSessionWithItems(items);
        } catch (error) {
            showToast(error.message || '读取复习题失败，请重试');
        }
    }

    async function showReviewHistory(code) {
        try {
            const response = await apiFetch(`/api/review/history?code=${encodeURIComponent(code)}`, { cache: 'no-store' });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.error || '读取历史失败');
            showUtilityModal('复习历史', data.title || code);
            const lines = (Array.isArray(data.attempts) ? data.attempts : []).map(entry =>
                `${entry.reviewedOn || ''} · ${GRADE_LABELS[entry.grade] || entry.grade} · ${entry.answer || '（没写）'}`);
            utilityBody.textContent = lines.length > 0 ? lines.join('\n') : '还没有作答记录';
        } catch (error) {
            showToast(error.message || '读取历史失败');
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
        const blockFragment = document.createDocumentFragment();
        for (const entry of byProject.entries()) {
            const projectBlock = document.createElement('div');
            projectBlock.className = 'review-project-block';
            const nameRow = document.createElement('div');
            nameRow.className = 'review-project-name';
            nameRow.textContent = entry[1][0].projectName;
            projectBlock.append(nameRow, ...entry[1].map(item => createReviewItemElement(item)));
            blockFragment.appendChild(projectBlock);
        }
        group.appendChild(blockFragment);
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
        placeholder.textContent = '更多';
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
        const aiGroup = document.createElement('div');
        aiGroup.className = 'review-ai-group';
        const aiBtns = [
            ['拟题', 'queueOpenAssessment', '针对本任务再出题'],
            ['复制', 'copyText', '复制任务文本'],
            ['摘要', 'queueSummary', '生成核心摘要']
        ];
        aiBtns.forEach((pair) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'review-btn';
            btn.textContent = pair[0];
            btn.title = pair[2];
            btn.addEventListener('click', () => {
                if (pair[1] === 'copyText') copyText(item.node.text || '');
                else if (pair[1] === 'queueSummary') queueSummary(item);
                else queueOpenAssessment(item);
            });
            aiGroup.appendChild(btn);
        });
        row.append(main, actions);
        row.appendChild(aiGroup);
        return row;
    }

    function daysBetween(fromIso, toIso) {
        const a = fromIso.split('-').map(Number);
        const b = toIso.split('-').map(Number);
        const start = new Date(a[0], a[1] - 1, a[2]);
        const end = new Date(b[0], b[1] - 1, b[2]);
        return Math.round((end - start) / 86400000);
    }

    // 队列里的节点不一定在内存里（数据来自服务端聚合）：
    // 只有真的要改复习计划时才加载这一个项目，之后的逻辑与原来完全一致。
    async function resolveQueueNode(item) {
        if (!item || !item.node) return null;
        const project = await ensureProjectLoaded(item.projectId);
        return findNodeById(project.tree || [], item.node.id) || null;
    }

    async function runQueueAction(item, action) {
        if (!item || !item.node) return;
        try {
            if (action !== 'locate') {
                const node = await resolveQueueNode(item);
                if (!node) {
                    showToast('任务不存在或已被删除，正在刷新队列');
                    await showReviewQueue();
                    return;
                }
                item.node = node;
            }
            runQueueActionNow(item, action);
        } catch (error) {
            showToast(error.message || '复习操作失败，请重试');
        }
    }

    function runQueueActionNow(item, action) {
        // 复习计划只改这一个节点：先判定能否 patch，再改，最后按需落库
        const owner = owningProjectOfNode(item.node);
        const patchSafe = canUseNodePatch(owner);
        const persistReview = () => persistNodeFields(
            owner, item.node, { review: item.node.review || null }, patchSafe);
        if (action === 'easy' || action === 'hard' || action === 'again') {
            applyReviewResult(item.node, action);
            persistReview();
            finishQueueAction();
        } else if (action === 'd1' || action === 'd3' || action === 'd7' || action === 'd30') {
            const days = action === 'd1' ? 1 : action === 'd3' ? 3 : action === 'd7' ? 7 : 30;
            scheduleReview(item.node, addDaysToIso(todayStr(), days));
            persistReview();
            finishQueueAction();
        } else if (action === 'clear') {
            if (!window.confirm('清除该任务的复习安排？')) return;
            clearReview(item.node);
            persistReview();
            finishQueueAction();
        } else if (action === 'custom') {
            const chosen = window.prompt('自定义复习日期（YYYY-MM-DD）：', addDaysToIso(todayStr(), 7));
            if (chosen === null) return;
            const date = String(chosen).trim();
            if (!isValidIsoDate(date)) { showToast('日期格式不正确（应为 YYYY-MM-DD）'); return; }
            scheduleReview(item.node, date);
            persistReview();
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


    async function queueSummary(item) {
        if (!item || !item.node) return;
        try {
            const response = await apiFetch('/api/summary', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question: item.node.text || '',
                    context: { project: item.projectName || '' },
                    model: 'flash'
                })
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || !payload.summary) throw new Error(payload.error || '生成摘要失败，请重试');
            showToast('已保存到摘要清单（同题去重）');
        } catch (error) {
            showToast(error.message || '生成摘要失败，请重试');
        }
    }

    async function queueOpenAssessment(item) {
        if (!item) return;
        try {
            const project = await ensureProjectLoaded(item.projectId);
            const node = findNodeById(project.tree || [], item.node.id);
            if (!node) throw new Error('任务不存在');
            showDetailView(project.id);
            openAssessment(node);
        } catch (error) {
            showToast(error.message || '打开验收失败，请重试');
        }
    }

    async function finishQueueAction() {
        try {
            await saveProjects();
        } catch (error) {
            showToast(error.message || '保存失败，请重试');
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
        // 复习队列/工作台里也可能点到"安排复习"（那时没有当前项目），按节点找所属项目。
        const project = owningProjectOfNode(node);
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
                const owner = owningProjectOfNode(node);
                const patchSafe = canUseNodePatch(owner);
                scheduleReview(node, choice[1]);
                persistNodeFields(owner, node, { review: node.review || null }, patchSafe);
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
            const owner = owningProjectOfNode(node);
            const patchSafe = canUseNodePatch(owner);
            scheduleReview(node, date);
            persistNodeFields(owner, node, { review: node.review || null }, patchSafe);
            finishScheduleModal();
        });
        list.appendChild(customButton);
        const clearButton = document.createElement('button');
        clearButton.type = 'button';
        clearButton.className = 'utility-task delete-proj-btn';
        clearButton.textContent = '清除复习安排';
        clearButton.addEventListener('click', () => {
            if (!window.confirm('清除该任务的复习安排？')) return;
            const owner = owningProjectOfNode(node);
            const patchSafe = canUseNodePatch(owner);
            clearReview(node);
            persistNodeFields(owner, node, { review: null }, patchSafe);
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
            if (stored && stored.serverToday && stored.serverToday !== todayStr() && !timezoneWarned) {
                timezoneWarned = true;
                showToast(`本机日期 ${todayStr()} 与服务端 ${stored.serverToday} 不一致，复习计数以本机日期为准`);
            }
        } catch (error) {
            console.warn('刷新复习计数失败', error);
        }
        if (projectsView.classList.contains('active')) renderProjects();
    }


    function copyText(text) {
        if (!text) { showToast('没有可复制的内容'); return; }
        const done = () => showToast('已复制');
        const fallback = () => {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.left = '-9999px';
            document.body.appendChild(textarea);
            textarea.select();
            let okCopy = false;
            try { okCopy = document.execCommand('copy'); } catch (e) { okCopy = false; }
            textarea.remove();
            showToast(okCopy ? '已复制' : '复制失败，请手动选择');
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(done, fallback);
        } else {
            fallback();
        }
    }

    function copyCurrentQuestion() {
        copyText(assessmentQuestionItems[assessmentQuestionIndex] || '');
        if (assessmentQuestionItems[assessmentQuestionIndex]) showToast('已复制当前题目');
    }

    async function generateSummary() {
        if (!assessmentNode) return;
        const question = assessmentQuestionItems[assessmentQuestionIndex] || assessmentNode.text || '';
        if (!question) { showToast('没有可总结的内容'); return; }
        summaryQuestionBtn.disabled = true;
        const label = summaryQuestionBtn.textContent;
        summaryQuestionBtn.textContent = '生成中…';
        try {
            const response = await apiFetch('/api/summary', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question,
                    context: getAssessmentContext(assessmentNode),
                    model: assessmentModel.value
                })
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || !payload.summary) throw new Error(payload.error || '生成摘要失败，请重试');
            showToast('已保存到摘要清单（同题去重）');
        } catch (error) {
            showToast(error.message || '生成摘要失败，请重试');
        } finally {
            summaryQuestionBtn.disabled = false;
            summaryQuestionBtn.textContent = label;
        }
    }

    async function openSummaryList() {
        showUtilityModal('核心摘要', '摘要清单');
        renderUtilityMessage('正在读取摘要…');
        try {
            const response = await apiFetch('/api/summaries', { cache: 'no-store' });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.error || '读取摘要清单失败，请重试');
            renderSummaryList(payload.summaries || []);
        } catch (error) {
            renderUtilityMessage(error.message || '读取摘要清单失败，请重试');
        }
    }

    function renderSummaryList(summaries) {
        utilityBody.innerHTML = '';
        const toolbar = document.createElement('div');
        toolbar.className = 'utility-toolbar';
        const count = document.createElement('span');
        count.textContent = '共 ' + summaries.length + ' 条摘要 · 点击卡片查看详情';
        toolbar.appendChild(count);
        if (summaries.length > 0) {
            const clearBtn = document.createElement('button');
            clearBtn.type = 'button';
            clearBtn.className = 'utility-secondary-btn';
            clearBtn.textContent = '清空全部';
            clearBtn.addEventListener('click', async (event) => {
                event.stopPropagation();
                if (!window.confirm('确认清空全部核心摘要？')) return;
                try {
                    const res = await apiFetch('/api/summaries', { method: 'DELETE' });
                    const body = await res.json().catch(() => ({}));
                    if (!res.ok) throw new Error(body.error || '清空失败，请重试');
                    renderSummaryList(body.summaries || []);
                    showToast('已清空摘要清单');
                } catch (error) {
                    showToast(error.message || '清空失败，请重试');
                }
            });
            toolbar.appendChild(clearBtn);
        }
        utilityBody.appendChild(toolbar);
        if (summaries.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'utility-empty';
            empty.textContent = '还没有摘要；在 AI 验收题目区点「核心摘要」即可生成并收藏';
            utilityBody.appendChild(empty);
            return;
        }
        const grid = document.createElement('div');
        grid.className = 'summary-grid';
        const summaryFragment = document.createDocumentFragment();
        for (const item of summaries) {
            const card = document.createElement('div');
            card.className = 'summary-item';
            const title = document.createElement('div');
            title.className = 'summary-question';
            title.textContent = item.question || '未知知识点';
            const content = document.createElement('div');
            content.className = 'summary-content';
            content.textContent = item.content || '';
            const footer = document.createElement('div');
            footer.className = 'summary-footer';
            const date = document.createElement('span');
            date.className = 'summary-date';
            date.textContent = '创建于 ' + (item.createdAt || '').slice(0, 10);
            const del = document.createElement('button');
            del.type = 'button';
            del.className = 'utility-secondary-btn summary-delete';
            del.textContent = '删除';
            del.addEventListener('click', async (event) => {
                event.stopPropagation();
                if (!window.confirm('删除这条摘要？')) return;
                try {
                    const res = await apiFetch('/api/summary?id=' + encodeURIComponent(item.id), { method: 'DELETE' });
                    const body = await res.json().catch(() => ({}));
                    if (!res.ok) throw new Error(body.error || '删除失败，请重试');
                    renderSummaryList(body.summaries || []);
                    showToast('已删除');
                } catch (error) {
                    showToast(error.message || '删除失败，请重试');
                }
            });
            footer.appendChild(date);
            footer.appendChild(del);
            card.appendChild(title);
            card.appendChild(content);
            card.appendChild(footer);
            card.addEventListener('click', () => card.classList.toggle('expanded'));
            summaryFragment.appendChild(card);
        }
        grid.replaceChildren(summaryFragment);
        utilityBody.appendChild(grid);
    }

    async function loadTrashItems() {
        const response = await apiFetch('/api/trash', { cache: 'no-store' });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !Array.isArray(payload.items)) throw new Error(payload.error || '读取回收站失败，请重试');
        trashItems = payload.items;
        return trashItems;
    }

    async function storeTrashItem(item) {
        const response = await apiFetch('/api/trash', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'store', item })
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !payload.item) throw new Error(payload.error || '写入回收站失败，请重试');
        trashItems = payload.items || trashItems;
        return payload.item;
    }

    async function restoreTrashItem(id) {
        const response = await apiFetch('/api/trash', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'restore', id })
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.error || '恢复失败，请重试');
        trashItems = payload.items || trashItems;
        if (Array.isArray(payload.projects)) {
            projects = payload.projects.map(normalizeProjectSummary);
            savedProjectJsonById.clear();
            dirtyProjectIds.clear();
            saveConflict = false;
            renderProjects();
        }
        return payload.item;
    }

    async function deleteTrashItemById(id) {
        const response = await apiFetch('/api/trash', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'delete', id })
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.error || '删除回收站条目失败，请重试');
        trashItems = payload.items || trashItems;
    }

    function renderTrashItems(items) {
        utilityBody.innerHTML = '';
        const selected = new Set();
        const toolbar = document.createElement('div');
        toolbar.className = 'utility-toolbar';
        const count = document.createElement('span');
        const retention = items.length > 0 && items[0].expiresAt
            ? `（最近一条将于 ${items[0].expiresAt.slice(0, 16).replace('T', ' ')} 自动清理）` : '';
        count.textContent = `共 ${items.length} 条最近删除记录${retention}`;
        toolbar.appendChild(count);
        utilityBody.appendChild(toolbar);
        const hint = document.createElement('p');
        hint.className = 'utility-hint';
        hint.textContent = '删除的项目和任务会按设置里的保留天数自动清理；'
            + '恢复或删除都可以逐条操作，也可以勾选后批量处理（恢复不了原位置的会进「孤立任务箱」）。';
        utilityBody.appendChild(hint);
        if (items.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'utility-empty';
            empty.textContent = '最近删除的项目会出现在这里';
            utilityBody.appendChild(empty);
            return;
        }
        const actionBar = document.createElement('div');
        actionBar.className = 'utility-actions trash-action-bar';
        const selectAll = document.createElement('button');
        selectAll.type = 'button';
        selectAll.className = 'utility-secondary-btn';
        selectAll.textContent = '全选';
        const restoreMany = document.createElement('button');
        restoreMany.type = 'button';
        restoreMany.className = 'utility-primary-btn';
        restoreMany.textContent = '批量恢复';
        restoreMany.disabled = true;
        const deleteMany = document.createElement('button');
        deleteMany.type = 'button';
        deleteMany.className = 'utility-secondary-btn';
        deleteMany.textContent = '批量删除';
        deleteMany.disabled = true;
        const purgeAll = document.createElement('button');
        purgeAll.type = 'button';
        purgeAll.className = 'utility-secondary-btn';
        purgeAll.textContent = '立即清空回收站';
        actionBar.append(selectAll, restoreMany, deleteMany, purgeAll);
        utilityBody.appendChild(actionBar);

        const updateSelectionUi = () => {
            restoreMany.disabled = selected.size === 0;
            deleteMany.disabled = selected.size === 0;
            selectAll.textContent = selected.size === items.length ? '取消全选' : '全选';
        };
        selectAll.addEventListener('click', () => {
            if (selected.size === items.length) selected.clear();
            else items.forEach(item => selected.add(item.id));
            list.querySelectorAll('input[type="checkbox"]').forEach(box => { box.checked = selected.has(box.dataset.id); });
            updateSelectionUi();
        });

        const runBatch = async (action, confirmText, successText) => {
            if (selected.size === 0) return;
            if (!window.confirm(`${confirmText}（共 ${selected.size} 条）`)) return;
            if (action === 'delete-many' || action === 'purge') {
                await createSnapshot('before-trash-purge');
            }
            try {
                const response = await apiFetch('/api/trash', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action, ids: [...selected] })
                });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(payload.error || '批量操作失败，请重试');
                trashItems = payload.items || [];
                const failed = payload.failed || [];
                if (Array.isArray(payload.projects)) {
                    projects = payload.projects.map(normalizeProjectSummary);
                    renderProjects();
                }
                renderTrashItems(trashItems);
                showToast(failed.length > 0
                    ? `${successText} ${selected.size - failed.length} 条，${failed.length} 条失败：${failed[0].error}`
                    : `${successText} ${selected.size} 条`);
            } catch (error) {
                showToast(error.message || '批量操作失败，请重试');
            }
        };
        restoreMany.addEventListener('click', () => runBatch('restore-many', '确认恢复选中的记录？', '已恢复'));
        deleteMany.addEventListener('click', () => runBatch('delete-many', '确认永久删除选中的记录？此操作不可撤销', '已永久删除'));
        purgeAll.addEventListener('click', async () => {
            if (!window.confirm('确认立即清空回收站？所有记录将被永久删除，无法恢复（会先自动生成完整快照）。')) return;
            await createSnapshot('before-trash-purge');
            try {
                const response = await apiFetch('/api/trash', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'purge' })
                });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(payload.error || '清空回收站失败，请重试');
                trashItems = payload.items || [];
                renderTrashItems(trashItems);
                showToast(`已清空回收站（${payload.purged || 0} 条）`);
            } catch (error) {
                showToast(error.message || '清空回收站失败，请重试');
            }
        });

        const list = document.createElement('div');
        list.className = 'trash-list';
        const trashFragment = document.createDocumentFragment();
        items.forEach(item => {
            const card = document.createElement('div');
            card.className = 'trash-item';
            const head = document.createElement('label');
            head.className = 'trash-head';
            const box = document.createElement('input');
            box.type = 'checkbox';
            box.dataset.id = item.id;
            box.checked = selected.has(item.id);
            box.addEventListener('change', () => {
                if (box.checked) selected.add(item.id);
                else selected.delete(item.id);
                updateSelectionUi();
            });
            const title = document.createElement('strong');
            title.textContent = item.title || '未命名条目';
            head.append(box, title);
            const meta = document.createElement('small');
            meta.textContent = `${item.kind === 'project' ? '项目' : '任务'} · 删除于 ${(item.deletedAt || '').slice(0, 16).replace('T', ' ')}`
                + (item.expiresAt ? ` · ${item.expiresAt.slice(0, 10)} 自动清理` : '');
            const context = document.createElement('div');
            context.className = 'trash-context';
            context.textContent = item.context || item.projectId || '';
            const target = document.createElement('div');
            target.className = 'trash-target';
            if (item.restoreTarget === 'orphan') {
                target.textContent = '原位置已不存在：恢复后会放进「孤立任务箱」';
            } else if (item.restoreTarget === 'unavailable') {
                target.textContent = '原项目已不存在：无法恢复（可以永久删除）';
            } else if (item.restoreTarget === 'conflict') {
                target.textContent = '同 ID 的项目已存在：恢复前需要先处理现有项目';
            } else {
                target.textContent = '恢复到删除前的位置';
            }
            if (item.restoreTarget === 'unavailable' || item.restoreTarget === 'conflict') {
                restoreBtn.disabled = true;
            }
            const actions = document.createElement('div');
            actions.className = 'trash-actions';
            const restoreBtn = document.createElement('button');
            restoreBtn.type = 'button';
            restoreBtn.className = 'utility-primary-btn';
            restoreBtn.textContent = '恢复';
            restoreBtn.addEventListener('click', async () => {
                if (!window.confirm(`确认恢复“${item.title || '未命名条目'}”？`)) return;
                try {
                    await restoreTrashItem(item.id);
                    renderTrashItems(trashItems);
                    showToast('已恢复');
                } catch (error) {
                    showToast(error.message || '恢复失败，请重试');
                }
            });
            const deleteBtn = document.createElement('button');
            deleteBtn.type = 'button';
            deleteBtn.className = 'utility-secondary-btn';
            deleteBtn.textContent = '删除';
            deleteBtn.addEventListener('click', async () => {
                if (!window.confirm('确认永久删除这条记录？此操作不可撤销（会先自动生成完整快照）。')) return;
                await createSnapshot('before-trash-purge');
                try {
                    await deleteTrashItemById(item.id);
                    renderTrashItems(trashItems);
                } catch (error) {
                    showToast(error.message || '删除失败，请重试');
                }
            });
            actions.append(restoreBtn, deleteBtn);
            card.append(head, meta, context, target, actions);
            trashFragment.appendChild(card);
        });
        list.replaceChildren(trashFragment);
        utilityBody.appendChild(list);
        updateSelectionUi();
    }

    async function openTrashBin() {
        showUtilityModal('回收站', '最近删除');
        renderUtilityMessage('正在读取回收站…');
        try {
            const items = await loadTrashItems();
            renderTrashItems(items);
        } catch (error) {
            renderUtilityMessage(error.message || '读取回收站失败，请重试');
        }
    }

    async function openGlobalSearch() {
        showUtilityModal('全局搜索', '跨项目');
        utilityBody.innerHTML = '';
        const toolbar = document.createElement('div');
        toolbar.className = 'utility-toolbar';
        const search = document.createElement('input');
        search.type = 'search';
        search.className = 'memo-search';
        search.placeholder = '搜索项目名、描述、周、单元、任务';
        const meta = document.createElement('span');
        meta.textContent = '正在加载全部项目…';
        toolbar.append(search, meta);
        utilityBody.appendChild(toolbar);
        const results = document.createElement('div');
        results.className = 'search-results';
        utilityBody.appendChild(results);
        // 搜索交给服务端（SQL LIKE + 递归 CTE）：不再为了搜索把每个项目的整棵树拉下来。
        meta.textContent = '输入关键词开始搜索';
        let searchToken = 0;
        const render = async () => {
            const token = ++searchToken;
            results.innerHTML = '';
            const query = search.value.trim();
            if (!query) {
                meta.textContent = '输入关键词后可跨项目搜索';
                const empty = document.createElement('p');
                empty.className = 'utility-empty';
                empty.textContent = '输入关键词后可跨项目搜索';
                results.appendChild(empty);
                return;
            }
            meta.textContent = '搜索中…';
            let matched = [];
            try {
                const response = await apiFetch(
                    `/api/search?q=${encodeURIComponent(query)}&limit=100`, { cache: 'no-store' });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(payload.error || '搜索失败');
                matched = Array.isArray(payload.results) ? payload.results : [];
            } catch (error) {
                if (token !== searchToken) return;
                const message = listStatusText('search', 'failed', error && error.message);
                meta.textContent = message;
                const failed = document.createElement('p');
                failed.className = 'utility-empty';
                failed.textContent = message;
                results.appendChild(failed);
                results.appendChild(createRetryButton('重试', () => render()));
                return;
            }
            if (token !== searchToken) return;   // 已经有更新的关键词，丢弃这次结果
            meta.textContent = `找到 ${matched.length} 条结果`;
            if (matched.length === 0) {
                const empty = document.createElement('p');
                empty.className = 'utility-empty';
                empty.textContent = '没有找到匹配项';
                results.appendChild(empty);
                return;
            }
            matched.forEach(item => {
                const row = document.createElement('button');
                row.type = 'button';
                row.className = 'search-result';
                const title = document.createElement('strong');
                title.textContent = item.label;
                const detail = document.createElement('small');
                detail.textContent = item.kind === 'project'
                    ? `项目 · ${item.detail || ''}`
                    : `任务 · ${item.detail || ''}`;
                row.append(title, detail);
                row.addEventListener('click', async () => {
                    if (item.kind === 'project') {
                        await openProjectDetail(item.projectId);
                        closeUtilityModal();
                    } else {
                        await locateStudyTask(item.projectId, {
                            id: item.nodeId,
                            text: item.label,
                            ancestorIds: item.ancestorIds || [],
                            path: item.detail || '',
                            optional: false
                        });
                    }
                });
                results.appendChild(row);
            });
        };
        search.addEventListener('input', debounce(render, SEARCH_DEBOUNCE_MS));
        render();
        search.focus();
    }


    function toggleExtraAsk() {
        if (!extraAsk) return;
        extraAsk.hidden = !extraAsk.hidden;
    }
    function closeExtraAsk() {
        if (extraAsk) extraAsk.hidden = true;
    }
    async function generateExtraQuestions() {
        if (!assessmentNode) return;
        const count = Math.max(1, Math.min(5, Number(extraCount.value) || 1));
        const weakPoint = assessmentQuestionItems[assessmentQuestionIndex] || '';
        extraConfirmBtn.disabled = true;
        const label = extraConfirmBtn.textContent;
        extraConfirmBtn.textContent = '生成中…';
        try {
            const response = await apiFetch('/api/question', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    taskId: assessmentNode.id,
                    task: assessmentNode.text,
                    context: getAssessmentContext(assessmentNode),
                    model: assessmentModel.value,
                    files: await getAssessmentFilePayload(),
                    count,
                    weakPoint,
                    priorSummary: buildPriorSummary()
                })
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || !Array.isArray(payload.questions) || payload.questions.length < count) {
                throw new Error(payload.error || 'AI 未生成足够题目');
            }
            const extra = payload.questions.slice(0, count).map(String);
            assessmentQuestionItems = assessmentQuestionItems.concat(extra);
            assessmentNode.assessment = {
                ...(assessmentNode.assessment || {}),
                questionSet: assessmentQuestionItems,
                model: assessmentModel.value
            };
            await saveProjects();
            renderAssessmentQuestions();
            closeExtraAsk();
            showToast('已追加 ' + extra.length + ' 道拟题（当前共 ' + assessmentQuestionItems.length + ' 题）');
        } catch (error) {
            showToast(error.message || '生成拟题失败，请重试');
        } finally {
            extraConfirmBtn.disabled = false;
            extraConfirmBtn.textContent = label;
        }
    }


    function buildPlanTree(nodes) {
        return (nodes || []).map((node) => {
            const base = {
                id: generateId(),
                type: node.type === 'day' ? 'day' : node.type === 'item' ? 'item' : 'week',
                text: String(node.text || '未命名内容'),
                completed: false,
                expanded: false,
                createdAt: todayStr(),
                children: []
            };
            if (base.type === 'item') {
                base.optional = Boolean(node.optional);
                base.assessmentRequired = Boolean(newProjectAiToggle.checked);
                base.assessment = null;
                base.assessmentHistory = 0;
            } else {
                base.children = buildPlanTree(node.children || []);
            }
            return base;
        });
    }


    function updateBranch(node, li) {
        if (!node || !li) return;
        if (isNodeFiltering()) { renderDetail(); return; }
        node.expanded = !node.expanded;
        const arrow = li.querySelector(':scope > .node-row .arrow');
        if (arrow) arrow.classList.toggle('expanded', node.expanded);
        const ul = li.querySelector(':scope > .children');
        if (!ul) return;
        if (node.expanded) {
            ul.classList.add('expanded');
            if (ul.childElementCount === 0) {
                const project = getCurrentProject();
                const projectCreatedAt = project ? (project.createdAt || '') : '';
                const branchFragment = document.createDocumentFragment();
                (node.children || []).forEach(child => {
                    branchFragment.appendChild(renderNode(child, projectCreatedAt, false));
                });
                ul.appendChild(branchFragment);
            }
        } else {
            ul.classList.remove('expanded');
        }
    }

    function nodeByIdMap(project) {
        const map = {};
        function walk(nodes) {
            for (const n of nodes || []) {
                if (n && n.id != null) map[String(n.id)] = n;
                if (n && n.children) walk(n.children);
            }
        }
        walk(project && project.tree);
        return map;
    }
    function setRowCompletionVisual(li, node) {
        if (!li || !node) return;
        const row = li.querySelector(':scope > .node-row');
        if (!row) return;
        const state = getNodeCompletionState(node);
        row.classList.toggle('completed-row', state === 'completed');
        const cb = row.querySelector('.checkbox');
        if (cb) {
            cb.classList.toggle('checked', state === 'completed');
            cb.classList.toggle('indeterminate', state === 'partial');
            cb.setAttribute('aria-checked', state === 'partial' ? 'mixed' : (state === 'completed' ? 'true' : 'false'));
        }
        const text = row.querySelector('.node-text');
        if (text) text.classList.toggle('completed-text', state === 'completed');
        const anchor = row.querySelector('.node-date') || row.lastElementChild;
        const oldLearning = row.querySelector('.node-learning-badge');
        const oldDate = row.querySelector('.node-review-date');
        const hasLearning = node.type === 'item' && node.review && node.review.learning;
        const hasDue = node.type === 'item' && node.review && node.review.due;
        if (hasLearning) {
            if (!oldLearning) {
                const badge = document.createElement('span');
                badge.className = 'node-learning-badge';
                badge.textContent = '需重学';
                row.insertBefore(badge, anchor);
            }
        } else if (oldLearning) {
            oldLearning.remove();
        }
        if (!hasLearning && hasDue) {
            if (!oldDate) {
                const span = document.createElement('span');
                span.className = 'node-review-date';
                span.textContent = '复习 ' + node.review.due.slice(5);
                row.insertBefore(span, anchor);
            }
        } else if (oldDate) {
            oldDate.remove();
        }
    }
    function refreshItemCompletion(project, node) {
        if (!project || !node || node.type !== 'item' || isNodeFiltering()) {
            // 没有打开项目时（例如从今日工作台直接完成任务）不要顺手切回列表页
            if (project) renderDetail();
            return;
        }
        let li = null;
        const all = document.querySelectorAll('#detailView .tree-node');
        for (const el of all) {
            if (String(el.dataset.id) === String(node.id)) { li = el; break; }
        }
        if (!li) { renderDetail(); return; }
        const map = nodeByIdMap(project);
        setRowCompletionVisual(li, node);
        let cursor = li.parentElement;
        while (cursor) {
            const up = cursor.parentElement;
            if (!up) break;
            if (up.classList && up.classList.contains('tree-node')) {
                const pid = String(up.dataset.id);
                if (pid && map[pid]) setRowCompletionVisual(up, map[pid]);
                cursor = up.parentElement;
            } else {
                break;
            }
        }
        const remaining = getProjectRemaining(project);
        const optional = getProjectOptionalStats(project);
        const count = document.getElementById('countDisplay');
        if (count) count.textContent = '主线剩余 ' + remaining + ' 项 · 选做 ' + optional.completed + '/' + optional.total;
    }
    function refreshAfterToggle(project, node) {
        try {
            refreshItemCompletion(project, node);
        } catch (err) {
            console.warn('局部刷新失败，退回整树重绘', err);
            renderDetail();
        }
    }

    const debouncedRenderProjects = debounce(renderProjects, SEARCH_DEBOUNCE_MS);
    const debouncedRenderDetail = debounce(renderDetail, SEARCH_DEBOUNCE_MS);

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
        if (extraQuestionBtn) extraQuestionBtn.addEventListener('click', toggleExtraAsk);
        if (extraConfirmBtn) extraConfirmBtn.addEventListener('click', generateExtraQuestions);
        if (extraCancelBtn) extraCancelBtn.addEventListener('click', closeExtraAsk);
        if (copyQuestionBtn) copyQuestionBtn.addEventListener('click', copyCurrentQuestion);
        if (summaryQuestionBtn) summaryQuestionBtn.addEventListener('click', generateSummary);
        if (openSummaryBtn) openSummaryBtn.addEventListener('click', openSummaryList);
        if (globalSearchBtn) globalSearchBtn.addEventListener('click', openGlobalSearch);
        if (openTrashBtn) openTrashBtn.addEventListener('click', openTrashBin);
        if (assessmentTemplateConclusionBtn) assessmentTemplateConclusionBtn.addEventListener('click', () => insertAssessmentTemplate('conclusion'));
        if (assessmentTemplateExplainBtn) assessmentTemplateExplainBtn.addEventListener('click', () => insertAssessmentTemplate('explain'));
        if (assessmentTemplateCodeBtn) assessmentTemplateCodeBtn.addEventListener('click', () => insertAssessmentTemplate('code'));
        if (assessmentRestoreBtn) assessmentRestoreBtn.addEventListener('click', restoreAssessmentSubmission);
        if (manageTemplatesBtn) manageTemplatesBtn.addEventListener('click', openTemplateManager);
        renderCustomTemplates();
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
            debouncedRenderProjects();
        });
        projectStatusFilter.addEventListener('change', () => {
            projectFilters.status = projectStatusFilter.value;
            renderProjects();
        });
        nodeSearchInput.addEventListener('input', () => {
            nodeFilters.query = nodeSearchInput.value;
            debouncedRenderDetail();
        });
        nodeStatusFilter.addEventListener('change', () => {
            nodeFilters.status = nodeStatusFilter.value;
            renderDetail();
        });
        nodePriorityFilter.addEventListener('change', () => {
            nodeFilters.priority = nodePriorityFilter.value;
            renderDetail();
        });
        nodeDueFilter.addEventListener('change', () => {
            nodeFilters.due = nodeDueFilter.value;
            renderDetail();
        });
        nodeTagFilter.addEventListener('input', debounce(() => {
            nodeFilters.tag = nodeTagFilter.value;
            renderDetail();
        }, SEARCH_DEBOUNCE_MS));
        batchToggleBtn.addEventListener('click', () => setBatchMode(!batchState.active));
        saveViewBtn.addEventListener('click', saveCurrentView);
        projectArchiveBtn.addEventListener('click', () => {
            if (currentProjectId) toggleProjectArchived(currentProjectId);
        });
        saveStatus.addEventListener('click', () => {
            if (saveConflict) openConflictPanel();
        });
        saveStatus.title = '有版本冲突时点这里解决';
        if (undoBtn) undoBtn.addEventListener('click', () => performUndo());
        if (redoBtn) redoBtn.addEventListener('click', () => performRedo());
        if (duplicateProjectBtn) duplicateProjectBtn.addEventListener('click', duplicateCurrentProject);
        if (saveTemplateBtn) saveTemplateBtn.addEventListener('click', saveCurrentProjectAsTemplate);
        if (createFromTemplateBtn) createFromTemplateBtn.addEventListener('click', () => {
            const templateId = templateSelect ? templateSelect.value : '';
            if (!templateId) {
                showToast('请先选择一个模板');
                return;
            }
            createProjectFromTemplate(templateId);
        });
        if (runAutoArchiveBtn) runAutoArchiveBtn.addEventListener('click', runAutoArchiveFromUi);
        if (saveSettingsBtn) saveSettingsBtn.addEventListener('click', saveSettingsFromUi);
        if (refreshActivityBtn) refreshActivityBtn.addEventListener('click', loadActivity);
        if (clearActivityBtn) clearActivityBtn.addEventListener('click', clearActivityFromUi);
        document.addEventListener('keydown', handleHistoryShortcut);
        exportBtn.addEventListener('click', () => exportBackup('json'));
        exportMarkdownBtn.addEventListener('click', () => exportBackup('markdown'));
        exportCsvBtn.addEventListener('click', () => exportBackup('csv'));
        downloadDatabaseBackupBtn.addEventListener('click', downloadDatabaseBackup);
        inspectDatabaseBackupBtn.addEventListener('click', inspectDatabaseBackupFromUi);
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
            if (backupListError) {
                loadDatabaseBackups();
                return;
            }
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
        createProjectBtn.addEventListener('click', async () => {
            const name = newProjectInput.value.trim();
            if (!name) return;
            const usePlan = newProjectPlanToggle ? newProjectPlanToggle.checked : false;
            const clearInputs = () => {
                newProjectInput.value = '';
                newProjectAiToggle.checked = false;
                if (newProjectPlanToggle) newProjectPlanToggle.checked = false;
            };
            const plainCreate = () => {
                const project = {
                    id: generateId(),
                    name: name,
                    description: '',
                    createdAt: todayStr(),
                    assessmentEnabled: Boolean(newProjectAiToggle.checked),
                    tree: []
                };
                projects.push(project);
                markProjectDirty(project);
                saveProjects();
                clearInputs();
                renderProjects();
            };
            if (!usePlan) {
                plainCreate();
                return;
            }
            createProjectBtn.disabled = true;
            const label = createProjectBtn.textContent;
            createProjectBtn.textContent = '规划中…';
            let plannedProject = null;
            try {
                const response = await apiFetch('/api/project/plan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ topic: name, model: 'flash' })
                });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok || !payload.plan) throw new Error(payload.error || 'AI 规划失败，请重试');
                plannedProject = {
                    id: generateId(),
                    name: name,
                    description: String(payload.plan.description || ''),
                    createdAt: todayStr(),
                    assessmentEnabled: Boolean(newProjectAiToggle.checked),
                    tree: buildPlanTree(payload.plan.tree || [])
                };
                projects.push(plannedProject);
                markProjectDirty(plannedProject);
            } catch (planError) {
                // 只有"规划请求本身"失败才退化成空项目；
                // 之后的保存/打开失败不能再建一个同名项目（会出现两个同名项目）。
                plainCreate();
                showToast('AI 规划失败，已创建空项目：' + (planError.message || ''));
                createProjectBtn.disabled = false;
                createProjectBtn.textContent = label;
                return;
            }
            clearInputs();
            try {
                await saveProjects();
                await openProjectDetail(plannedProject.id);
                showToast('已按 AI 规划创建项目');
            } catch (error) {
                // 项目已经建好并留在内存里（dirty 未清、离开守卫仍生效），只是这次没存进去。
                renderProjects();
                showToast('项目已创建，但保存失败：' + (error.message || '请检查本地服务'));
            } finally {
                createProjectBtn.disabled = false;
                createProjectBtn.textContent = label;
            }
        });
        newProjectInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') createProjectBtn.click();
        });
        backBtn.addEventListener('click', showProjectsView);
        // 顶栏「复习」打开复习页（分组 + 筛选）；页内的「开始今日复习」才进会话。
        reviewQueueBtn.addEventListener('click', () => { showReviewQueue(); });
        if (startReviewSessionBtn) {
            startReviewSessionBtn.addEventListener('click', () => { startReviewSession(); });
        }
        [reviewTypeFilter, reviewModuleFilter].forEach(select => {
            if (select) select.addEventListener('change', () => { showReviewQueue(); });
        });
        if (reviewScopeFilter) {
            // 范围筛选只重渲染分组，不重新拉取数据；但顶部统计的"范围筛选只收窄分组"标注
            // 依赖当前 scope，所以这里也要同步刷新一次文案。
            reviewScopeFilter.addEventListener('change', () => {
                renderReviewGroups();
                reviewSubline.textContent = reviewSublineText(reviewQueueState.summary || {},
                    reviewQueueState.items || []);
            });
        }
        reviewBackBtn.addEventListener('click', () => { showProjectsView(); });
        // 更多工具 →「知识点库」；库里的返回回到复习页（两页共用同一份 points 数据）。
        openKnowledgeBtn.addEventListener('click', () => { showKnowledgeLibrary(); });
        knowledgeBackBtn.addEventListener('click', () => { showReviewQueue(); });
        knowledgeSearch.addEventListener('input', () => renderKnowledgeList());
        [knowledgeModuleFilter, knowledgeLevelFilter].forEach(select => {
            if (select) select.addEventListener('change', () => renderKnowledgeList());
        });
        reviewSessionExitBtn.addEventListener('click', () => { saveReviewDraft(); saveReviewSession(); showReviewQueue(); });
        reviewRevealBtn.addEventListener('click', revealReviewAnswer);
        reviewAnswerInput.addEventListener('input', () => {
            clearTimeout(reviewDraftTimer);
            reviewDraftTimer = setTimeout(saveReviewDraft, 500);
        });
        reviewGradeButtons.addEventListener('click', (event) => {
            const button = event.target.closest('.review-grade-btn');
            if (button) gradeReviewQuestion(Number(button.dataset.grade));
        });
        workbenchBackBtn.addEventListener('click', () => { showProjectsView(); });
        workbenchRefreshBtn.addEventListener('click', () => showWorkbench());
        openWorkbenchBtn.addEventListener('click', () => showWorkbench());
        openRecentBtn.addEventListener('click', () => showRecent());
        quickAddBtn.addEventListener('click', () => quickAddToInbox());
        reminderToggleBtn.addEventListener('click', () => toggleReminders());
        reminderPermissionBtn.addEventListener('click', () => requestNotificationPermission());
        quickAddInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                quickAddToInbox();
            }
        });
        if (projectReviewToggle) {
            projectReviewToggle.addEventListener('change', () => {
                const reviewProject = getCurrentProject();
                if (!reviewProject) return;
                reviewProject.reviewEnabled = projectReviewToggle.checked;
                markProjectDirty(reviewProject);
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
            markProjectDirty(project);
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
            markProjectDirty(project);
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
        loadSavedViews();
        loadReminderSettings();
        renderReminderStatus();
        loadUndoStack();
        loadTemplates();
        loadSettings();
        loadActivity();
        if (reminderState.enabled) startReminders();
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
