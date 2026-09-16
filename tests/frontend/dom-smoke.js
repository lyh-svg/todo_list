// 前端运行时冒烟测试：用最小 DOM 桩真实加载 index.html + api-client.js + study-tools.js + app.js，
// 然后模拟点击（今日工作台 → 返回、打开项目、完成任务、打开元数据、批量模式、快速添加、提醒开关、
// 复习会话：开始复习 → 先回忆 → 揭示答案 → 五档自评），
// 断言：① 任何一步都不抛异常；② 任意时刻只有一个视图处于 active。
//
// 只读：不修改仓库文件。
const fs = require('fs');
const ROOT = require('path').resolve(__dirname, '..', '..');
const vm = require('vm');

const html = fs.readFileSync(`${ROOT}/index.html`, 'utf8');
const today = (() => {
    const d = new Date();
    const p = v => String(v).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
})();

// ---------------- DOM 桩 ----------------
let uuidCounter = 0;
function makeEl(tag = 'div', id = '') {
    const el = {
        _tag: tag, id, _children: [], _listeners: {},
        // className 必须和 classList 同步：运行时创建的行是直接赋 className 的，
        // 不同步的话 findAll(..., classList.contains('node-row')) 永远找不到它们。
        get className() { return [...this.classList._s].join(' '); },
        set className(value) {
            this.classList._s = new Set(String(value || '').split(/\s+/).filter(Boolean));
        },
        textContent: '', innerHTML: '', value: '', checked: false,
        hidden: false, disabled: false, type: '', title: '', placeholder: '', href: '', download: '',
        selectedIndex: 0, options: [], files: [], dataset: {}, style: {}, tabIndex: 0,
        scrollTop: 0, scrollHeight: 0, offsetHeight: 32, maxLength: 0, rows: 0,
        classList: {
            _s: new Set(),
            add(...names) { names.forEach(n => this._s.add(n)); },
            remove(...names) { names.forEach(n => this._s.delete(n)); },
            toggle(name, force) {
                const on = force === undefined ? !this._s.has(name) : Boolean(force);
                if (on) this._s.add(name); else this._s.delete(name);
                return on;
            },
            contains(name) { return this._s.has(name); },
        },
        setAttribute() {}, getAttribute() { return null; }, removeAttribute() {},
        hasAttribute() { return false; }, focus() {}, blur() {}, scrollIntoView() {}, click() { this.dispatch('click'); },
        addEventListener(type, fn) { (this._listeners[type] ||= []).push(fn); },
        removeEventListener(type, fn) { this._listeners[type] = (this._listeners[type] || []).filter(f => f !== fn); },
        // 真实 DOM 的事件会冒泡：复习自评/批量操作都用容器上的事件委托。
        // 桩以前只在目标元素自身跑监听器，委托处理器永远不会被触发。
        dispatch(type, event = {}) {
            const evt = {
                type, target: this, currentTarget: this,
                stopPropagation() { evt._stopped = true; }, preventDefault() {}, key: '',
                ...event,
            };
            let node = this;
            while (node) {
                (node._listeners[type] || []).forEach(fn => fn({ ...evt, currentTarget: node }));
                if (evt._stopped) break;
                node = node._parentElement || null;
            }
        },
        appendChild(child) { if (child) { child.parentElement = this; this._children.push(child); } return child; },
        append(...children) { children.forEach(c => this.appendChild(c)); },
        replaceChildren(...children) {
            this._children = [];
            children.forEach(c => {
                if (c && c._isFragment) (c._children || []).forEach(x => this.appendChild(x));
                else this.appendChild(c);
            });
        },
        insertBefore(child) { return this.appendChild(child); },
        remove() { if (this.parentElement) this.parentElement._children = this.parentElement._children.filter(c => c !== this); },
        querySelector(selector) {
            const text = String(selector).trim();
            const scopeChild = /^:scope\s*>\s*\.([\w-]+)$/.exec(text);
            if (scopeChild) {
                return (this.children || []).find(child => child.classList.contains(scopeChild[1])) || null;
            }
            const dataAttr = /^\[data-([\w-]+)\]$/.exec(text);
            if (dataAttr) {
                const key = dataAttr[1].replace(/-(\w)/g, (m, c) => c.toUpperCase());
                // 真实 HTML 里这些 data-* 在嵌套的 backdrop 上，必须递归找
                const found = findAll(this, child => child.dataset && child.dataset[key] !== undefined);
                if (found.length > 0) return found[0];
            }
            const classOnly = /^\.([\w-]+)$/.exec(text);
            if (classOnly) {
                const found = findAll(this, child => child.classList.contains(classOnly[1]));
                if (found.length > 0) return found[0];
            }
            this._qsCache = this._qsCache || new Map();
            if (!this._qsCache.has(text)) this._qsCache.set(text, makeEl('div', text));
            return this._qsCache.get(text);
        },
        querySelectorAll(selector) {
            const classOnly = /^\.([\w-]+)$/.exec(String(selector).trim());
            if (classOnly) return findAll(this, child => child.classList.contains(classOnly[1]));
            return [];
        },
        // 真实 DOM 会顺着祖先链找匹配元素：顶栏/列表的批量选中与复习自评都靠它。
        // 桩以前直接返回 null，事件委托就没法被测到。
        closest(selector) {
            const text = String(selector || '').trim();
            const classOnly = /^\.([\w-]+)$/.exec(text);
            const idOnly = /^#([\w-]+)$/.exec(text);
            let node = this;
            while (node) {
                if (classOnly && node.classList.contains(classOnly[1])) return node;
                if (idOnly && node.id === idOnly[1]) return node;
                if (!classOnly && !idOnly && node._tag === text) return node;
                node = node._parentElement || null;
            }
            return null;
        },
        getContext() { return { drawImage() {}, clearRect() {}, fillRect() {} }; },
        toBlob(cb) { cb(null); },
        getBoundingClientRect() { return { top: 0, left: 0, width: 100, height: 20 }; },
        get childElementCount() { return this._children.length; },
        get children() { return this._children; },
        get firstChild() { return this._children[0] || null; },
        get parentNode() { return this.parentElement; },
        get parentElement() { return this._parentElement || (this._parentElement = makeEl('span')); },
        set parentElement(value) { this._parentElement = value; },
    };
    return el;
}

// 桩以前把每个带 id 的标签都建成孤立元素，textOf(view) 永远只看到视图元素自己的 textContent，
// 于是「揭示前/后整个视图里有没有答案」这种断言形同虚设。这里按标签顺序重建父子关系：
// 带 id 的元素都进树；无 id 但直接挂在 id 元素下的元素也进树（只到这一层，
// 否则 index.html 里几十个纯样式 div 会挤进 children，把既有断言的计数搅乱）。
const elementsById = new Map();
{
    const tokenRe = /<(\/?)([a-zA-Z][\w-]*)((?:"[^"]*"|[^>"])*)>/g;
    const stack = [{ depth: 0, el: null, loose: false }];
    const VOID_TAGS = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
        'meta', 'param', 'source', 'track', 'wbr']);
    let match;
    while ((match = tokenRe.exec(html)) !== null) {
        const closing = match[1] === '/';
        const tagName = match[2].toLowerCase();
        const attrs = match[3] || '';
        const parent = stack[stack.length - 1];
        if (closing) {
            while (stack.length > 1 && stack[stack.length - 1].depth > parent.depth) stack.pop();
            if (stack.length > 1) stack.pop();
            continue;
        }
        const idMatch = /\sid="([^"]+)"/.exec(attrs);
        const classMatch = /\sclass="([^"]*)"/.exec(attrs);
        const wantsElement = Boolean(idMatch) || (Boolean(classMatch) && Boolean(parent.el) && !parent.loose);
        let el = null;
        if (wantsElement && !(idMatch && elementsById.has(idMatch[1]))) {
            el = makeEl(tagName, idMatch ? idMatch[1] : '');
            if (classMatch) classMatch[1].split(/\s+/).filter(Boolean).forEach(name => el.classList.add(name));
            // data-* 与 id 无关：五档自评按钮没有 id，只有 data-grade。
            // 以前把解析放在 `if (idMatch)` 里面，dataset.grade 恒为 undefined →
            // Number(undefined)=NaN → 请求体里是 grade:null，断言却照样通过。
            for (const dataMatch of attrs.matchAll(/data-([\w-]+)="([^"]*)"/g)) {
                const key = dataMatch[1].replace(/-(\w)/g, (m, c) => c.toUpperCase());
                el.dataset[key] = dataMatch[2];
            }
            if (idMatch) {
                if (/\shidden(\s|>|$)/.test(attrs)) el.hidden = true;
                elementsById.set(idMatch[1], el);
            }
            if (parent.el) parent.el.appendChild(el);
        }
        const selfClosing = /\/\s*$/.test(attrs) || VOID_TAGS.has(tagName);
        if (!selfClosing) stack.push({ depth: tokenRe.lastIndex, el, loose: Boolean(el) ? !idMatch : parent.loose });
    }
}

const documentListeners = {};
const documentStub = {
    readyState: 'complete', hidden: false, title: '测试',
    body: makeEl('body'), documentElement: makeEl('html'),
    createElement: tag => makeEl(tag),
    createDocumentFragment: () => { const f = makeEl('#fragment'); f._isFragment = true; return f; },
    getElementById: id => elementsById.get(id) || null,
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: (type, fn) => { (documentListeners[type] ||= []).push(fn); },
    removeEventListener: () => {},
    dispatch(type, event = {}) { (documentListeners[type] || []).forEach(fn => fn(event)); },
};
elementsById.set('app', documentStub.body);

// 验收弹窗以前从没被真正打开过（桩里项目 assessmentEnabled:false、任务 assessmentRequired:false），
// 于是下面两处 DOM 缺失一直没暴露，一打开验收就抛异常：
// ① assessmentFiles 跨了两层 class（.assessment-code-tools > label > input），而解析器只保留
//    "id 元素 + 直接挂在 id 元素下的一层 class 元素"，closest('.assessment-code-tools') 返回 null；
// ② .assessment-consent 没有 id，document.querySelector 恒返回 null。
// 这里补上真实祖先链，验收路径才能被冒烟真正覆盖（而不是靠关掉验收假绿）。
{
    const codeTools = makeEl('div');
    codeTools.classList.add('assessment-code-tools');
    const uploadLabel = makeEl('label');
    uploadLabel.classList.add('assessment-upload-btn');
    elementsById.get('assessmentForm').appendChild(codeTools);
    codeTools.appendChild(uploadLabel);
    uploadLabel.appendChild(elementsById.get('assessmentFiles'));
}
const assessmentConsent = makeEl('div');
assessmentConsent.classList.add('assessment-consent');
const defaultQuerySelector = documentStub.querySelector;
documentStub.querySelector = selector => (
    selector === '.assessment-consent' ? assessmentConsent : defaultQuerySelector(selector));

function storageStub() {
    const store = new Map();
    return {
        getItem: key => (store.has(key) ? store.get(key) : null),
        setItem: (key, value) => store.set(key, String(value)),
        removeItem: key => store.delete(key),
        clear: () => store.clear(),
    };
}

class URLSearchParamsStub {
    constructor(search = '') {
        this.params = new Map();
        String(search).replace(/^\?/, '').split('&').filter(Boolean).forEach(pair => {
            const [key, value = ''] = pair.split('=');
            this.params.set(decodeURIComponent(key), decodeURIComponent(value));
        });
    }
    get(name) { return this.params.has(name) ? this.params.get(name) : null; }
    set(name, value) { this.params.set(name, String(value)); }
    toString() { return [...this.params].map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&'); }
}

class HeadersStub {
    // 真实 Headers 的名字大小写不敏感：桩以前按精确 key 存，于是
    // streamEvaluate 用 headers.get('content-type') 拿不到 'Content-Type'，
    // 明明该走 JSON 分支却掉进"浏览器不支持流式读取"——验收提交永远失败。
    constructor(init) {
        this.map = new Map();
        if (init && init.forEach) init.forEach((v, k) => this.set(k, v));
        else Object.entries(init || {}).forEach(([k, v]) => this.set(k, v));
    }
    set(k, v) { this.map.set(String(k).toLowerCase(), v); }
    get(k) { const value = this.map.get(String(k).toLowerCase()); return value === undefined ? null : value; }
    has(k) { return this.map.has(String(k).toLowerCase()); }
}

// ---------------- fetch 桩 ----------------
const projectFixture = {
    id: 'p1', name: '测试项目', description: '', createdAt: today, assessmentEnabled: false, reviewEnabled: true,
    tree: [{
        id: 'w1', type: 'week', text: '第1周', completed: false, expanded: true, createdAt: today,
        children: [{
            id: 'd1', type: 'day', text: '单元1', completed: false, expanded: true, createdAt: today,
            children: [{
                id: 'i1', type: 'item', text: '任务一', completed: false, completedAt: null, optional: false,
                assessmentRequired: false, assessmentHistory: 0, assessment: null, createdAt: today,
                priority: 'high', dueDate: today, estimateMinutes: 30, tags: ['Python'], note: '备注', children: [],
            }],
        }, {
            // 服务端返回的 id 是 JSON 里的字符串（'1600'），而内置模板里是数字 1600 ——
            // 只比对数字会把队列当成"不存在"再插一份，导致保存时报"节点 ID 重复"。
            id: '1600', type: 'day', text: '补漏队列：基线测试薄弱点', completed: false, expanded: true, createdAt: today,
            children: [{
                id: '1601', type: 'item', text: '补漏任务', completed: false, completedAt: null, optional: false,
                assessmentRequired: false, assessmentHistory: 0, assessment: null, createdAt: today, children: [],
            }],
        }],
    }],
};
// 默认课程形态的项目（assessmentEnabled: true）：用来覆盖"勾选任务 → AI 验收 → 生成回流"这条默认路径。
// 列表里只给摘要、打开时才拉整棵树，所以验收场景拿到的必然是这份 assessmentRequired:true 的数据，
// 不会命中前面场景缓存的旧副本。
const assessProjectFixture = {
    id: 'p-assess', name: '验收项目', description: '', createdAt: today,
    assessmentEnabled: true, reviewEnabled: false,
    tree: [{
        id: 'w-assess', type: 'week', text: '第1周：验收', completed: false, expanded: true, createdAt: today,
        children: [{
            id: 'd-assess', type: 'day', text: '验收单元', completed: false, expanded: true, createdAt: today,
            children: [
                { id: 'i-skip', type: 'item', text: '跳过实现的任务', completed: false, completedAt: null,
                  optional: false, assessmentRequired: true, assessmentHistory: 0, createdAt: today,
                  assessment: { questionPassed: true, questionScore: 90 }, children: [] },
                { id: 'i-full', type: 'item', text: '完整通过的任务', completed: false, completedAt: null,
                  optional: false, assessmentRequired: true, assessmentHistory: 0, createdAt: today,
                  assessment: null, children: [] },
            ],
        }],
    }],
};
const workbenchFixture = {
    today, serverToday: today, horizonDays: 7,
    groups: {
        overdue: [], today: [{
            projectId: 'p1', projectName: '测试项目', nodeId: 'i1', text: '任务一', priority: 'high',
            dueDate: today, estimateMinutes: 30, tags: ['Python'], note: '备注',
            links: [{ label: '资料', url: 'https://example.com' }], repeat: { freq: 'daily', interval: 1 },
            path: '第1周 / 单元1', ancestorIds: ['w1', 'd1'],
        }],
        next7: [], reviewToday: [], inbox: [],
    },
    totals: { overdue: 0, today: 1, next7: 0, reviewToday: 0, inbox: 0 },
};
const fetchLog = [];
// 记录完整请求 URL：Task 11 的题型/模块筛选要断言查询参数真的带去后端了。
const fetchUrls = [];
// 记录整项目保存的请求体：用来断言「保存时不能出现重复节点 ID」这类数据完整性不变量
const projectPostBodies = [];
// 记录复习自评的请求体：断言"点第 3 个按钮 = 档位 3"，而不是只断言"发过这个请求"。
const reviewAnswerBodies = [];
// 记录 AI 判分的请求体：断言入口真的把当前题/答案 POST 给了 /api/review/ai-grade。
const reviewAiGradeBodies = [];
// 记录 /api/import 的请求体：断言导出文件里的 review 快照被原样转发（旧备份不能凭空多出该键）。
const importBodies = [];
// 记录 /api/import/preview 的请求体：预览走 5MiB 小限额分支且后端不消费 review，
// 带上它会在大 projects 上直接 413 → 确认按钮被禁用；这里断言它一定不含该键。
const previewBodies = [];
// 模拟"没配置 AI key"：置 true 后 /api/review/ai-grade 返回 503（走 toast 分支）。
let aiGradeUnavailable = false;
// null 表示用默认的「还有缺漏」verdict；测试用它切换 correct:true / 空 verdict 两个分支。
let aiGradeVerdict = null;
// 记录生成回流的请求体：验收失败必须带 remedial:true + gap，验收通过则不带。
const reviewGenerateBodies = [];
// 记录生成回流每次请求的 options：断言 keepalive:true（关页/刷新不丢请求）。
const reviewGenerateOptions = [];
// 非 null 时把 /api/review/generate 挂在可控 promise 上：用来断言调用处真的 await 了
// （没 await 时验收流程会立刻收尾，提交按钮提前恢复可用）。
let generateHold = null;
// 置 true 后 /api/review/generate 返回 500：断言生成回流失败只 warn，不阻断验收流程。
let generateFails = false;
async function fetchStub(url, options = {}) {
    const path = String(url).split('?')[0];
    fetchLog.push(`${options.method || 'GET'} ${path}`);
    fetchUrls.push(String(url));
    const reply = (status, payload) => ({
        ok: status >= 200 && status < 300, status,
        headers: new HeadersStub({ 'Content-Type': 'application/json' }),
        json: async () => payload, text: async () => JSON.stringify(payload), blob: async () => ({}),
    });
    if (path === '/api/projects') return reply(200, { projects: [
        { id: 'p1', name: '测试项目', description: '', createdAt: today, assessmentEnabled: false, archived: false, stats: { total: 1, remaining: 1, optionalTotal: 0, optionalCompleted: 0 }, _revision: 1 },
        { id: 'p-assess', name: '验收项目', description: '', createdAt: today, assessmentEnabled: true, archived: false, stats: { total: 2, remaining: 2, optionalTotal: 0, optionalCompleted: 0 }, _revision: 1 },
    ], reviewTotals: { today: 0, overdue: 0 }, serverToday: today, usedToday: today });
    if (path === '/api/project' && (options.method || 'GET') === 'POST' && options.body) {
        try { projectPostBodies.push(JSON.parse(options.body)); } catch (error) { fetchLog.push('BAD-BODY'); }
    }
    if (path === '/api/project') {
        // 真实服务按请求的 id 返回对应项目；桩也要保持一致，
        // 否则前端会发现"返回的 id 和当前项目 id 不一致"而退回列表页
        const requested = new URLSearchParamsStub(String(url).split('?')[1] || '').get('id') || 'p1';
        const base = requested === 'p-assess' ? assessProjectFixture : projectFixture;
        return reply(200, { project: { ...base, id: requested }, revision: 1 });
    }
    if (path === '/api/background') return reply(404, {});
    if (path === '/api/config') return reply(200, { ready: true, models: { flash: 'f', pro: 'p' }, error: '' });
    if (path === '/api/storage') return reply(200, { projectLimitBytes: 1000, largestProjectBytes: 10, projectCount: 1 });
    if (path === '/api/backups') return reply(200, {
        backups: [{ name: 'manual-20260915T000000000000.zip', kind: 'full', bytes: 2048,
                    modifiedAt: '2026-09-15T00:00:00', valid: true }]
    });
    if (path === '/api/import/preview') {
        if (options.body) {
            try { previewBodies.push(JSON.parse(options.body)); } catch (error) { fetchLog.push('BAD-BODY'); }
        }
        return reply(200, {
            ok: true,
            preview: {
                mode: 'replace', keepAiHistory: true, duplicates: [],
                newProjects: [{ id: 'imp-1', name: '导入的项目', itemCount: 1, completedCount: 0 }],
                updatedProjects: [], unchangedProjects: [],
                removedProjects: [{ id: 'old-1', name: '会被移除的项目' }],
                totals: { addedNodes: 1, updatedNodes: 0, keptLocalOnlyNodes: 0, deletedNodes: 2 },
                aiHistory: { nodesWithAssessment: 0, nodesWithReview: 0, policy: '保留' }
            }
        });
    }
    if (path === '/api/import') {
        if (options.body) {
            try { importBodies.push(JSON.parse(options.body)); } catch (error) { fetchLog.push('BAD-BODY'); }
        }
        return reply(200, { backup: 'before-import-smoke.zip',
        ok: true,
        // 导入响应是"导入后的完整项目列表"：真实服务会把已有项目一起回传，
        // 这里带上默认课程项目，后面的验收场景才有一个未缓存的默认课程可打开。
        projects: [{ id: 'imp-1', name: '导入的项目', description: '', createdAt: today,
                     assessmentEnabled: false, archived: false, reviewEnabled: false,
                     stats: { total: 1, remaining: 1, optionalTotal: 0, optionalCompleted: 0 }, _revision: 1 },
                   { id: 'p-assess', name: '验收项目', description: '', createdAt: today,
                     assessmentEnabled: true, archived: false, reviewEnabled: false,
                     stats: { total: 2, remaining: 2, optionalTotal: 0, optionalCompleted: 0 }, _revision: 1 }]
        });
    }
    if (path === '/api/project/plan') return reply(200, {
        ok: true,
        plan: { description: '冒烟用 AI 计划', tree: [{ type: 'week', text: '第1周：AI 规划', children: [
            { type: 'day', text: '单元1：入门', children: [{ type: 'item', text: 'AI 生成的任务' }] }] }] }
    });
    if (path === '/api/views') return reply(200, { views: [] });
    if (path === '/api/workbench') return reply(200, workbenchFixture);
    if (path === '/api/recent') return reply(200, { opened: [], modified: [], completed: [] });
    if (path === '/api/trash') {
        // 删除流程要求返回写入后的回收站条目；以前桩里没有 item，
        // storeTrashItem 会抛错，删除后半段（patch / 撤销）根本没被覆盖到。
        if ((options.method || 'GET') === 'POST') {
            return reply(200, { item: { id: 'trash-new', kind: 'node', title: '任务一' }, items: [] });
        }
        return reply(200, { items: [] });
    }
    if (path === '/api/settings') return reply(200, { settings: {
        trashRetentionDays: 7, autoArchiveEnabled: false, autoArchiveDays: 30,
        reviewDailyLimit: 10, reviewNewPerDay: 2 } });
    if (path === '/api/review/summary') return reply(200, { dueToday: 1, overdue: 1, upcoming: 0, weak: 1,
        total: 3, learned: 2, answeredToday: 0, streakDays: 3, limit: 10, newPerDay: 2,
        // 最近答错/最近掌握是"作答记录"：带题型/档位/日期/答案，复习页不能再靠知识点 lastGrade 兜底。
        // module 是模块筛选作用于这两组的前提（修复前记录里根本没有这个字段）。
        recentWrong: [{ id: 'a1', code: 'py.a.b', title: '答错的知识点', module: '容器', questionType: 'concept',
            grade: 1, answer: '我写错的答案', reviewedOn: '2026-09-10' }],
        recentMastered: [{ id: 'a2', code: 'py.a.d', title: '掌握的知识点', module: '函数', questionType: 'predict',
            grade: 5, answer: '我写对的答案', reviewedOn: '2026-09-12' }] });
    if (path === '/api/review/queue') return reply(200, { items: [{ code: 'py.a.b', title: '示例知识点',
        minutes: 10, module: '容器', level: '基础', questionType: 'predict',
        prompt: '写出下面代码的输出', body: 'def add(a, b):\n    return a + b\n\nprint(add(1, 2))',
        reason: 'overdue', due: '2026-09-01', taskId: '1103', projectId: 'p1' },
        { code: 'py.a.c', title: '示例知识点二',
        minutes: 10, module: '容器', level: '基础', questionType: 'debug',
        prompt: '找出下面代码的问题', body: 'def total(items=[]):\n    items.append(1)\n    return items',
        reason: 'today', due: today, taskId: '1104', projectId: 'p1' }],
        total: 2, truncated: false, limit: 10 });
    // 任务级到期（旧的 review_due 数据）仍走 /api/reviews：复习页要把它单独成组渲染出来。
    if (path === '/api/reviews') return reply(200, { due: [{ projectId: 'p1', projectName: '测试项目',
        ancestorIds: ['w1', 'd1'], path: '第1周 / 单元1', nodeId: 'i1', text: '任务一', due: today,
        learning: false }], future: [], truncated: false, limit: 50 });
    if (path === '/api/review/reveal') {
        // 按请求的题型返回对应的揭示内容：predict 和 debug 的题面代码不一样，
        // 桩里写死一份会让"第二题"的断言失去意义。
        let revealRequest = {};
        try { revealRequest = JSON.parse(options.body || '{}'); } catch (error) { revealRequest = {}; }
        // 知识点 code 在 reveal 里叫 pointCode（题面片段才叫 code），与
        // review_storage.reveal 的真实返回一致；两个都叫 code 会撞重复键。
        const predictReveal = { pointCode: 'py.a.b', type: 'predict', title: '示例知识点',
            prompt: '写出下面代码的输出', expected: ['[1]', '[1, 2]'],
            code: 'def add(a, b):\n    return a + b\n\nprint(add(1, 2))',
            explain: '第二次调用复用了同一个列表', pitfalls: ['可变默认参数'], history: [], state: null };
        const debugReveal = { pointCode: 'py.a.c', type: 'debug', title: '示例知识点二',
            prompt: '找出下面代码的问题', code: 'def total(items=[]):\n    items.append(1)\n    return items',
            rootCause: '可变默认参数被复用', fix: 'items=None 再兜底成 []',
            pitfalls: ['可变默认参数'], history: [], state: null };
        return reply(200, revealRequest.type === 'debug' ? debugReveal : predictReveal);
    }
    if (path === '/api/review/answer') {
        if (options.body) {
            try { reviewAnswerBodies.push(JSON.parse(options.body)); } catch (error) { fetchLog.push('BAD-BODY'); }
        }
        return reply(200, { ok: true, schedule: { due: '2026-09-30',
            intervalDays: 14, streak: 1, lapses: 0, weak: false, lastGrade: 4 } });
    }
    // 规格 §16 可选 AI 判分：默认模拟"已配置 key"，aiGradeUnavailable=true 时模拟 503。
    if (path === '/api/review/ai-grade') {
        if (options.body) {
            try { reviewAiGradeBodies.push(JSON.parse(options.body)); } catch (error) { fetchLog.push('BAD-BODY'); }
        }
        if (aiGradeUnavailable) return reply(503, { error: '未配置 AI，判分不可用（复习本身不受影响）' });
        // aiGradeVerdict 非 null 时用它（覆盖 correct:true / 空 verdict 两个边界分支）。
        return reply(200, { ok: true, verdict: aiGradeVerdict || {
            correct: false, missing: ['没有讲清第二次调用复用了同一个列表'],
            wrongAt: '把 add(1, 2) 的输出写成了 [1]',
            hint: '对照默认参数在定义时求值这一点',
        } });
    }
    if (path === '/api/review/session') return reply(200, { ok: true, sessionId: 's-review-1' });
    // 生成回流：第一次生成有新增（inserted 2），已挂过点的任务 inserted 0（前端应静默）。
    if (path === '/api/review/generate') {
        let request = {};
        try { request = JSON.parse(options.body || '{}'); } catch (error) { request = {}; }
        reviewGenerateBodies.push(request);
        // 记录 options：断言 keepalive 真的传到了 fetch（关页/刷新时请求也能发完）。
        reviewGenerateOptions.push({ method: options.method || 'GET', keepalive: options.keepalive === true });
        if (generateFails) return reply(500, { error: '生成失败（模拟）' });
        const fresh = request.taskId !== 'i-full';
        const payload = {
            ok: true,
            inserted: fresh ? 2 : 0,
            unchanged: fresh ? 0 : 2,
            created: [{ code: `py.ai.${request.taskId}.1`, title: '复习知识点' }],
            usedAi: false,
        };
        if (generateHold) {
            // 挂起：调用处 await 的话，验收流程会停在这里（提交按钮保持 disabled）。
            return new Promise(resolve => generateHold.push(() => resolve(reply(200, payload))));
        }
        return reply(200, payload);
    }
    // 验收出题：固定三道题（与真实 /api/question 契约一致）。
    if (path === '/api/question') return reply(200, {
        questions: ['验收题一：讲清机制', '验收题二：预测输出', '验收题三：定位 bug'], focus: '机制' });
    // 验收判分：回答写成 FAIL 就判不通过（用于覆盖"失败 → 补漏题"分支）。
    if (path === '/api/evaluate') {
        let request = {};
        try { request = JSON.parse(options.body || '{}'); } catch (error) { request = {}; }
        const failed = String(request.answer || '') === 'FAIL';
        return reply(200, { result: {
            passed: !failed, score: failed ? 40 : 92,
            summary: failed ? '没讲清核心机制' : '核心机制已讲清',
            reply: failed ? '再想一次求值时机' : '通过',
            strengths: [], problems: failed ? ['把自由变量当成全局变量'] : [],
            missingEvidence: [], nextAction: failed ? '补一个最小实验' : '',
        } });
    }
    if (path === '/api/review/points') return reply(200, { points: [{ code: 'py.a.b', title: '示例知识点',
        minutes: 10, module: '容器', level: '基础', origin: 'builtin', due: today, weak: true, lastGrade: 2,
        pitfalls: ['可变默认参数'] },
        { code: 'py.a.d', title: '已掌握的知识点', minutes: 8, module: '函数', level: '进阶', origin: 'builtin',
        due: '2026-10-01', weak: false, lastGrade: 5, pitfalls: [] }], total: 2, limit: 500, offset: 0 });
    if (path === '/api/review/history') return reply(200, { code: 'py.a.b', title: '示例知识点',
        module: '容器', level: '基础', minutes: 10, pitfalls: [], attempts: [], state: null });
    if (path === '/api/memos') return reply(200, { memos: [], databaseBytes: 0 });
    if (path === '/api/inbox/add') return reply(200, { ok: true, node: { ...projectFixture.tree[0].children[0].children[0], id: 'i-new', text: '新任务' }, revision: 2, projectId: 'inbox' });
    if (path === '/api/batch') return reply(200, { ok: true, changed: 1, spawned: 0, failed: [], projects: [] });
    if (path === '/api/heartbeat' || path === '/api/health') return reply(200, { ok: true });
    return reply(200, { ok: true });
}

// ---------------- 组装全局环境 ----------------
const timers = [];
let reloadCount = 0;
const windowStub = {
    document: documentStub, location: { protocol: 'http:', search: '', pathname: '/', hash: '', href: 'http://127.0.0.1:8765/', reload() { reloadCount += 1; } },
    history: { replaceState() {} },
    sessionStorage: storageStub(), localStorage: storageStub(),
    crypto: { randomUUID: () => `uuid-${++uuidCounter}` },
    fetch: fetchStub, Headers: HeadersStub, Notification: Object.assign(function Notification() {}, { permission: 'default', requestPermission: async () => 'granted' }),
    URL: Object.assign(function URL() {}, { createObjectURL: () => 'blob:stub', revokeObjectURL() {} }),
    Blob: class Blob {}, File: class File {}, FileReader: class FileReader {},
    TextDecoder, AbortController, URLSearchParams: URLSearchParamsStub, Promise, Math, Date, JSON, Object, Array,
    String, Number, Boolean, Map, Set, RegExp, Error, Symbol, WeakMap, Reflect, Proxy, Intl, isNaN, isFinite,
    parseInt, parseFloat, encodeURIComponent, decodeURIComponent, encodeURI, decodeURI, structuredClone,
    queueMicrotask: fn => setTimeout(fn, 0), performance: { now: () => Date.now() },
    btoa: value => Buffer.from(String(value), 'binary').toString('base64'),
    atob: value => Buffer.from(String(value), 'base64').toString('binary'),
    setTimeout: (fn, ms) => { const id = setTimeout(fn, Math.min(ms || 0, 5)); timers.push(id); return id; },
    clearTimeout, setInterval: () => 1, clearInterval() {}, requestAnimationFrame: fn => setTimeout(fn, 0),
    addEventListener() {}, removeEventListener() {}, getComputedStyle: () => ({ getPropertyValue: () => '' }),
    alert() {}, confirm: () => true, prompt: () => null, console,
    navigator: { userAgent: 'node' }, innerWidth: 1280, innerHeight: 800,
    TodoApiClient: undefined, TodoStudyTools: undefined,
};
windowStub.window = windowStub;
const sandbox = Object.assign(windowStub, { globalThis: windowStub });
vm.createContext(sandbox);

// ---------------- 加载脚本 ----------------
const failures = [];
const asyncErrors = [];
process.on('unhandledRejection', error => {
    asyncErrors.push(error && error.stack ? error.stack.split('\n').slice(0, 2).join(' | ') : String(error));
});
function loadScript(relative) {
    try {
        vm.runInContext(fs.readFileSync(`${ROOT}/${relative}`, 'utf8'), sandbox, { filename: relative });
        console.log(`   ✔ 加载 ${relative}`);
    } catch (error) {
        failures.push(`加载 ${relative} 失败：${error.message}`);
        console.log(`   ✘ 加载 ${relative} 失败：${error.stack.split('\n').slice(0, 3).join(' | ')}`);
    }
}
loadScript('js/api-client.js');
loadScript('js/study-tools.js');
loadScript('js/app.js');

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const VIEWS = ['projectsView', 'detailView', 'reviewView', 'reviewSessionView', 'knowledgeView', 'workbenchView'];
function activeViews() {
    return VIEWS.filter(id => {
        const el = elementsById.get(id);
        return el && el.classList.contains('active');
    });
}
function textOf(el) {
    if (!el) return '';
    let text = String(el.textContent || '');
    (el.children || []).forEach(child => { text += ' ' + textOf(child); });
    return text;
}
function findAll(root, predicate, found = []) {
    for (const child of root.children || []) {
        if (predicate(child)) found.push(child);
        findAll(child, predicate, found);
    }
    return found;
}
const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}
function step(name, fn) {
    try {
        fn();
        check(name, true);
        return true;
    } catch (error) {
        check(name, false, error.stack.split('\n').slice(0, 2).join(' | '));
        return false;
    }
}

(async () => {
    await sleep(60);
    check('init() 之后恰好一个视图 active', activeViews().length === 1, JSON.stringify(activeViews()));
    check('启动拉取了项目列表与工作台所需接口', fetchLog.some(line => line.includes('/api/projects')), JSON.stringify(fetchLog.slice(0, 6)));
    check('设置面板有每日复习上限与新增名额输入框',
        Boolean(elementsById.get('reviewDailyLimitInput')) && Boolean(elementsById.get('reviewNewPerDayInput')),
        '缺少设置输入框');

    // ① 打开今日工作台
    step('点击「今日工作台」不抛异常', () => elementsById.get('openWorkbenchBtn').dispatch('click'));
    await sleep(40);
    check('工作台打开后只有它 active', JSON.stringify(activeViews()) === JSON.stringify(['workbenchView']), JSON.stringify(activeViews()));
    check('工作台渲染出了分组标题', elementsById.get('workbenchBody').children.length > 0,
        String(elementsById.get('workbenchBody').children.length));

    // ② 返回（这就是用户报的"退不出去"）
    step('点击工作台「返回」不抛异常', () => elementsById.get('workbenchBackBtn').dispatch('click'));
    await sleep(40);
    check('返回后回到项目列表且工作台已关闭', JSON.stringify(activeViews()) === JSON.stringify(['projectsView']), JSON.stringify(activeViews()));

    // ③ 再次进入工作台并完成一条任务（没有打开项目的情况）
    elementsById.get('openWorkbenchBtn').dispatch('click');
    await sleep(40);
    const workbenchText = textOf(elementsById.get('workbenchBody'));
    const doneButtons = findAll(elementsById.get('workbenchBody'), el => el.textContent === '完成');
    check('工作台里有「完成」按钮', doneButtons.length > 0,
        '工作台内容：' + workbenchText.slice(0, 160));
    // 服务端现在会返回 note/links/repeat，工作台行必须把它们渲染成徽标
    check('工作台行显示备注 / 链接 / 周期徽标',
        workbenchText.includes('备注') && workbenchText.includes('链接') && workbenchText.includes('↻'),
        '工作台内容：' + workbenchText.slice(0, 200));
    if (doneButtons[0]) step('点击工作台「完成」不抛异常', () => doneButtons[0].dispatch('click'));
    await sleep(40);
    check('完成后视图没有错乱', activeViews().length === 1, JSON.stringify(activeViews()));
    check('完成动作真的发了保存请求（节点级 patch 或全量保存）',
        fetchLog.some(line => line.startsWith('POST /api/project') || line === 'POST /api/node/patch'),
        JSON.stringify(fetchLog.slice(-4)));

    // ④ 回到列表 → 打开项目 → 元数据弹窗 → 批量模式 → 快速添加 → 提醒
    elementsById.get('workbenchBackBtn')?.dispatch('click');
    await sleep(20);
    step('点击项目卡片打开详情不抛异常', () => elementsById.get('projectGrid').children[0].dispatch('click'));
    await sleep(60);
    check('详情视图 active', activeViews().includes('detailView'), JSON.stringify(activeViews()));
    const tree = elementsById.get('treeRoot');
    check('详情树渲染出节点', tree.children.length > 0, String(tree.children.length));
    const weekRows = findAll(tree, el => el.classList.contains('node-row'));
    check('加载后默认收起（只渲染周行）', weekRows.length >= 1, textOf(tree).slice(0, 120));
    if (weekRows[0]) step('点击周行展开子层（懒渲染）不抛异常', () => weekRows[0].dispatch('click'));
    await sleep(20);
    check('展开后子节点被渲染出来', findAll(tree, el => el.classList.contains('node-row')).length > weekRows.length,
        textOf(tree).slice(0, 200));

    // 懒渲染：一层一层展开（周 → 单元 → 任务），直到出现任务行的 ⋯ 按钮
    for (let round = 0; round < 4; round += 1) {
        if (findAll(tree, el => el.textContent === '⋯').length > 0) break;
        const expandable = findAll(tree, el => el.classList.contains('node-row') && textOf(el).includes('▶'));
        if (expandable.length === 0) break;
        expandable.forEach(row => row.dispatch('click'));
        await sleep(20);
    }

    // 数据完整性：内置「补漏队列」（id 1600）在服务端存的是字符串 id，
    // 分组勾选走「整棵树保存」路径，正好用来检查保存体；勾两次（完成→取消）恢复原状。
    const groupCheckbox = findAll(tree, el => el.classList.contains('checkbox'))[0];
    if (groupCheckbox) {
        step('勾选分组（整棵树保存路径）不抛异常', () => groupCheckbox.dispatch('click'));
        await sleep(420);
        step('再勾一次恢复分组未完成', () => groupCheckbox.dispatch('click'));
        await sleep(420);
    }
    // 早期实现拿数字 1600 去比对，会把队列再克隆一份 → 保存时「节点 ID 重复」直接 400。
    const savedTree = (() => {
        const bodies = projectPostBodies.filter(body => body && body.project && String(body.project.id) === 'p1');
        return bodies.length ? (bodies[bodies.length - 1].project.tree || []) : null;
    })();
    const savedIds = [];
    (function walk(nodes) { (nodes || []).forEach(node => { savedIds.push(String(node.id)); walk(node.children); }); })(savedTree);
    check('保存的项目里没有重复节点 ID（补漏队列没有被复制）',
        savedIds.length > 0 && new Set(savedIds).size === savedIds.length,
        `ids=${savedIds.length} unique=${new Set(savedIds).size}`);
    check('补漏队列只保留一份且被移到树根末尾',
        savedIds.filter(id => id === '1600').length === 1
        && String((savedTree[savedTree.length - 1] || {}).id) === '1600',
        `queue=${savedIds.filter(id => id === '1600').length} last=${String((savedTree[savedTree.length - 1] || {}).id)}`);


    const metaButtons = findAll(tree, el => el.textContent === '⋯');
    check('详情树里有元数据按钮（⋯）', metaButtons.length > 0, '树内容：' + textOf(tree).slice(0, 160));
    if (metaButtons[0]) step('点击 ⋯ 打开元数据弹窗不抛异常', () => metaButtons[0].dispatch('click'));
    check('元数据弹窗已打开', elementsById.get('utilityModal').hidden === false);
    check('元数据弹窗里有表单字段', elementsById.get('utilityBody').children.length > 0);

    step('关闭元数据弹窗', () => elementsById.get('utilityCloseBtn').dispatch('click'));
    step('切换批量模式', () => elementsById.get('batchToggleBtn').dispatch('click'));
    check('批量工具栏显示出来', elementsById.get('batchToolbar').hidden === false);
    step('退出批量模式', () => elementsById.get('batchToggleBtn').dispatch('click'));
    check('批量工具栏收起来', elementsById.get('batchToolbar').hidden === true);

    // ⑤ 自然语言快速添加 → 预览弹窗
    const quick = elementsById.get('quickAddInput');
    quick.value = '明天 交周报 !高 #工作 30分钟';
    step('点「加入收集箱」触发解析预览不抛异常', () => elementsById.get('quickAddBtn').dispatch('click'));
    await sleep(40);
    check('解析出结果后弹出了预览（不是直接写入）', elementsById.get('utilityModal').hidden === false);
    check('预览里显示了识别到的片段', textOf(elementsById.get('utilityBody')).includes('识别到'),
        textOf(elementsById.get('utilityBody')).slice(0, 160));
    step('关闭预览', () => elementsById.get('utilityCloseBtn').dispatch('click'));

    // ⑥ 提醒开关
    step('开启提醒不抛异常', () => elementsById.get('reminderToggleBtn').dispatch('click'));
    await sleep(20);
    check('提醒状态文案更新', String(elementsById.get('reminderStatus').textContent).includes('已开启'));
    step('再次点击关闭提醒', () => elementsById.get('reminderToggleBtn').dispatch('click'));

    // ⑦ 保存状态条：冲突时点击打开冲突面板（无冲突时应是安全的 no-op）
    step('点击保存状态条不抛异常', () => elementsById.get('saveStatus').dispatch('click'));

    // ⑧ 新建项目（普通）
    elementsById.get('newProjectInput').value = '冒烟新建项目';
    elementsById.get('newProjectAiToggle').checked = false;
    elementsById.get('newProjectPlanToggle').checked = false;
    step('点「新建项目」不抛异常', () => elementsById.get('createProjectBtn').dispatch('click'));
    await sleep(60);
    check('新建的项目出现在列表里', textOf(elementsById.get('projectGrid')).includes('冒烟新建项目'),
        textOf(elementsById.get('projectGrid')).slice(0, 160));
    check('新建项目触发了落库', fetchLog.some(line => line.startsWith('POST /api/project')), JSON.stringify(fetchLog.slice(-3)));

    // ⑨ AI 规划项目（走 /api/project/plan + 进入详情）
    elementsById.get('newProjectInput').value = '冒烟 AI 项目';
    elementsById.get('newProjectPlanToggle').checked = true;
    step('勾选 AI 规划后新建不抛异常', () => elementsById.get('createProjectBtn').dispatch('click'));
    await sleep(100);
    check('AI 规划调用了 /api/project/plan', fetchLog.includes('POST /api/project/plan'), JSON.stringify(fetchLog.slice(-4)));
    check('AI 规划后进入新项目详情页', activeViews().includes('detailView'), JSON.stringify(activeViews()));
    check('AI 生成的计划周渲染到了详情树', textOf(elementsById.get('treeRoot')).includes('第1周：AI 规划'),
        textOf(elementsById.get('treeRoot')).slice(0, 160));
    elementsById.get('newProjectPlanToggle').checked = false;

    // ⑩ 导入 JSON（文件选择框 → 确认 → POST /api/import）
    // 导出的备份里除了 projects 还带 5 张复习表的 review 快照；确认导入必须原样转发给
    // /api/import，否则"导出 → 导入"在 UI 路径上会静默丢掉复习进度与作答历史。
    // 但预览（POST /api/import/preview）走 5MiB 小限额分支且后端不消费 review：
    // 它必须保持"不带 review"，否则 projects 接近上限时预览直接 413 → 确认按钮被禁用。
    // 弹窗在 DOM 桩里 innerHTML='' 清不掉旧子节点（见 app.js 同款注释），第二次打开导入预览时
    // utilityBody 里会同时留着上一次的「确认导入」，必须点最后（最新）那一个。
    const clickImportConfirm = () => {
        const buttons = findAll(elementsById.get('utilityBody'), el => el.textContent === '确认导入');
        const button = buttons[buttons.length - 1];
        if (button) button.dispatch('click');
    };
    const importPayload = {
        schemaVersion: 2,
        projects: [{
            id: 'imp-1', name: '导入的项目', description: '', createdAt: today,
            assessmentEnabled: false, reviewEnabled: false,
            tree: [{ id: 'imp-w', type: 'week', text: '第1周：导入', completed: false, expanded: false,
                     createdAt: today, children: [{ id: 'imp-d', type: 'day', text: '单元1',
                     completed: false, expanded: false, createdAt: today, children: [{ id: 'imp-i',
                     type: 'item', text: '导入进来的任务', completed: false, completedAt: null,
                     optional: false, assessmentRequired: false, assessmentHistory: 0, assessment: null,
                     createdAt: today, children: [] }] }] }]
        }],
        review: {
            points: [{ code: 'py.imp.b', title: '导入的知识点', minutes: 5, module: '容器', level: '基础',
                       origin: 'builtin', content: { prompt: '导入的题面' },
                       createdAt: today, updatedAt: today }],
            pointTasks: [{ code: 'py.imp.b', taskId: 'imp-i', projectId: 'imp-1', relation: 'import' }],
            states: [{ code: 'py.imp.b', due: today, intervalDays: 3, streak: 1, lapses: 0,
                       lastGrade: 4, weak: false, lastReviewedAt: today }],
            attempts: [{ id: 'imp-a1', code: 'py.imp.b', taskId: '', projectId: '',
                         questionType: 'concept', grade: 4, answer: '导入的作答', aiVerdict: '',
                         reviewedOn: today, durationMs: 900, sessionId: '', createdAt: today }],
            sessions: [],
        },
    };
    elementsById.get('importInput').files = [{ name: 'backup.json', text: async () => JSON.stringify(importPayload) }];
    step('选择要导入的 JSON 文件不抛异常', () => elementsById.get('importInput').dispatch('change'));
    await sleep(120);
    check('导入先出预览（不直接覆盖数据）',
        elementsById.get('utilityModal').hidden === false && fetchLog.includes('POST /api/import/preview'),
        JSON.stringify(fetchLog.slice(-4)));
    const previewText = textOf(elementsById.get('utilityBody'));
    check('预览里显示新增/更新/移除/AI 历史处理方式',
        previewText.includes('新增项目') && previewText.includes('将被移除')
        && previewText.includes('AI 历史') && previewText.includes('导入方式'),
        previewText.slice(0, 200));
    step('点「确认导入」不抛异常', clickImportConfirm);
    await sleep(150);
    check('确认后才真正调用 /api/import', fetchLog.includes('POST /api/import'), JSON.stringify(fetchLog.slice(-4)));
    check('预览请求体不带 review（/api/import/preview 走 5MiB 小限额且不消费它，带了会 413）',
        previewBodies.length === 1 && !('review' in previewBodies[0])
        && Array.isArray(previewBodies[0].projects) && previewBodies[0].projects.length === 1
        && previewBodies[0].mode === 'replace',
        JSON.stringify(previewBodies.slice(-1)).slice(0, 200));
    check('导入请求体带上备份里的 review 快照（points/states/attempts 都在）',
        importBodies.length === 1 && Boolean(importBodies[0].review)
        && Array.isArray(importBodies[0].review.points) && importBodies[0].review.points[0].code === 'py.imp.b'
        && Array.isArray(importBodies[0].review.states) && importBodies[0].review.states[0].code === 'py.imp.b'
        && Array.isArray(importBodies[0].review.attempts) && importBodies[0].review.attempts[0].id === 'imp-a1',
        JSON.stringify(importBodies.slice(-1)).slice(0, 260));
    check('导入后列表显示导入的项目', textOf(elementsById.get('projectGrid')).includes('导入的项目'),
        textOf(elementsById.get('projectGrid')).slice(0, 160));

    // 旧备份（没有 review 键）必须照常导入，且预览/确认两条请求体里都不能凭空多出 review。
    const legacyPayload = { schemaVersion: 2, projects: importPayload.projects };
    elementsById.get('importInput').files = [{ name: 'legacy-backup.json', text: async () => JSON.stringify(legacyPayload) }];
    step('导入不含 review 的旧备份不抛异常', () => elementsById.get('importInput').dispatch('change'));
    await sleep(120);
    step('确认旧备份导入不抛异常', clickImportConfirm);
    await sleep(150);
    check('不含 review 的旧备份仍能导入，且预览/确认两条请求体里都没有 review 键',
        importBodies.length === 2 && !('review' in importBodies[1])
        && previewBodies.length === 2 && !('review' in previewBodies[1])
        && Array.isArray(importBodies[1].projects) && importBodies[1].projects.length === 1
        && Array.isArray(previewBodies[1].projects) && previewBodies[1].projects.length === 1,
        `count=${importBodies.length}/${previewBodies.length} last=${JSON.stringify(importBodies.slice(-1)).slice(0, 160)}`);

    // ⑫ 复习页改版：顶栏「复习」先开复习页（按知识点分组 + 筛选），
    //     再点「开始今日复习」进会话；会话仍是一次一题 → 先回忆 → 揭示 → 5 档自评。
    step('点击「复习」打开复习页不抛异常', () => elementsById.get('reviewQueueBtn').dispatch('click'));
    await sleep(120);
    check('顶栏「复习」先进复习页（不再直接进会话）',
        activeViews().includes('reviewView') && !activeViews().includes('reviewSessionView'),
        JSON.stringify(activeViews()));
    const reviewPageText = textOf(elementsById.get('reviewBody'));
    check('复习页主体按知识点分组（今日必须复习 + 已逾期）',
        reviewPageText.includes('今日必须复习') && reviewPageText.includes('已逾期'),
        reviewPageText.slice(0, 240));
    check('任务级到期单独成组（保留旧 /api/reviews 数据）',
        reviewPageText.includes('任务级到期') && reviewPageText.includes('任务一'),
        reviewPageText.slice(0, 240));
    check('最近答错/最近掌握渲染真实作答记录（含题型/档位/日期/答案摘要）',
        reviewPageText.includes('最近答错') && reviewPageText.includes('最近掌握')
        && reviewPageText.includes('答错的知识点') && reviewPageText.includes('掌握的知识点')
        && reviewPageText.includes('概念题') && reviewPageText.includes('2026-09-10')
        && reviewPageText.includes('第 1 档') && reviewPageText.includes('我写错的答案')
        && reviewPageText.includes('2026-09-12') && reviewPageText.includes('第 5 档'),
        reviewPageText.slice(0, 500));
    // 以前这两组是用 /api/review/points 的 lastGrade（2/5）兜底出来的知识点，
    // 会渲染"已掌握的知识点"；改成真实作答记录后它必须消失。
    check('最近答错/最近掌握不再用知识点 lastGrade 兜底',
        !reviewPageText.includes('已掌握的知识点'),
        reviewPageText.slice(0, 500));
    const typeFilter = elementsById.get('reviewTypeFilter');
    const moduleFilter = elementsById.get('reviewModuleFilter');
    const scopeFilter = elementsById.get('reviewScopeFilter');
    check('复习页有题型/模块/范围筛选与「开始今日复习」按钮',
        Boolean(typeFilter) && Boolean(moduleFilter) && Boolean(scopeFilter)
        && Boolean(elementsById.get('startReviewSessionBtn')));
    check('模块下拉由知识点数据填充',
        moduleFilter ? findAll(moduleFilter, el => el._tag === 'option').length >= 3 : false,
        textOf(moduleFilter));
    const queueFetchesBefore = fetchUrls.filter(u => u.includes('/api/review/queue')).length;
    step('切换题型筛选不抛异常', () => {
        typeFilter.value = 'concept';
        typeFilter.dispatch('change');
    });
    await sleep(120);
    check('题型筛选变化后带 type 重新拉取队列',
        fetchUrls.filter(u => u.includes('/api/review/queue')).length > queueFetchesBefore
        && fetchUrls.some(u => u.includes('/api/review/queue') && u.includes('type=concept')),
        JSON.stringify(fetchUrls.filter(u => u.includes('/api/review/queue')).slice(-3)));
    check('题型筛选也作用于最近答错/最近掌握（predict 记录被过滤掉）',
        textOf(elementsById.get('reviewBody')).includes('答错的知识点')
        && !textOf(elementsById.get('reviewBody')).includes('掌握的知识点'),
        textOf(elementsById.get('reviewBody')).slice(0, 300));
    check('题型/模块筛选后顶部统计标注筛后口径',
        textOf(elementsById.get('reviewSubline')).includes('按题型/模块筛选后'),
        textOf(elementsById.get('reviewSubline')));
    step('切换模块筛选不抛异常', () => {
        moduleFilter.value = '函数';
        moduleFilter.dispatch('change');
    });
    await sleep(120);
    check('模块筛选变化后带 module 重新拉取队列',
        fetchUrls.some(u => u.includes('/api/review/queue') && u.includes('module=%E5%87%BD%E6%95%B0')),
        JSON.stringify(fetchUrls.filter(u => u.includes('/api/review/queue')).slice(-3)));
    // 模块筛选必须同样作用于"最近答错/最近掌握"两组（summary 的最近记录带 module）。
    // 复位题型后只选「函数」模块：容器模块的答错记录要被过滤掉，函数模块的掌握记录保留。
    // 去掉 renderReviewGroups 里 matchesAttempt 的模块判断这条断言会变红（见报告自证）。
    step('复位题型筛选不抛异常', () => {
        typeFilter.value = '';
        typeFilter.dispatch('change');
    });
    await sleep(120);
    check('模块筛选也作用于最近答错/最近掌握（容器模块的答错记录被过滤掉）',
        textOf(elementsById.get('reviewBody')).includes('掌握的知识点')
        && !textOf(elementsById.get('reviewBody')).includes('答错的知识点'),
        textOf(elementsById.get('reviewBody')).slice(0, 300));
    // 后面的「开始今日复习」用例要求此时题型筛选仍是 concept，验完模块过滤就还原。
    step('还原题型筛选不抛异常', () => {
        typeFilter.value = 'concept';
        typeFilter.dispatch('change');
    });
    await sleep(60);
    step('切换范围筛选不抛异常', () => {
        scopeFilter.value = 'overdue';
        scopeFilter.dispatch('change');
    });
    await sleep(60);
    check('范围筛选只保留已逾期分组（前端过滤）',
        textOf(elementsById.get('reviewBody')).includes('已逾期')
        && !textOf(elementsById.get('reviewBody')).includes('今日必须复习'),
        textOf(elementsById.get('reviewBody')).slice(0, 200));
    // 范围筛选只作用于知识点分组：任务级到期组按自己的 due/future 显隐，不能被整组隐藏。
    check('范围筛选不隐藏任务级到期组（它按自身 due 判断显隐）',
        textOf(elementsById.get('reviewBody')).includes('任务级到期')
        && textOf(elementsById.get('reviewBody')).includes('任务一'),
        textOf(elementsById.get('reviewBody')).slice(0, 240));
    step('切换到没有条目的范围筛选不抛异常', () => {
        scopeFilter.value = 'new';
        scopeFilter.dispatch('change');
    });
    await sleep(60);
    check('范围筛选空态区分"该范围没有条目"与"今天完全没有到期"',
        textOf(elementsById.get('reviewBody')).includes('该范围')
        && !textOf(elementsById.get('reviewBody')).includes('今天没有到期的知识点'),
        textOf(elementsById.get('reviewBody')).slice(0, 240));
    step('复位范围筛选不抛异常', () => {
        scopeFilter.value = '';
        scopeFilter.dispatch('change');
    });
    await sleep(60);
    check('复位范围筛选后分组恢复',
        textOf(elementsById.get('reviewBody')).includes('今日必须复习'),
        textOf(elementsById.get('reviewBody')).slice(0, 200));
    const startQueueFetchesBefore = fetchUrls.filter(u => u.includes('/api/review/queue')).length;
    step('点「开始今日复习」进会话不抛异常',
        () => elementsById.get('startReviewSessionBtn').dispatch('click'));
    await sleep(120);
    check('「开始今日复习」继承题型/模块筛选（不再硬编码 ?today=）',
        fetchUrls.filter(u => u.includes('/api/review/queue')).length > startQueueFetchesBefore
        && fetchUrls.filter(u => u.includes('/api/review/queue')).slice(-1)[0].includes('type=concept')
        && fetchUrls.filter(u => u.includes('/api/review/queue')).slice(-1)[0].includes('module=%E5%87%BD%E6%95%B0'),
        JSON.stringify(fetchUrls.filter(u => u.includes('/api/review/queue')).slice(-2)));
    check('复习会话视图打开', activeViews().includes('reviewSessionView'), JSON.stringify(activeViews()));
    const promptEl = elementsById.get('reviewQuestionPrompt');
    check('会话出题了（有题面）', Boolean(promptEl && textOf(promptEl).trim()),
        textOf(elementsById.get('reviewSessionView')).slice(0, 160));
    // 队列的 body（题面代码）必须渲染出来，否则 predict/debug 根本没法作答。
    check('揭示前视图里就有题面代码（def add）', textOf(elementsById.get('reviewSessionView')).includes('def add('),
        textOf(elementsById.get('reviewQuestionPrompt')).slice(0, 200));
    check('题面代码渲染成等宽 pre',
        findAll(elementsById.get('reviewQuestionPrompt'), el => el._tag === 'pre').length === 1,
        textOf(elementsById.get('reviewQuestionPrompt')).slice(0, 160));
    const beforeReveal = textOf(elementsById.get('reviewSessionView'));
    check('揭示前 DOM 里没有参考答案（active recall）',
        !beforeReveal.includes('参考答案') && !beforeReveal.includes('expected-answer'),
        beforeReveal.slice(0, 200));
    check('揭示前 AI 判分入口不可见（还没作答不该判分）',
        elementsById.get('reviewAiGradeRow').hidden === true
        && elementsById.get('reviewAiGradeResult').hidden === true,
        `row.hidden=${elementsById.get('reviewAiGradeRow').hidden}`);
    step('填写回忆内容不抛异常', () => {
        const input = elementsById.get('reviewAnswerInput');
        input.value = '我写的回忆';
        input.dispatch('input');
    });
    // ⑫a 草稿/会话恢复：退出（保存草稿 + 会话进度）后再点复习，
    //     必须接着同一会话（不再开新会话），输入框里还是刚才没提交的回忆内容。
    const sessionStartsBefore = fetchLog.filter(line => line === 'POST /api/review/session').length;
    step('「退出」复习会话不抛异常', () => elementsById.get('reviewSessionExitBtn').dispatch('click'));
    await sleep(80);
    step('再次点「开始今日复习」不抛异常', () => elementsById.get('startReviewSessionBtn').dispatch('click'));
    await sleep(80);
    check('再次开始复习恢复了上次未提交的回忆内容',
        elementsById.get('reviewAnswerInput').value === '我写的回忆',
        `value=${JSON.stringify(elementsById.get('reviewAnswerInput').value)}`);
    check('恢复的是同一个会话（没有重新开新会话）',
        fetchLog.filter(line => line === 'POST /api/review/session').length === sessionStartsBefore,
        JSON.stringify(fetchLog.slice(-4)));
    const resumedSession = JSON.parse(windowStub.localStorage.getItem('todo_review_session') || 'null');
    check('恢复后仍停在第 1 题（会话进度 index=0）',
        Boolean(resumedSession) && Number(resumedSession.index) === 0,
        String(windowStub.localStorage.getItem('todo_review_session')));
    step('点「看答案」不抛异常', () => elementsById.get('reviewRevealBtn').dispatch('click'));
    await sleep(120);
    const afterReveal = textOf(elementsById.get('reviewSessionView'));
    check('揭示后才出现参考答案与历史', afterReveal.includes('参考答案'), afterReveal.slice(0, 200));
    check('揭示面板把题面代码与参考答案分开渲染',
        afterReveal.includes('题面代码') && afterReveal.includes('def add('), afterReveal.slice(0, 240));
    check('揭示后出现五档自评按钮', findAll(elementsById.get('reviewGradeButtons'),
        el => el.classList.contains('review-grade-btn')).length === 5);
    // 五档按钮必须真的带档位：桩以前漏解析 data-*，请求体里永远是 grade:null，
    // "点了第 3 个按钮"的断言却照样通过。
    check('五档自评按钮各自带 dataset.grade',
        findAll(elementsById.get('reviewGradeButtons'), el => el.classList.contains('review-grade-btn'))
            .map(el => Number(el.dataset.grade)).join(',') === '1,2,3,4,5',
        findAll(elementsById.get('reviewGradeButtons'), el => el.classList.contains('review-grade-btn'))
            .map(el => String(el.dataset.grade)).join(','));
    // ⑫a AI 判分入口（规格 §16）：揭示后按钮可见，点击请求 /api/review/ai-grade 并把 verdict 渲染进面板。
    const aiGradeRow = elementsById.get('reviewAiGradeRow');
    const aiGradeBtn = elementsById.get('reviewAiGradeBtn');
    check('揭示后出现「AI 判分（可选）」按钮',
        Boolean(aiGradeRow) && aiGradeRow.hidden === false && Boolean(aiGradeBtn),
        `row=${Boolean(aiGradeRow)} hidden=${aiGradeRow ? aiGradeRow.hidden : 'n/a'}`);
    const aiGradeBefore = reviewAiGradeBodies.length;
    if (aiGradeBtn) step('点「AI 判分（可选）」不抛异常', () => aiGradeBtn.dispatch('click'));
    await sleep(120);
    check('AI 判分请求了 /api/review/ai-grade，并带上当前题 code/type/answer',
        reviewAiGradeBodies.length === aiGradeBefore + 1
        && reviewAiGradeBodies[aiGradeBefore].code === 'py.a.b'
        && reviewAiGradeBodies[aiGradeBefore].type === 'predict'
        && reviewAiGradeBodies[aiGradeBefore].answer === '我写的回忆',
        JSON.stringify(reviewAiGradeBodies.slice(aiGradeBefore)));
    const aiVerdictText = textOf(elementsById.get('reviewAiGradeResult'));
    check('AI 判分的 verdict 渲染进面板（correct/missing/wrongAt/hint）',
        elementsById.get('reviewAiGradeResult').hidden === false
        && aiVerdictText.includes('还有缺漏') && aiVerdictText.includes('没有讲清第二次调用复用')
        && aiVerdictText.includes('把 add(1, 2) 的输出写成了 [1]')
        && aiVerdictText.includes('对照默认参数在定义时求值'),
        aiVerdictText.slice(0, 240) || '（面板为空）');
    // verdict 的两个边界分支：correct:true 要报「要点基本覆盖」；空 verdict（后端 AI 调用失败
    // 时返回 {}）必须给明确说明，而不是渲染出一个像「判错了」的空面板。
    aiGradeVerdict = { correct: true };
    if (aiGradeBtn) step('点「AI 判分」（correct:true）不抛异常', () => aiGradeBtn.dispatch('click'));
    await sleep(120);
    check('verdict correct:true 渲染成「要点基本覆盖」',
        elementsById.get('reviewAiGradeResult').hidden === false
        && textOf(elementsById.get('reviewAiGradeResult')).includes('要点基本覆盖'),
        textOf(elementsById.get('reviewAiGradeResult')).slice(0, 160) || '（面板为空）');
    aiGradeVerdict = {};
    if (aiGradeBtn) step('点「AI 判分」（空 verdict）不抛异常', () => aiGradeBtn.dispatch('click'));
    await sleep(120);
    check('空 verdict 渲染明确说明（不是空面板）',
        elementsById.get('reviewAiGradeResult').hidden === false
        && textOf(elementsById.get('reviewAiGradeResult')).includes('AI 没有返回判分结果'),
        textOf(elementsById.get('reviewAiGradeResult')).slice(0, 160) || '（面板为空）');
    aiGradeVerdict = null;
    // 未配置 AI key（503）：只 toast 提示，不抛异常，也不能顺手提交一次自评。
    aiGradeUnavailable = true;
    const answersBeforeUnavailable = reviewAnswerBodies.length;
    if (aiGradeBtn) step('未配置 AI（503）时点判分不抛异常', () => aiGradeBtn.dispatch('click'));
    await sleep(120);
    check('503 时用 toast 说明判分不可用，且没有提交自评',
        String(elementsById.get('toastMessage').textContent).includes('未配置 AI')
        && reviewAnswerBodies.length === answersBeforeUnavailable,
        `toast=${String(elementsById.get('toastMessage').textContent)} answers=${reviewAnswerBodies.length - answersBeforeUnavailable}`);
    aiGradeUnavailable = false;
    const answersBefore = reviewAnswerBodies.length;
    // 防重入：五档按钮是容器上的事件委托，双击同一档必须只发一次请求（否则 index 前进 2 格跳题）。
    step('连点两次「基本掌握」不抛异常', () => {
        const buttons = findAll(elementsById.get('reviewGradeButtons'),
            el => el.classList.contains('review-grade-btn'));
        if (buttons[2]) { buttons[2].dispatch('click'); buttons[2].dispatch('click'); }
    });
    await sleep(150);
    check('连点两次同一档只提交一次 /api/review/answer（防重入）',
        reviewAnswerBodies.length === answersBefore + 1,
        `bodies=${reviewAnswerBodies.length - answersBefore}`);
    const gradeBody = reviewAnswerBodies[answersBefore];
    check('提交自评后调用了 /api/review/answer',
        fetchLog.includes('POST /api/review/answer'), JSON.stringify(fetchLog.slice(-4)));
    check('自评请求体带的是第 3 个按钮的档位 grade === 3',
        Boolean(gradeBody) && Number(gradeBody.grade) === 3,
        JSON.stringify(reviewAnswerBodies.slice(answersBefore)));
    check('自评请求体带的是当前题的 code/type',
        Boolean(gradeBody) && gradeBody.code === 'py.a.b' && gradeBody.type === 'predict',
        JSON.stringify(reviewAnswerBodies.slice(answersBefore)));
    // ⑫b 会话进度落盘：队列有 2 题，评完第 1 题后仍在本轮会话里 → index 必须是 1。
    // （若这一轮已经练完，finishReviewSession 会清掉 key，断言就会退化成"null 也算过"。）
    const savedSession = JSON.parse(windowStub.localStorage.getItem('todo_review_session') || 'null');
    check('评完一题后 localStorage 里的会话进度 index 前进到 1',
        Boolean(savedSession) && Number(savedSession.index) === 1,
        String(windowStub.localStorage.getItem('todo_review_session')));
    check('评完第 1 题后自动进入第 2 题',
        textOf(elementsById.get('reviewSessionProgress')).includes('第 2 / 2 题'),
        textOf(elementsById.get('reviewSessionProgress')));
    check('第 2 题也渲染了自己的题面代码',
        textOf(elementsById.get('reviewQuestionPrompt')).includes('def total('),
        textOf(elementsById.get('reviewQuestionPrompt')).slice(0, 200));
    check('进入第 2 题后答案面板重新隐藏（没揭示前不露答案）',
        elementsById.get('reviewAnswerPanel').hidden === true
        && elementsById.get('reviewGradeButtons').hidden === true,
        `answerPanel.hidden=${elementsById.get('reviewAnswerPanel').hidden}`);
    // 这一句只有在 renderReviewQuestion() 里复位 reviewAiGradeRow.hidden 时才成立：
    // 上一题揭示后它被设成 false，不复位的话第 2 题没揭示就能点 AI 判分。
    check('进入第 2 题后 AI 判分入口重新隐藏（揭示前不可判分）',
        elementsById.get('reviewAiGradeRow').hidden === true
        && elementsById.get('reviewAiGradeResult').hidden === true,
        `row.hidden=${elementsById.get('reviewAiGradeRow').hidden} result.hidden=${elementsById.get('reviewAiGradeResult').hidden}`);
    // 第 2 题（debug）走完，会话结束 → 进度 key 被清掉、总结出现
    step('第 2 题揭示并自评不抛异常', () => elementsById.get('reviewRevealBtn').dispatch('click'));
    await sleep(120);
    check('第 2 题揭示后是 debug 的根因/修法',
        textOf(elementsById.get('reviewSessionView')).includes('根因')
        && textOf(elementsById.get('reviewSessionView')).includes('可变默认参数被复用'),
        textOf(elementsById.get('reviewSessionView')).slice(0, 240));
    step('第 2 题选「完全不会」不抛异常', () => {
        const buttons = findAll(elementsById.get('reviewGradeButtons'),
            el => el.classList.contains('review-grade-btn'));
        if (buttons[0]) buttons[0].dispatch('click');
    });
    await sleep(150);
    check('第 2 题请求体档位是 1（第 1 个按钮）',
        Number((reviewAnswerBodies[reviewAnswerBodies.length - 1] || {}).grade) === 1,
        JSON.stringify(reviewAnswerBodies.slice(-1)));
    check('练完后清掉了会话进度（下次复习重新取队列）',
        windowStub.localStorage.getItem('todo_review_session') === null,
        String(windowStub.localStorage.getItem('todo_review_session')));
    check('练完后展示本轮总结', textOf(elementsById.get('reviewSessionSummary')).includes('本次复习完成'),
        textOf(elementsById.get('reviewSessionSummary')).slice(0, 160));

    // ⑪ 恢复备份（下拉选择 → 恢复 → 刷新页面）
    step('打开备份下拉不抛异常', () => elementsById.get('databaseBackupPickerButton').dispatch('click'));
    await sleep(20);
    const backupOptions = findAll(elementsById.get('databaseBackupMenu'),
        el => el.classList.contains('backup-picker-option'));
    check('备份下拉里有可恢复的备份', backupOptions.length > 0,
        textOf(elementsById.get('databaseBackupMenu')).slice(0, 120));
    if (backupOptions[0]) {
        step('选中备份不抛异常', () => backupOptions[0].dispatch('click'));
        check('选中后写出了备份名', String(elementsById.get('databaseBackupSelect').value).endsWith('.zip'),
            String(elementsById.get('databaseBackupSelect').value));
    }
    const beforeReload = reloadCount;
    step('点「恢复」不抛异常', () => elementsById.get('restoreDatabaseBackupBtn').dispatch('click'));
    await sleep(80);
    check('恢复调用了 /api/backup', fetchLog.includes('POST /api/backup'), JSON.stringify(fetchLog.slice(-4)));
    check('恢复成功后请求刷新页面', reloadCount > beforeReload, `reloadCount=${reloadCount}`);

    // ⑬ 删除 → 影响面确认 → 回收站 → Ctrl+Z 撤销
    // 注意：前面的导入/恢复把项目换掉了，这里要重新打开详情页并展开，才能拿到真实的行
    elementsById.get('projectGrid').children[0].dispatch('click');
    await sleep(80);
    for (let round = 0; round < 4; round += 1) {
        if (findAll(tree, el => el.classList.contains('delete-btn')).length > 0) break;
        const expandable = findAll(tree, el => el.classList.contains('node-row') && textOf(el).includes('▶'));
        if (expandable.length === 0) break;
        expandable.forEach(row => row.dispatch('click'));
        await sleep(25);
    }
    check('重新打开详情页后有可操作的任务行',
        findAll(tree, el => el.classList.contains('node-row')).length > 0 && activeViews().includes('detailView'),
        JSON.stringify(activeViews()) + textOf(tree).slice(0, 120));

    const deleteButtons = findAll(tree, el => el.classList.contains('delete-btn'));
    check('任务行有删除按钮', deleteButtons.length > 0, textOf(tree).slice(0, 120));
    if (deleteButtons[0]) {
        const trashBefore = fetchLog.filter(line => line === 'POST /api/trash').length;
        const patchBefore = fetchLog.filter(line => line === 'POST /api/node/patch').length;
        step('点删除不抛异常', () => deleteButtons[0].dispatch('click'));
        await sleep(120);
        check('删除前查询了影响面', fetchLog.some(line => line.startsWith('GET /api/node/delete-impact')),
            JSON.stringify(fetchLog.slice(-4)));
        check('删除写进了回收站', fetchLog.filter(line => line === 'POST /api/trash').length > trashBefore);
        // patch 排在保存队列后面，可能比点击晚一点才发出去
        for (let round = 0; round < 20
             && fetchLog.filter(line => line === 'POST /api/node/patch').length === patchBefore; round += 1) {
            await sleep(25);
        }
        check('删除走节点级 patch（不再整棵树重传）',
            fetchLog.filter(line => line === 'POST /api/node/patch').length > patchBefore,
            JSON.stringify(fetchLog.slice(-4)));
        check('撤销按钮变为可用', elementsById.get('undoBtn').disabled === false);
        step('Ctrl+Z 撤销不抛异常', () => documentStub.dispatch('keydown',
            { key: 'z', ctrlKey: true, shiftKey: false, target: null, preventDefault() {} }));
        await sleep(150);
        const trashAfter = fetchLog.filter(line => line === 'POST /api/trash').length;
        check('撤销真的做了恢复（又一次回收站调用）', trashAfter > trashBefore,
            JSON.stringify(fetchLog.slice(-3)));
    }

    // ⑬ 复制对话框（选项 → 调 /api/node/duplicate）
    const copyButtons = findAll(tree, el => el.classList.contains('copy-btn'));
    if (copyButtons[0]) {
        step('点复制打开选项对话框', () => copyButtons[0].dispatch('click'));
        await sleep(40);
        check('复制对话框说明了可选项（含子任务/完成状态/AI 历史/复习）',
            textOf(elementsById.get('utilityBody')).includes('包含子任务')
            && textOf(elementsById.get('utilityBody')).includes('保留 AI 验收历史'),
            textOf(elementsById.get('utilityBody')).slice(0, 160));
        const confirmCopy = findAll(elementsById.get('utilityBody'), el => el.textContent === '复制');
        if (confirmCopy[0]) {
            step('确认复制不抛异常', () => confirmCopy[0].dispatch('click'));
            await sleep(120);
            check('复制调用了 /api/node/duplicate', fetchLog.includes('POST /api/node/duplicate'),
                JSON.stringify(fetchLog.slice(-4)));
        }
    } else {
        check('任务行有复制按钮', false, '详情树里没找到 ⧉');
    }

    // ⑮ 知识点库：更多工具 → 打开库页 → 按模块/层级筛选 → 立即练一次进会话
    const pointsFetchesBefore = fetchUrls.filter(u => u.includes('/api/review/points')).length;
    step('打开知识点库不抛异常', () => elementsById.get('openKnowledgeBtn').dispatch('click'));
    await sleep(120);
    check('知识点库视图打开并列出知识点',
        activeViews().includes('knowledgeView')
        && textOf(elementsById.get('knowledgeList')).includes('示例知识点'),
        textOf(elementsById.get('knowledgeList')).slice(0, 160));
    // 只断言"曾经拉过 points"会被前面复习页的请求蒙混过关：这里要求本次开库真的新拉了一次。
    check('知识点库调用了 /api/review/points',
        fetchUrls.filter(u => u.includes('/api/review/points')).length > pointsFetchesBefore
        && fetchUrls.filter(u => u.includes('/api/review/points')).slice(-1)[0].includes('limit=500'),
        JSON.stringify(fetchUrls.filter(u => u.includes('/api/review/points')).slice(-2)));
    const knowledgeModuleOptions = elementsById.get('knowledgeModuleFilter')
        ? findAll(elementsById.get('knowledgeModuleFilter'), el => el._tag === 'option') : [];
    check('知识点库的模块下拉与复习页用同一份知识点数据',
        knowledgeModuleOptions.length >= 3,
        textOf(elementsById.get('knowledgeModuleFilter')));
    step('知识点库切到「函数」模块不抛异常', () => {
        const moduleSelect = elementsById.get('knowledgeModuleFilter');
        moduleSelect.value = '函数';
        moduleSelect.dispatch('change');
    });
    await sleep(40);
    check('模块筛选只保留该模块的知识点',
        textOf(elementsById.get('knowledgeList')).includes('已掌握的知识点')
        && !textOf(elementsById.get('knowledgeList')).includes('示例知识点'),
        textOf(elementsById.get('knowledgeList')).slice(0, 200));
    step('知识点库切到「基础」层级不抛异常', () => {
        const moduleSelect = elementsById.get('knowledgeModuleFilter');
        const levelSelect = elementsById.get('knowledgeLevelFilter');
        moduleSelect.value = '';
        levelSelect.value = '基础';
        levelSelect.dispatch('change');
    });
    await sleep(40);
    check('层级筛选只保留该层级的知识点',
        textOf(elementsById.get('knowledgeList')).includes('示例知识点')
        && !textOf(elementsById.get('knowledgeList')).includes('已掌握的知识点'),
        textOf(elementsById.get('knowledgeList')).slice(0, 200));
    step('复位知识点库层级筛选不抛异常', () => {
        const levelSelect = elementsById.get('knowledgeLevelFilter');
        levelSelect.value = '';
        levelSelect.dispatch('change');
    });
    await sleep(40);
    const practiceButtons = elementsById.get('knowledgeList')
        ? findAll(elementsById.get('knowledgeList'), el => el.textContent === '立即练一次') : [];
    check('每个知识点都有「立即练一次」按钮', practiceButtons.length === 2, String(practiceButtons.length));
    step('点「立即练一次」不抛异常', () => { if (practiceButtons[0]) practiceButtons[0].dispatch('click'); });
    await sleep(150);
    check('立即练一次用 code 精确取这一题的题面（不是整条队列）',
        fetchUrls.some(u => u.includes('/api/review/queue') && u.includes('code=py.a.b')),
        JSON.stringify(fetchUrls.filter(u => u.includes('/api/review/queue')).slice(-2)));
    check('立即练一次进入会话且只练这一个知识点',
        activeViews().includes('reviewSessionView')
        && textOf(elementsById.get('reviewSessionProgress')).includes('第 1 / 1 题'),
        JSON.stringify(activeViews()) + ' ' + textOf(elementsById.get('reviewSessionProgress')));
    check('立即练一次的会话用的是这一题的题面',
        textOf(elementsById.get('reviewQuestionPrompt')).includes('写出下面代码的输出'),
        textOf(elementsById.get('reviewQuestionPrompt')).slice(0, 160));

    // ⑯ 默认课程（assessmentEnabled: true + 每个任务 assessmentRequired: true）：
    //     勾选任务直接进 AI 验收，验收通过必须走生成回流（POST /api/review/generate）；
    //     验收失败必须带 remedial:true + gap 生成补漏题。
    //     桩以前把 assessmentEnabled 关掉、任务全是 assessmentRequired:false，
    //     导致"完成任务 → 生成复习项"在默认路径上是死代码却照样全绿。
    async function openAssessItem(text) {
        elementsById.get('backBtn').dispatch('click');
        await sleep(150);
        const card = findAll(elementsById.get('projectGrid'), el => textOf(el).includes('验收项目'))[0];
        if (card) card.dispatch('click');
        await sleep(150);
        for (let round = 0; round < 6; round += 1) {
            if (findAll(tree, el => el.classList.contains('node-row') && textOf(el).includes(text)).length > 0) break;
            // 只点"还收起着的分组行"：连展开的行一起点会把刚展开的又收起来。
            const collapsed = findAll(tree, el => el.classList.contains('node-row') && textOf(el).includes('▶')
                && !findAll(el, child => child.classList.contains('arrow')
                    && child.classList.contains('expanded')).length);
            if (collapsed.length === 0) break;
            collapsed.forEach(row => row.dispatch('click'));
            await sleep(30);
        }
        return findAll(tree, el => el.classList.contains('node-row') && textOf(el).includes(text))[0];
    }

    // 路径 A：第一阶段已通过 → 第二阶段留空提交，跳过实现阶段直接通过（js/app.js 跳过实现那条通过路径）。
    const skipRow = await openAssessItem('跳过实现的任务');
    check('验收任务行渲染出来了（assessmentRequired:true，默认课程路径）', Boolean(skipRow),
        textOf(elementsById.get('treeRoot')).slice(0, 200));
    const generateBeforeSkip = fetchLog.filter(line => line === 'POST /api/review/generate').length;
    const generateOptionsBeforeSkip = reviewGenerateOptions.length;
    if (skipRow) {
        const checkbox = findAll(skipRow, el => el.classList.contains('checkbox'))[0];
        step('勾选验收任务打开验收弹窗不抛异常', () => checkbox.dispatch('click'));
        await sleep(120);
        check('验收弹窗打开（body 进入 assessment-open）',
            documentStub.body.classList.contains('assessment-open'));
        // 生成回流挂在可控 promise 上：既能断言"请求真的发出去了"（不是只派发 promise），
        // 也能断言调用处真的 await——没 await 时 finally 会立刻把提交按钮恢复可用，
        // 下面的 disabled 断言就会变红。
        generateHold = [];
        step('留空提交验收（跳过实现阶段）不抛异常', () => elementsById.get('assessmentForm').dispatch('submit'));
        await sleep(200);
        check('验收通过后 /api/review/generate 请求已经发出（不是只派发 promise）',
            reviewGenerateOptions.length > generateOptionsBeforeSkip,
            JSON.stringify(reviewGenerateOptions.slice(-2)));
        check('生成回流请求带 keepalive（关页/刷新时也能发完）',
            Boolean(reviewGenerateOptions.slice(-1)[0])
            && reviewGenerateOptions.slice(-1)[0].keepalive === true,
            JSON.stringify(reviewGenerateOptions.slice(-2)));
        check('生成回流被 await：请求未完成时验收流程尚未收尾（提交按钮仍禁用）',
            elementsById.get('assessmentSubmitBtn').disabled === true,
            `disabled=${elementsById.get('assessmentSubmitBtn').disabled}`);
        generateHold.forEach(release => release());
        generateHold = null;
        await sleep(80);
        check('释放生成回流后验收流程正常收尾（提交按钮恢复可用）',
            elementsById.get('assessmentSubmitBtn').disabled === false,
            `disabled=${elementsById.get('assessmentSubmitBtn').disabled}`);
    }
    check('验收通过（跳过实现阶段）后 POST 了 /api/review/generate',
        fetchLog.filter(line => line === 'POST /api/review/generate').length > generateBeforeSkip,
        JSON.stringify(fetchLog.slice(-6)));
    check('确有新增时才提示"已生成 N 个复习知识点"',
        String(elementsById.get('toastMessage').textContent).includes('已生成 2 个复习知识点'),
        String(elementsById.get('toastMessage').textContent));

    // 路径 B：完整走完三道题（先失败一次 → 补漏题）+ 实现阶段通过。
    const fullRow = await openAssessItem('完整通过的任务');
    check('第二个验收任务行渲染出来了', Boolean(fullRow), textOf(elementsById.get('treeRoot')).slice(0, 200));
    if (fullRow) {
        const checkbox = findAll(fullRow, el => el.classList.contains('checkbox'))[0];
        checkbox.dispatch('click');
        await sleep(200);
        check('验收弹窗生成出三道针对题',
            fetchLog.includes('POST /api/question')
            && textOf(elementsById.get('assessmentModal')).includes('题目已生成，请回答当前题'),
            textOf(elementsById.get('assessmentModal')).slice(0, 200));
        const remedialBefore = reviewGenerateBodies.filter(body => body.remedial).length;
        elementsById.get('assessmentAnswer').value = 'FAIL';
        elementsById.get('assessmentForm').dispatch('submit');
        await sleep(200);
        const remedialBodies = reviewGenerateBodies.filter(body => body.remedial);
        check('问题阶段验收失败后带 remedial + gap 生成补漏题',
            remedialBodies.length > remedialBefore
            && remedialBodies.some(body => body.remedial === true && String(body.gap || '').includes('自由变量')),
            JSON.stringify(reviewGenerateBodies.slice(-2)));
        // 三道题连续通过 → 进入实现阶段。
        for (let index = 0; index < 3; index += 1) {
            elementsById.get('assessmentAnswer').value = `正确答案 ${index + 1}`;
            elementsById.get('assessmentForm').dispatch('submit');
            await sleep(150);
        }
        const generateBeforeFull = fetchLog.filter(line => line === 'POST /api/review/generate').length;
        elementsById.get('assessmentAnswer').value = '我按 None 哨兵重写了实现';
        // 生成回流失败（500）必须只 warn：既不抛未处理异常，也不阻断验收流程收尾。
        const generateWarnings = [];
        const realWarn = console.warn;
        console.warn = (...args) => { generateWarnings.push(args.map(item => String(item)).join(' ')); };
        generateFails = true;
        elementsById.get('assessmentForm').dispatch('submit');
        await sleep(250);
        generateFails = false;
        console.warn = realWarn;
        check('完整验收通过后 POST 了 /api/review/generate',
            fetchLog.filter(line => line === 'POST /api/review/generate').length > generateBeforeFull,
            JSON.stringify(fetchLog.slice(-6)));
        check('生成回流 500 只 warn：无未处理异常，验收流程照常收尾（按钮恢复可用）',
            asyncErrors.length === 0
            && generateWarnings.some(line => line.includes('生成复习知识点失败'))
            && elementsById.get('assessmentSubmitBtn').disabled === false,
            JSON.stringify({ errors: asyncErrors.slice(-2), warnings: generateWarnings.slice(-2),
                disabled: elementsById.get('assessmentSubmitBtn').disabled }));
        check('零新增（inserted=0）时不再误报"已生成 N 个"',
            !String(elementsById.get('toastMessage').textContent).includes('已生成'),
            String(elementsById.get('toastMessage').textContent));
    }

    await sleep(80);
    check('事件处理器里没有未处理的异步异常', asyncErrors.length === 0, asyncErrors.slice(0, 3).join(' || '));
    console.log(`\n   通过 ${results.filter(Boolean).length} 项，失败 ${results.filter(r => !r).length + failures.length} 项`);
    failures.forEach(message => console.log('   ! ' + message));
    process.exit(results.every(Boolean) && failures.length === 0 ? 0 : 1);
})();
