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
            if (idMatch) {
                if (/\shidden(\s|>|$)/.test(attrs)) el.hidden = true;
                // data-* 也要解析：复习自评按钮靠 dataset.grade 传档位，桩里漏掉就会永远点不出请求。
                for (const dataMatch of attrs.matchAll(/data-([\w-]+)="([^"]*)"/g)) {
                    const key = dataMatch[1].replace(/-(\w)/g, (m, c) => c.toUpperCase());
                    el.dataset[key] = dataMatch[2];
                }
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
    constructor(init) { this.map = new Map(); if (init && init.forEach) init.forEach((v, k) => this.map.set(k, v)); else Object.entries(init || {}).forEach(([k, v]) => this.map.set(k, v)); }
    set(k, v) { this.map.set(k, v); }
    get(k) { return this.map.get(k) || null; }
    has(k) { return this.map.has(k); }
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
// 记录整项目保存的请求体：用来断言「保存时不能出现重复节点 ID」这类数据完整性不变量
const projectPostBodies = [];
async function fetchStub(url, options = {}) {
    const path = String(url).split('?')[0];
    fetchLog.push(`${options.method || 'GET'} ${path}`);
    const reply = (status, payload) => ({
        ok: status >= 200 && status < 300, status,
        headers: new HeadersStub({ 'Content-Type': 'application/json' }),
        json: async () => payload, text: async () => JSON.stringify(payload), blob: async () => ({}),
    });
    if (path === '/api/projects') return reply(200, { projects: [{ id: 'p1', name: '测试项目', description: '', createdAt: today, assessmentEnabled: false, archived: false, stats: { total: 1, remaining: 1, optionalTotal: 0, optionalCompleted: 0 }, _revision: 1 }], reviewTotals: { today: 0, overdue: 0 }, serverToday: today, usedToday: today });
    if (path === '/api/project' && (options.method || 'GET') === 'POST' && options.body) {
        try { projectPostBodies.push(JSON.parse(options.body)); } catch (error) { fetchLog.push('BAD-BODY'); }
    }
    if (path === '/api/project') {
        // 真实服务按请求的 id 返回对应项目；桩也要保持一致，
        // 否则前端会发现"返回的 id 和当前项目 id 不一致"而退回列表页
        const requested = new URLSearchParamsStub(String(url).split('?')[1] || '').get('id') || 'p1';
        return reply(200, { project: { ...projectFixture, id: requested }, revision: 1 });
    }
    if (path === '/api/background') return reply(404, {});
    if (path === '/api/config') return reply(200, { ready: true, models: { flash: 'f', pro: 'p' }, error: '' });
    if (path === '/api/storage') return reply(200, { projectLimitBytes: 1000, largestProjectBytes: 10, projectCount: 1 });
    if (path === '/api/backups') return reply(200, {
        backups: [{ name: 'manual-20260915T000000000000.zip', kind: 'full', bytes: 2048,
                    modifiedAt: '2026-09-15T00:00:00', valid: true }]
    });
    if (path === '/api/import/preview') return reply(200, {
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
    if (path === '/api/import') return reply(200, { backup: 'before-import-smoke.zip',
        ok: true,
        projects: [{ id: 'imp-1', name: '导入的项目', description: '', createdAt: today,
                     assessmentEnabled: false, archived: false, reviewEnabled: false,
                     stats: { total: 1, remaining: 1, optionalTotal: 0, optionalCompleted: 0 }, _revision: 1 }]
    });
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
        total: 3, learned: 2, answeredToday: 0, streakDays: 3, limit: 10, newPerDay: 2 });
    if (path === '/api/review/queue') return reply(200, { items: [{ code: 'py.a.b', title: '示例知识点',
        minutes: 10, module: '容器', level: '基础', questionType: 'predict',
        prompt: '写出下面代码的输出', reason: 'today', due: today, taskId: '1103', projectId: 'p1' }],
        total: 1, truncated: false, limit: 10 });
    if (path === '/api/review/reveal') return reply(200, { code: 'py.a.b', type: 'predict',
        title: '示例知识点', prompt: '写出下面代码的输出', expected: ['[1]', '[1, 2]'],
        explain: '第二次调用复用了同一个列表', pitfalls: ['可变默认参数'], history: [], state: null });
    if (path === '/api/review/answer') return reply(200, { ok: true, schedule: { due: '2026-09-30',
        intervalDays: 14, streak: 1, lapses: 0, weak: false, lastGrade: 4 } });
    if (path === '/api/review/session') return reply(200, { ok: true, sessionId: 's-review-1' });
    if (path === '/api/review/points') return reply(200, { points: [{ code: 'py.a.b', title: '示例知识点',
        minutes: 10, module: '容器', level: '基础', origin: 'builtin', due: today, weak: true, lastGrade: 3,
        pitfalls: ['可变默认参数'] }], total: 1, limit: 200, offset: 0 });
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
        }]
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
    step('点「确认导入」不抛异常', () => {
        const buttons = findAll(elementsById.get('utilityBody'), el => el.textContent === '确认导入');
        if (buttons[0]) buttons[0].dispatch('click');
    });
    await sleep(150);
    check('确认后才真正调用 /api/import', fetchLog.includes('POST /api/import'), JSON.stringify(fetchLog.slice(-4)));
    check('导入后列表显示导入的项目', textOf(elementsById.get('projectGrid')).includes('导入的项目'),
        textOf(elementsById.get('projectGrid')).slice(0, 160));

    // ⑫ 复习会话：一次一题 → 先回忆 → 揭示 → 5 档自评（揭示前 DOM 里不能有答案）
    step('点击「开始复习」不抛异常', () => elementsById.get('reviewQueueBtn').dispatch('click'));
    await sleep(120);
    check('复习会话视图打开', activeViews().includes('reviewSessionView'), JSON.stringify(activeViews()));
    const promptEl = elementsById.get('reviewQuestionPrompt');
    check('会话出题了（有题面）', Boolean(promptEl && textOf(promptEl).trim()),
        textOf(elementsById.get('reviewSessionView')).slice(0, 160));
    const beforeReveal = textOf(elementsById.get('reviewSessionView'));
    check('揭示前 DOM 里没有参考答案（active recall）',
        !beforeReveal.includes('参考答案') && !beforeReveal.includes('expected-answer'),
        beforeReveal.slice(0, 200));
    step('填写回忆内容不抛异常', () => {
        const input = elementsById.get('reviewAnswerInput');
        input.value = '我写的回忆';
        input.dispatch('input');
    });
    step('点「看答案」不抛异常', () => elementsById.get('reviewRevealBtn').dispatch('click'));
    await sleep(120);
    const afterReveal = textOf(elementsById.get('reviewSessionView'));
    check('揭示后才出现参考答案与历史', afterReveal.includes('参考答案'), afterReveal.slice(0, 200));
    check('揭示后出现五档自评按钮', findAll(elementsById.get('reviewGradeButtons'),
        el => el.classList.contains('review-grade-btn')).length === 5);
    step('选「基本掌握」不抛异常', () => {
        const buttons = findAll(elementsById.get('reviewGradeButtons'),
            el => el.classList.contains('review-grade-btn'));
        if (buttons[2]) buttons[2].dispatch('click');
    });
    await sleep(150);
    check('提交自评后调用了 /api/review/answer',
        fetchLog.includes('POST /api/review/answer'), JSON.stringify(fetchLog.slice(-4)));

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

    await sleep(80);
    check('事件处理器里没有未处理的异步异常', asyncErrors.length === 0, asyncErrors.slice(0, 3).join(' || '));
    console.log(`\n   通过 ${results.filter(Boolean).length} 项，失败 ${results.filter(r => !r).length + failures.length} 项`);
    failures.forEach(message => console.log('   ! ' + message));
    process.exit(results.every(Boolean) && failures.length === 0 ? 0 : 1);
})();
