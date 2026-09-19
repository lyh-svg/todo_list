// 前端规模基线：1000 / 10000 个任务时，"保存前的序列化"和"渲染"各要多久、各建多少 DOM。
// 只读：从 js/app.js 抽出真实函数，用最小 DOM 桩跑，不修改仓库文件。
//
//   node tests/frontend/measure-scale.js
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..', '..');
const src = fs.readFileSync(path.join(ROOT, 'js', 'app.js'), 'utf8');

function extract(name) {
    const at = src.indexOf(`    function ${name}(`);
    if (at < 0) throw new Error('找不到 ' + name);
    let depth = 0, seen = false;
    for (let i = at; i < src.length; i++) {
        if (src[i] === '{') { depth++; seen = true; }
        else if (src[i] === '}') { depth--; if (seen && depth === 0) return src.slice(at, i + 1); }
    }
    throw new Error(name + ' 括号不配对');
}
const asyncAt = src.indexOf('    async function renderNode(');
function extractAsync(name) {
    const at = src.indexOf(`    async function ${name}(`);
    if (at < 0) throw new Error('找不到 async ' + name);
    let depth = 0, seen = false;
    for (let i = at; i < src.length; i++) {
        if (src[i] === '{') { depth++; seen = true; }
        else if (src[i] === '}') { depth--; if (seen && depth === 0) return src.slice(at, i + 1); }
    }
    throw new Error(name + ' 括号不配对');
}

// ---------- 最小 DOM 桩（只统计"建了多少元素"和耗时） ----------
let created = 0;
function makeEl(tag = 'div') {
    created += 1;
    const el = {
        tagName: String(tag).toUpperCase(), _children: [], _listeners: 0, style: {}, dataset: {},
        className: '', textContent: '', innerHTML: '', value: '', checked: false, hidden: false,
        disabled: false, type: '', title: '', placeholder: '', href: '', download: '', expanded: false,
        selectedIndex: 0, options: [], files: [], tabIndex: 0, scrollTop: 0, scrollHeight: 0,
        offsetHeight: 32, _parent: null,
        classList: {
            _s: new Set(),
            add(...n) { n.forEach(x => this._s.add(x)); },
            remove(...n) { n.forEach(x => this._s.delete(x)); },
            toggle(n, f) { const on = f === undefined ? !this._s.has(n) : Boolean(f); if (on) this._s.add(n); else this._s.delete(n); return on; },
            contains(n) { return this._s.has(n); },
        },
        setAttribute() {}, getAttribute() { return null; }, removeAttribute() {}, hasAttribute() { return false; },
        focus() {}, blur() {}, scrollIntoView() {}, click() {},
        addEventListener() { this._listeners += 1; }, removeEventListener() {},
        appendChild(child) { if (child) { child._parent = this; this._children.push(child); } return child; },
        append(...cs) { cs.forEach(c => this.appendChild(c)); },
        replaceChildren(...cs) { this._children = []; cs.forEach(c => this.appendChild(c)); },
        insertBefore(c) { return this.appendChild(c); },
        remove() {},
        querySelector() { return makeEl('div'); },
        querySelectorAll() { return []; },
        closest() { return null; },
        getContext() { return { drawImage() {}, clearRect() {}, fillRect() {} }; },
        toBlob(cb) { cb(null); },
        getBoundingClientRect() { return { top: 0, left: 0, width: 100, height: 20 }; },
        get children() { return this._children; },
        get childElementCount() { return this._children.length; },
        get firstChild() { return this._children[0] || null; },
        get parentElement() { return this._parent || (this._parent = makeEl('span')); },
        set parentElement(v) { this._parent = v; },
        get parentNode() { return this._parent; },
    };
    return el;
}

const storageMaps = { projectStatsCache: new Map(), nodeStatsCache: new Map() };
const documentStub = {
    createElement: tag => makeEl(tag),
    createDocumentFragment: () => { const f = makeEl('div'); f._isFragment = true; return f; },
    querySelector: () => makeEl('div'),
    querySelectorAll: () => [],
    addEventListener() {}, removeEventListener() {},
    body: makeEl('body'),
};
const windowStub = {
    document: documentStub, location: { protocol: 'http:', search: '' },
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    getComputedStyle: () => ({ getPropertyValue: () => '' }),
    setTimeout: (fn) => { if (typeof fn === 'function') fn(); return 0; },
    clearTimeout() {}, requestAnimationFrame: fn => fn(), console,
    navigator: { userAgent: 'node' }, innerWidth: 1280,
};
windowStub.window = windowStub;

// 抽出渲染与序列化需要的真实函数
const bundle = [
    'generateId', 'todayStr', 'cloneData', 'isValidIsoDate', 'daysBetween',
    'normalizeAssessment', 'normalizeNode', 'normalizeProjects', 'normalizeProjectSummary',
    'serializeProject', 'skipViewState', 'projectStateJson', 'projectAutoReview', 'formatEstimate', 'dueBadgeInfo', 'describeRepeat',
    'cleanRepeat', 'buildRepeatRule', 'createNodeMetaBadges', 'getNodeCompletionState',
    'setRowCompletionVisual', 'nodeByIdMap', 'escapeHtmlText', 'richToHtml', 'formatBytes',
    'findNodeById', 'findParentList', 'nodeMatchesOwnFilter', 'nodeHasVisibleMatch',
    'isNodeFiltering', 'nodeMatchesMetaFilter', 'nodeMatchesStatus', 'getProjectTotal',
    'normalizeNodeReview', 'normalizeNodeMeta', 'cleanPriority', 'cleanDueDate',
    'cleanEstimateMinutes', 'cleanTags', 'cleanLinks', 'normalizeAssessmentFiles',
    'treeHasAssessment', 'applyAssessmentRequirements', 'ensureUniqueIds',
    'getNodeStats', 'computeNodeStats', 'getChildrenStats', 'nodeStatsOf',
    'getProjectRemaining', 'getProjectOptionalStats', 'renderNode', 'renderDetail',
];
const prelude = `
    const WEEKDAY_NAMES = ['日','一','二','三','四','五','六'];
    const PROJECT_STATE_SKIP_KEYS = new Set(['expanded', '_revision', 'stats']);
    const DATA_SCHEMA_VERSION = 2;
    const NODE_PRIORITIES = ['', 'high', 'mid', 'low'];
    const MAX_TAGS = 20;
    const MAX_TAG_CHARS = 40;
    const MAX_NOTE_CHARS = 20000;
    const MAX_LINKS = 20;
    const MAX_LINK_CHARS = 2000;
    const MAX_ESTIMATE_MINUTES = 60 * 24 * 30;
    const MAX_ASSESSMENT_FILES = 10;
    let projects = [];
    let currentProjectId = null;
    const nodeFilters = { query: '', status: 'all', priority: 'all', due: 'all', tag: '' };
    let batchState = { active: false, selected: new Set() };
    let projectStatsCache = new Map();
    let nodeStatsCache = new Map();
    function getCurrentProject() { return projects.find(p => p.id === currentProjectId) || null; }
    function markProjectDirty() {}
    function ensureProjectCaches() {}
    function refreshProjectCaches() {}
    function renderNodeBadges() {}
    function updateBranch() {}
    function refreshItemCompletion() {}
    function collectReviewMatches() { return []; }
    function assessmentBadgeFor() { return null; }
    function isAssessmentPassed() { return false; }
    function openAssessment() {}
    function openScheduleReview() {}
    function openNodeMeta() {}
    function startEditNode() {}
    function startAddChild() {}
    function deleteNode() {}
    function toggleNodeCompleted() {}
    function openFileItPicker() {}
    function renderChildren() {}
    function attachDragHandlers() {}
    function createNodeMetaBadges() { return null; }
    function searchMatchesNode() { return false; }
    function getNodeSearchText() { return ''; }
    const detailView = document.createElement('div');
    const treeRoot = document.createElement('div');
`;
const sandboxSource = `${prelude}\n${bundle.map(name => {
    try { return extract(name); } catch (error) { return `    function ${name}() {}`; }
}).join('\n')}\n
    return { renderNode, normalizeProjects, serializeProject: (typeof serializeProject === 'function' ? serializeProject : null), projectStateJson: (typeof projectStateJson === 'function' ? projectStateJson : null) };`;
const factory = new Function('window', 'document', 'console', 'Math', 'Date', 'JSON', 'Number',
    'String', 'Array', 'Object', 'Boolean', 'Set', 'Map', 'RegExp', 'Error', 'isNaN', 'parseInt',
    'parseFloat', 'encodeURIComponent', 'decodeURIComponent', sandboxSource);
const api = factory(windowStub, documentStub, console, Math, Date, JSON, Number, String, Array,
    Object, Boolean, Set, Map, RegExp, Error, isNaN, parseInt, parseFloat, encodeURIComponent,
    decodeURIComponent);

function buildTree(total) {
    const weeks = total > 4000 ? 20 : 10;
    const daysPerWeek = 10;
    const itemsPerDay = Math.max(1, Math.floor(total / (weeks * daysPerWeek)));
    let index = 0;
    const tree = [];
    for (let w = 1; w <= weeks; w += 1) {
        const week = { id: `w${w}`, type: 'week', text: `第${w}周`, completed: false, expanded: w === 1,
                       createdAt: '2026-09-16', children: [] };
        for (let d = 1; d <= daysPerWeek; d += 1) {
            const day = { id: `w${w}d${d}`, type: 'day', text: `单元${d}`, completed: false,
                          expanded: d === 1, createdAt: '2026-09-16', children: [] };
            for (let i = 0; i < itemsPerDay; i += 1) {
                index += 1;
                day.children.push({
                    id: `i${index}`, type: 'item', text: `任务 ${index}：解释并举例`, completed: index % 4 === 0,
                    completedAt: index % 4 === 0 ? '2026-09-16T08:00:00' : null, optional: index % 7 === 0,
                    assessmentRequired: false, assessmentHistory: 0, assessment: null,
                    createdAt: '2026-09-16', children: [], priority: ['high', 'mid', 'low', ''][index % 4],
                    dueDate: '2026-09-20', estimateMinutes: (index % 6) * 15, tags: ['基线'],
                    note: index % 3 === 0 ? '备注' : '', links: [],
                });
            }
            week.children.push(day);
        }
        tree.push(week);
    }
    return tree;
}

function median(samples) {
    const sorted = [...samples].sort((a, b) => a - b);
    return sorted[Math.floor(sorted.length / 2)];
}

console.log(`${'指标'.padEnd(44)}${'1000 任务'.padStart(14)}${'10000 任务'.padStart(14)}`);
console.log('-'.repeat(72));
const rows = {};
for (const total of [1000, 10000]) {
    const project = { id: 'p1', name: '基线', description: '', createdAt: '2026-09-16',
                      assessmentEnabled: false, reviewEnabled: true, archived: false, tree: buildTree(total) };
    const items = [];
    (function walk(nodes) { (nodes || []).forEach(n => { if (n.type === 'item') items.push(n); walk(n.children); }); })(project.tree);

    // 1) 保存前序列化：normalizeProjects + serializeProject + JSON.stringify
    const serializeSamples = [];
    for (let i = 0; i < 5; i += 1) {
        const start = process.hrtime.bigint();
        const normalized = api.normalizeProjects([project]);
        const text = JSON.stringify(api.serializeProject(normalized[0]));
        const ms = Number(process.hrtime.bigint() - start) / 1e6;
        serializeSamples.push(ms);
        rows[total] = rows[total] || {};
        rows[total].bytes = Buffer.byteLength(text);
    }
    rows[total].serialize = median(serializeSamples).toFixed(1);

    // 1b) 节点级 patch 之前的"内存 vs 服务端"指纹：每次勾选都会算一次，必须便宜
    if (api.projectStateJson) {
        const fingerprintSamples = [];
        for (let i = 0; i < 5; i += 1) {
            const normalized = api.normalizeProjects([project])[0];
            const start = process.hrtime.bigint();
            const fingerprint = api.projectStateJson(api.serializeProject(normalized));
            fingerprintSamples.push(Number(process.hrtime.bigint() - start) / 1e6);
            rows[total].fingerprintBytes = Buffer.byteLength(fingerprint);
        }
        rows[total].fingerprint = median(fingerprintSamples).toFixed(1);
    }

    // 2) 渲染：折叠状态（只有周行）
    created = 0;
    let start = process.hrtime.bigint();
    const collapsed = documentStub.createElement('ul');
    project.tree.forEach(week => collapsed.appendChild(api.renderNode(week, '2026-09-16', false)));
    rows[total].collapsedMs = (Number(process.hrtime.bigint() - start) / 1e6).toFixed(1);
    rows[total].collapsedEls = created;

    // 3) 渲染：展开一周（10 单元 × 每单元任务）
    created = 0;
    const expanded = { ...project.tree[0], expanded: true };
    start = process.hrtime.bigint();
    const expandedEl = api.renderNode(expanded, '2026-09-16', false);
    rows[total].oneWeekMs = (Number(process.hrtime.bigint() - start) / 1e6).toFixed(1);
    rows[total].oneWeekEls = created;
    rows[total].items = items.length;
}

const labels = [['items', '任务数'], ['bytes', '保存载荷(字节)'], ['serialize', '保存前序列化(ms)'],
                ['fingerprint', '整树指纹(ms)（基线/flush 用）'], ['fingerprintBytes', '整树指纹(字节)'],
                ['collapsedMs', '渲染-全部折叠(ms)'], ['collapsedEls', '渲染-全部折叠(元素数)'],
                ['oneWeekMs', '渲染-展开1周(ms)'], ['oneWeekEls', '渲染-展开1周(元素数)']];
for (const [key, label] of labels) {
    console.log(`${label.padEnd(44)}${String(rows[1000][key]).padStart(14)}${String(rows[10000][key]).padStart(14)}`);
}
