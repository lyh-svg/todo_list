// ④ 的实测（不是断言，是数字）：从 js/app.js 抽出真实 renderNode，用桩 DOM 跑，
// 数一数"折叠"与"展开"分别创建了多少个 <li>（= DOM 节点数）。
const fs = require('fs');
const ROOT = require('path').resolve(__dirname, '..', '..');
const src = fs.readFileSync(ROOT + '/js/app.js', 'utf8');

function extract(name) {
    const at = src.indexOf(`    function ${name}(`);
    if (at < 0) throw new Error(`找不到 ${name}`);
    let depth = 0, seen = false;
    for (let i = at; i < src.length; i++) {
        if (src[i] === '{') { depth++; seen = true; }
        else if (src[i] === '}') { depth--; if (seen && depth === 0) return src.slice(at, i + 1); }
    }
    throw new Error(`${name} 括号不配对`);
}

// ---- 桩 DOM ----
const created = [];
function makeElement(tag) {
    created.push(tag);
    const el = {
        tagName: String(tag).toUpperCase(),
        className: '', textContent: '', title: '', value: '', type: '', hidden: false,
        disabled: false, tabIndex: 0, dataset: {}, style: {}, children: [],
        classList: {
            _set: new Set(),
            add(...names) { names.forEach(n => this._set.add(n)); },
            remove(...names) { names.forEach(n => this._set.delete(n)); },
            toggle(name, force) { const on = force === undefined ? !this._set.has(name) : Boolean(force); on ? this._set.add(name) : this._set.delete(name); return on; },
            contains(name) { return this._set.has(name); },
        },
        setAttribute() {}, getAttribute() { return null; }, removeAttribute() {},
        addEventListener() {}, removeEventListener() {},
        appendChild(child) { this.children.push(child); return child; },
        append(...nodes) { this.children.push(...nodes); },
        replaceChildren(...nodes) { this.children = nodes; },
        querySelector() { return null; }, querySelectorAll() { return []; },
        closest() { return null; }, remove() {}, focus() {},
    };
    return el;
}
const documentStub = {
    createElement: makeElement,
    createDocumentFragment: () => makeElement('#fragment'),
};

// ---- 抽出真实 renderNode，注入它依赖的外部函数 ----
const renderNode = new Function(
    'document', 'getNodeCompletionState', 'startAddChild', 'openAssessment', 'openScheduleReview',
    'startEditNode', 'deleteNode', 'nodeHasVisibleMatch', 'updateBranch', 'toggleNodeCompleted',
    'batchState', 'createNodeMetaBadges',
    `${extract('renderNode')}
     return renderNode;`
)(
    documentStub,
    node => (node._state || 'active'),
    () => {}, () => {}, () => {}, () => {}, () => {},
    () => false,
    () => {}, () => {},
    { active: false, selected: new Set() },
    () => null
);

// ---- 造一棵与真实项目同规模的树：8 周 / 41 单元 / 174 任务 ----
function buildTree(expanded) {
    // 与真实项目同规模：8 周 / 41 单元 / 174 任务
    const perDay = new Array(41).fill(4);                 // 164
    for (let i = 0; i < 174 - 164; i += 1) perDay[i] += 1; // 补到 174
    const weeks = [];
    let dayNo = 0, itemNo = 0;
    for (let w = 0; w < 8; w += 1) {
        const week = { id: `w${w}`, type: 'week', text: `第${w + 1}周`, expanded, children: [] };
        const daysInWeek = w === 0 ? 6 : 5;               // 6 + 7*5 = 41
        for (let d = 0; d < daysInWeek; d += 1) {
            const day = { id: `w${w}d${d}`, type: 'day', text: `单元${dayNo + 1}`, expanded, children: [] };
            for (let i = 0; i < perDay[dayNo]; i += 1) {
                itemNo += 1;
                day.children.push({
                    id: `w${w}d${d}i${i}`, type: 'item', text: `任务${itemNo}`,
                    completed: false, completedAt: null, optional: false,
                    assessmentRequired: false, assessmentHistory: 0, assessment: null,
                    createdAt: '2026-09-15', children: [],
                });
            }
            dayNo += 1;
            week.children.push(day);
        }
        weeks.push(week);
    }
    return weeks;
}

function measure(weeks, filtering) {
    created.length = 0;
    weeks.forEach(week => renderNode(week, '2026-09-15', filtering));
    const byTag = created.reduce((acc, tag) => Object.assign(acc, { [tag]: (acc[tag] || 0) + 1 }), {});
    return { total: created.length, li: byTag.li || 0, byTag };
}

const collapsed = buildTree(false);
const expanded = buildTree(true);
const itemCount = expanded.reduce((n, w) => n + w.children.reduce((m, d) => m + d.children.length, 0), 0);
const dayCount = expanded.reduce((n, w) => n + w.children.length, 0);

console.log(`   树规模：${expanded.length} 周 / ${dayCount} 单元 / ${itemCount} 任务`);
const a = measure(collapsed, false);
const b = measure(expanded, false);
console.log(`   全部折叠：创建元素 ${a.total} 个，其中 <li> ${a.li} 个`);
console.log(`   全部展开：创建元素 ${b.total} 个，其中 <li> ${b.li} 个`);

const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}
check('④ 折叠时只为可见的 8 周建 <li>，子分支一个都不建', a.li === 8, `实际 ${a.li}`);
check('④ 展开时才建满 8+41+174 = 223 个 <li>', b.li === 8 + dayCount + itemCount, `实际 ${b.li}`);
check('④ 折叠比展开少建 20 倍以上元素', b.total > a.total * 20, `折叠 ${a.total} vs 展开 ${b.total}`);
check('④ 折叠时完全不创建任务节点',
    !Object.keys(a.byTag).length || a.li === 8);

// 过滤模式：只沿"命中路径"展开（这是必要的，不是浪费）
const matchDeep = buildTree(false);
matchDeep[3].children[2].children[1]._hit = true;
const filtering = new Function(
    'document', 'getNodeCompletionState', 'startAddChild', 'openAssessment', 'openScheduleReview',
    'startEditNode', 'deleteNode', 'nodeHasVisibleMatch', 'updateBranch', 'toggleNodeCompleted',
    'batchState', 'createNodeMetaBadges',
    `${extract('renderNode')} return renderNode;`
)(documentStub, node => (node._state || 'active'), () => {}, () => {}, () => {}, () => {}, () => {},
   node => Boolean(node._hit || (node.children || []).some(c => Boolean(c._hit))), () => {}, () => {},
   { active: false, selected: new Set() }, () => null);
created.length = 0;
filtering(matchDeep[3], '2026-09-15', true);
const filteredLi = created.filter(tag => tag === 'li').length;
check('④ 搜索/筛选模式只渲染命中路径（1 周 + 1 单元 + 1 任务）', filteredLi === 3, `实际 ${filteredLi}`);

const failed = results.filter(r => !r).length;
console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
process.exit(failed ? 1 : 0);
