// 前端运行时冒烟测试：用最小 DOM 桩真实加载 index.html + api-client.js + study-tools.js + app.js，
// 然后模拟点击（今日工作台 → 返回、打开项目、完成任务、打开元数据、批量模式、快速添加、提醒开关），
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
        _tag: tag, id, _children: [], _listeners: {}, parentElement: null,
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
        dispatch(type, event = {}) {
            (this._listeners[type] || []).forEach(fn => fn({ target: this, currentTarget: this, stopPropagation() {}, preventDefault() {}, key: '', ...event }));
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
        closest() { return null; },
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

const elementsById = new Map();
for (const match of html.matchAll(/<[^>]*id="([^"]+)"[^>]*>/g)) {
    const el = makeEl('div', match[1]);
    const classMatch = match[0].match(/class="([^"]*)"/);
    if (classMatch) classMatch[1].split(/\s+/).filter(Boolean).forEach(name => el.classList.add(name));
    if (/\shidden(\s|>|$)/.test(match[0])) el.hidden = true;
    elementsById.set(match[1], el);
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
async function fetchStub(url, options = {}) {
    const path = String(url).split('?')[0];
    fetchLog.push(`${options.method || 'GET'} ${path}`);
    const reply = (status, payload) => ({
        ok: status >= 200 && status < 300, status,
        headers: new HeadersStub({ 'Content-Type': 'application/json' }),
        json: async () => payload, text: async () => JSON.stringify(payload), blob: async () => ({}),
    });
    if (path === '/api/projects') return reply(200, { projects: [{ id: 'p1', name: '测试项目', description: '', createdAt: today, assessmentEnabled: false, archived: false, stats: { total: 1, remaining: 1, optionalTotal: 0, optionalCompleted: 0 }, _revision: 1 }], reviewTotals: { today: 0, overdue: 0 }, serverToday: today, usedToday: today });
    if (path === '/api/project') return reply(200, { project: projectFixture, revision: 1 });
    if (path === '/api/background') return reply(404, {});
    if (path === '/api/config') return reply(200, { ready: true, models: { flash: 'f', pro: 'p' }, error: '' });
    if (path === '/api/storage') return reply(200, { projectLimitBytes: 1000, largestProjectBytes: 10, projectCount: 1 });
    if (path === '/api/backups') return reply(200, { backups: [] });
    if (path === '/api/views') return reply(200, { views: [] });
    if (path === '/api/workbench') return reply(200, workbenchFixture);
    if (path === '/api/recent') return reply(200, { opened: [], modified: [], completed: [] });
    if (path === '/api/trash') return reply(200, { items: [] });
    if (path === '/api/memos') return reply(200, { memos: [], databaseBytes: 0 });
    if (path === '/api/inbox/add') return reply(200, { ok: true, node: { ...projectFixture.tree[0].children[0].children[0], id: 'i-new', text: '新任务' }, revision: 2, projectId: 'inbox' });
    if (path === '/api/batch') return reply(200, { ok: true, changed: 1, spawned: 0, failed: [], projects: [] });
    if (path === '/api/heartbeat' || path === '/api/health') return reply(200, { ok: true });
    return reply(200, { ok: true });
}

// ---------------- 组装全局环境 ----------------
const timers = [];
const windowStub = {
    document: documentStub, location: { protocol: 'http:', search: '', pathname: '/', hash: '', href: 'http://127.0.0.1:8765/', reload() {} },
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
const VIEWS = ['projectsView', 'detailView', 'reviewView', 'workbenchView'];
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
    check('完成动作真的发了保存请求', fetchLog.some(line => line.startsWith('POST /api/project')), JSON.stringify(fetchLog.slice(-4)));

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

    await sleep(80);
    check('事件处理器里没有未处理的异步异常', asyncErrors.length === 0, asyncErrors.slice(0, 3).join(' || '));
    console.log(`\n   通过 ${results.filter(Boolean).length} 项，失败 ${results.filter(r => !r).length + failures.length} 项`);
    failures.forEach(message => console.log('   ! ' + message));
    process.exit(results.every(Boolean) && failures.length === 0 ? 0 : 1);
})();
