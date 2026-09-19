// P5 验证：树行事件委托 + 筛选只遍历一遍。
//
// 1) 静态：renderNode 里不再有任何 addEventListener；treeRoot 上挂一组委托；
//    注册表在 renderNode 里登记；renderDetail 一次遍历算 visibleIds。
// 2) 行为：用真实抽出来的 renderNode + 委托处理器（配最小 DOM 桩）真的派发事件，
//    断言点复选框/点行/点按钮/双击/键盘/拖拽各自叫到了谁、带的是哪个节点。
// 3) 筛选：collectVisibleNodeIds 对每个节点只判断一次，并和旧的"顶层 filter + 每层再
//    filter"两段式遍历对比调用次数（旧写法会重复走进子树）。
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..', '..');
const src = fs.readFileSync(path.join(ROOT, 'js', 'app.js'), 'utf8');

function extract(name) {
    let at = src.indexOf(`    async function ${name}(`);
    if (at < 0) at = src.indexOf(`    function ${name}(`);
    if (at < 0) throw new Error('找不到 ' + name);
    let depth = 0, seen = false;
    for (let i = at; i < src.length; i++) {
        if (src[i] === '{') { depth++; seen = true; }
        else if (src[i] === '}') { depth--; if (seen && depth === 0) return src.slice(at, i + 1); }
    }
    throw new Error(name + ' 括号不配对');
}

function sliceConst(name) {
    const at = src.indexOf(`    const ${name} = [`);
    if (at < 0) throw new Error('找不到 const ' + name);
    const end = src.indexOf('];', at);
    return src.slice(at, end + 2);
}

const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}

// ---------------- 最小 DOM 桩（带冒泡 + closest，与 dom-smoke 同口径） ----------------
function makeEl(tag = 'div') {
    const el = {
        tagName: String(tag).toUpperCase(), _children: [], _listeners: {}, _parentElement: null,
        style: {}, dataset: {}, id: '', textContent: '', innerHTML: '', value: '', checked: false,
        hidden: false, disabled: false, type: '', title: '', placeholder: '', tabIndex: 0,
        draggable: false, className: '',
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
        setAttribute() {}, getAttribute() { return null; }, removeAttribute() {}, hasAttribute() { return false; },
        focus() {}, blur() {}, scrollIntoView() {},
        addEventListener(type, fn) { (this._listeners[type] ||= []).push(fn); },
        removeEventListener(type, fn) { this._listeners[type] = (this._listeners[type] || []).filter(f => f !== fn); },
        dispatch(type, event = {}) {
            const evt = {
                type, target: this, currentTarget: this, key: '', clientY: 0,
                preventDefault() { evt.defaultPrevented = true; },
                stopPropagation() { evt._stopped = true; },
                ...event,
            };
            let node = this;
            while (node) {
                (node._listeners[type] || []).forEach(fn => fn({ ...evt, currentTarget: node }));
                if (evt._stopped) break;
                node = node._parentElement || null;
            }
            return evt;
        },
        appendChild(child) { if (child) { child._parentElement = this; this._children.push(child); } return child; },
        append(...children) { children.forEach(c => this.appendChild(c)); },
        replaceChildren(...children) { this._children = []; children.forEach(c => this.appendChild(c)); },
        closest(selector) {
            const text = String(selector || '').trim();
            const classOnly = /^\.([\w-]+)$/.exec(text);
            const idOnly = /^#([\w-]+)$/.exec(text);
            let node = this;
            while (node) {
                if (classOnly && node.classList.contains(classOnly[1])) return node;
                if (idOnly && node.id === idOnly[1]) return node;
                if (!classOnly && !idOnly && node.tagName && node.tagName.toLowerCase() === text) return node;
                node = node._parentElement || null;
            }
            return null;
        },
        querySelector(selector) { return findAll(this, el => matches(el, selector))[0] || null; },
        querySelectorAll(selector) { return findAll(this, el => matches(el, selector)); },
        get children() { return this._children; },
        get firstChild() { return this._children[0] || null; },
        get childElementCount() { return this._children.length; },
        get parentElement() { return this._parentElement; },
        set parentElement(value) { this._parentElement = value; },
        get parentNode() { return this._parentElement; },
    };
    Object.defineProperty(el, 'className', {
        get() { return [...el.classList._s].join(' '); },
        set(value) { el.classList._s = new Set(String(value || '').split(/\s+/).filter(Boolean)); },
    });
    return el;
}

function findAll(root, predicate, out = []) {
    (root._children || []).forEach(child => {
        if (predicate(child)) out.push(child);
        findAll(child, predicate, out);
    });
    return out;
}

function matches(el, selector) {
    const text = String(selector || '').trim();
    const classOnly = /^\.([\w-]+)$/.exec(text);
    if (classOnly) return el.classList.contains(classOnly[1]);
    return el.tagName && el.tagName.toLowerCase() === text;
}

function countListeners(root) {
    let total = 0;
    const walk = node => {
        total += Object.values(node._listeners || {}).reduce((sum, list) => sum + list.length, 0);
        (node._children || []).forEach(walk);
    };
    walk(root);
    return total;
}

// ---------------- 组装沙箱：真实 renderNode + 真实委托处理器 ----------------
function buildWorld() {
    const calls = [];
    const documentStub = {
        createElement: tag => makeEl(tag),
        createDocumentFragment: () => { const fragment = makeEl('#fragment'); fragment._isFragment = true; return fragment; },
    };
    const treeRoot = makeEl('ul');
    const state = {
        renderedNodeEntries: new Map(), treeDelegationReady: false, dragState: null,
        batchState: { active: false, selected: new Set() }, nodeFilters: { query: '', status: 'all', priority: 'all', due: 'all', tag: '' },
        currentProject: { id: 'p1', createdAt: '2026-09-15' },
        filterMatchedIds: null,
    };
    const deps = {
        document: documentStub, treeRoot, state, calls,
        // 图标走 sprite 引用（iconEl 在真实 app.js 里；沙箱里给个同名桩）
        iconEl: () => makeEl('span'),
        getCurrentProject: () => state.currentProject,
        getNodeCompletionState: node => (node.completed ? 'completed' : 'active'),
        createNodeMetaBadges: node => {
            if (!node.note && !node.dueDate) return null;
            const wrap = makeEl('span');
            wrap.classList.add('node-meta');
            return wrap;
        },
        startAddChild: (node) => calls.push(['startAddChild', String(node.id)]),
        openAssessment: node => calls.push(['openAssessment', String(node.id)]),
        openScheduleReview: node => calls.push(['openScheduleReview', String(node.id)]),
        openNodeMeta: node => calls.push(['openNodeMeta', String(node.id)]),
        startEditNode: (node, textSpan) => calls.push(['startEditNode', String(node.id), textSpan && textSpan.classList.contains('node-text')]),
        deleteNode: (node, row) => calls.push(['deleteNode', String(node.id), row && row.classList.contains('node-row')]),
        duplicateNodeWithOptions: node => calls.push(['duplicateNodeWithOptions', String(node.id)]),
        openMoveNodeDialog: node => calls.push(['openMoveNodeDialog', String(node.id)]),
        updateBranch: (node) => calls.push(['updateBranch', String(node.id)]),
        toggleNodeCompletedSafely: node => calls.push(['toggleNodeCompletedSafely', String(node.id)]),
        toggleBatchSelection: node => calls.push(['toggleBatchSelection', String(node.id)]),
        batchKey: (projectId, nodeId) => `${projectId}:${nodeId}`,
        dropTargetFor: () => ({ mode: 'after', node: { id: 'x' } }),
        clearDropHints: () => calls.push(['clearDropHints']),
        applyDrop: target => { calls.push(['applyDrop', target.mode]); return Promise.resolve(); },
        // 旧实现（修复前）用得到；新实现不再引用，留着只为让"跑在旧代码上"能走到断言
        attachDragHandlers: () => {},
        nodeHasVisibleMatch: () => false,
        nodeMatchesOwnFilter: node => {
            calls.push(['nodeMatchesOwnFilter', String(node.id)]);
            return state.filterMatchedIds ? state.filterMatchedIds.has(String(node.id)) : false;
        },
    };
    // 函数不存在时退化成空桩，好让"改坏了"表现为断言失败而不是脚本崩溃
    const tolerant = name => {
        try {
            return extract(name);
        } catch (error) {
            return `    function ${name}() {}`;
        }
    };
    let handlerTable = 'const TREE_ACTION_HANDLERS = [];';
    try {
        handlerTable = sliceConst('TREE_ACTION_HANDLERS');
    } catch (error) {
        handlerTable = 'const TREE_ACTION_HANDLERS = [];';
    }
    const body = [
        tolerant('renderNode'), tolerant('collectVisibleNodeIds'), tolerant('treeEntryFor'), handlerTable,
        tolerant('handleTreeClick'), tolerant('handleTreeKeydown'), tolerant('handleTreeDblClick'),
        tolerant('handleTreeDragStart'), tolerant('handleTreeDragEnd'), tolerant('handleTreeDragOver'),
        tolerant('handleTreeDragLeave'), tolerant('handleTreeDrop'), tolerant('ensureTreeDelegation'),
    ].join('\n');
    const prelude = `
        const { document, treeRoot, state, calls, getCurrentProject, getNodeCompletionState,
                createNodeMetaBadges, startAddChild, openAssessment, openScheduleReview, openNodeMeta,
                startEditNode, deleteNode, duplicateNodeWithOptions, openMoveNodeDialog, updateBranch,
                toggleNodeCompletedSafely, toggleBatchSelection, batchKey, dropTargetFor, clearDropHints,
                applyDrop, nodeMatchesOwnFilter, attachDragHandlers, nodeHasVisibleMatch, iconEl } = deps;
        const renderedNodeEntries = state.renderedNodeEntries;
        let treeDelegationReady = state.treeDelegationReady;
        let dragState = state.dragState;
        const batchState = state.batchState;
        const nodeFilters = state.nodeFilters;
    `;
    const factory = new Function('deps', `${prelude}\n${body}\n
        return { renderNode, collectVisibleNodeIds, ensureTreeDelegation, treeRoot,
                 entries: () => renderedNodeEntries,
                 dragState: () => dragState,
                 setDelegationReady: v => { treeDelegationReady = v; state.treeDelegationReady = v; } };`);
    const api = factory(deps);
    return { api, state, calls, treeRoot, documentStub };
}

const item = (id, text, extra = {}) => Object.assign({
    id, type: 'item', text, completed: false, completedAt: null, optional: false,
    assessmentRequired: false, assessmentHistory: 0, assessment: null, createdAt: '2026-09-15', children: [],
}, extra);
const day = (id, text, children, extra = {}) => Object.assign({
    id, type: 'day', text, completed: false, expanded: true, createdAt: '2026-09-15', children,
}, extra);
const week = (id, text, children, extra = {}) => Object.assign({
    id, type: 'week', text, completed: false, expanded: true, createdAt: '2026-09-15', children,
}, extra);

// 取某个节点自己的行（li.dataset.id === id），再在行内找元素——
// 直接 findAll 会拿到整棵树里第一个 .checkbox（那是周的），断言就会张冠李戴。
function rowFor(root, id) {
    return findAll(root, el => el.classList.contains('node-row')
        && el._parentElement && String(el._parentElement.dataset.id) === String(id))[0];
}
function inRow(root, id, className) {
    const row = rowFor(root, id);
    return row ? findAll(row, el => el.classList.contains(className))[0] : null;
}

function renderInto(world, node) {
    const li = world.api.renderNode(node, '2026-09-15');
    world.treeRoot.appendChild(li);
    return li;
}

// ---------------- 静态断言 ----------------
check('静态：renderNode 里没有任何 addEventListener',
    !/addEventListener/.test(extract('renderNode')));
check('静态：renderNode 会登记渲染注册表（委托靠它反查节点）',
    /renderedNodeEntries\.set\(String\(node\.id\), \{ node, li, row, textSpan \}\)/.test(src));
check('静态：treeRoot 上挂了 8 个委托事件',
    /function ensureTreeDelegation\(\)[\s\S]{0,900}addEventListener\('click'[\s\S]{0,120}addEventListener\('keydown'[\s\S]{0,120}addEventListener\('dblclick'[\s\S]{0,120}addEventListener\('dragstart'[\s\S]{0,120}addEventListener\('dragend'[\s\S]{0,120}addEventListener\('dragover'[\s\S]{0,120}addEventListener\('dragleave'[\s\S]{0,120}addEventListener\('drop'/.test(src));
check('静态：initEvents 里挂上委托', /function initEvents\(\) \{\s*\r?\n\s*ensureTreeDelegation\(\);/.test(src));
check('静态：筛选只遍历一遍（renderDetail 里用 collectVisibleNodeIds）',
    /collectVisibleNodeIds\(project\.tree, visibleIds\)/.test(src)
    && /project\.tree\.filter\(week => visibleIds\.has\(String\(week\.id\)\)\)/.test(src));
check('静态：renderNode 的子节点筛选改成 O(1) 查表',
    /filter\(child => visibleIds\.has\(String\(child\.id\)\)\)/.test(src));
check('静态：旧的 nodeHasVisibleMatch 已删除（不再有重复子树遍历的入口）',
    !/nodeHasVisibleMatch/.test(src));

// ---------------- 行为：每行 0 监听器 ----------------
{
    const world = buildWorld();
    const li = renderInto(world, week('w1', '第1周', [day('d1', '单元1', [item('i1', '任务1'), item('i2', '任务2')])]));
    check('行为：渲染出来的整棵子树里监听器数为 0（不再每行挂闭包）',
        countListeners(li) === 0, String(countListeners(li)));
    check('行为：行仍然可拖拽', findAll(li, el => el.classList.contains('node-row')).every(row => row.draggable === true));
    check('行为：注册表登记了每个节点（周+单元+2 任务 = 4 个）',
        world.api.entries().size === 4, String(world.api.entries().size));

    // 挂上委托（模拟 initEvents），之后所有事件都从 treeRoot 分发
    world.api.ensureTreeDelegation();
    check('行为：委托挂在 treeRoot 上（8 个）', countListeners(world.treeRoot) === 8, String(countListeners(world.treeRoot)));
}

// ---------------- 行为：点复选框 / 点行 / 按钮 / 双击 / 键盘 ----------------
{
    const world = buildWorld();
    const li = renderInto(world, week('w1', '第1周', [day('d1', '单元1', [item('i1', '任务1', { note: '有备注' })])]));
    world.api.ensureTreeDelegation();
    const find = cls => inRow(li, 'i1', cls);

    world.calls.length = 0;
    find('checkbox').dispatch('click');
    check('行为：点复选框 → 切换完成（不触发行点击的展开）',
        JSON.stringify(world.calls) === JSON.stringify([['toggleNodeCompletedSafely', 'i1']]), JSON.stringify(world.calls));

    world.calls.length = 0;
    find('node-text').dispatch('click');
    check('行为：点任务行 → 切换完成',
        JSON.stringify(world.calls) === JSON.stringify([['toggleNodeCompletedSafely', 'i1']]), JSON.stringify(world.calls));

    world.calls.length = 0;
    world.state.batchState.active = true;
    find('checkbox').dispatch('click');
    check('行为：批量模式下点复选框 → 选中而不是切换完成',
        JSON.stringify(world.calls) === JSON.stringify([['toggleBatchSelection', 'i1']]), JSON.stringify(world.calls));
    world.state.batchState.active = false;

    world.calls.length = 0;
    find('edit-btn').dispatch('click');
    check('行为：点 ✎ → startEditNode（带对的 node-text 与 node-row）',
        JSON.stringify(world.calls) === JSON.stringify([['startEditNode', 'i1', true]]), JSON.stringify(world.calls));

    world.calls.length = 0;
    find('delete-btn').dispatch('click');
    check('行为：点 ✕ → deleteNode（带对的 row）',
        JSON.stringify(world.calls) === JSON.stringify([['deleteNode', 'i1', true]]), JSON.stringify(world.calls));

    world.calls.length = 0;
    find('move-btn').dispatch('click');
    check('行为：点 ⇄ → openMoveNodeDialog', JSON.stringify(world.calls) === JSON.stringify([['openMoveNodeDialog', 'i1']]));

    world.calls.length = 0;
    find('copy-btn').dispatch('click');
    check('行为：点 ⧉ → duplicateNodeWithOptions', JSON.stringify(world.calls) === JSON.stringify([['duplicateNodeWithOptions', 'i1']]));

    world.calls.length = 0;
    find('meta-btn').dispatch('click');
    check('行为：点 ⋯ → openNodeMeta', JSON.stringify(world.calls) === JSON.stringify([['openNodeMeta', 'i1']]));

    world.calls.length = 0;
    find('node-meta').dispatch('click');
    check('行为：点元数据徽标 → openNodeMeta（原来挂在徽标容器上）',
        JSON.stringify(world.calls) === JSON.stringify([['openNodeMeta', 'i1']]), JSON.stringify(world.calls));

    world.calls.length = 0;
    find('node-text').dispatch('dblclick');
    check('行为：双击任务文字 → startEditNode',
        JSON.stringify(world.calls) === JSON.stringify([['startEditNode', 'i1', true]]), JSON.stringify(world.calls));

    world.calls.length = 0;
    find('checkbox').dispatch('keydown', { key: 'Enter' });
    check('行为：复选框上按 Enter → 切换完成',
        JSON.stringify(world.calls) === JSON.stringify([['toggleNodeCompletedSafely', 'i1']]), JSON.stringify(world.calls));

    world.calls.length = 0;
    find('node-text').dispatch('keydown', { key: 'Enter' });
    check('行为：文字上按 Enter → 不动作（原来只绑在复选框上）',
        world.calls.length === 0, JSON.stringify(world.calls));

    // 容器：点行展开、点 + 添加子项
    world.calls.length = 0;
    const weekRow = findAll(li, el => el.classList.contains('node-row'))[0];
    weekRow.dispatch('click');
    check('行为：点周行 → updateBranch 展开',
        JSON.stringify(world.calls) === JSON.stringify([['updateBranch', 'w1']]), JSON.stringify(world.calls));

    world.calls.length = 0;
    inRow(li, 'w1', 'add-btn').dispatch('click');
    check('行为：点 + → startAddChild',
        JSON.stringify(world.calls) === JSON.stringify([['startAddChild', 'w1']]), JSON.stringify(world.calls));
}

// ---------------- 行为：拖拽走委托 ----------------
{
    const world = buildWorld();
    renderInto(world, week('w1', '第1周', [day('d1', '单元1', [item('i1', '任务1'), item('i2', '任务2')])]));
    world.api.ensureTreeDelegation();
    const rows = findAll(world.treeRoot, el => el.classList.contains('node-row'));
    const rowOf = id => findAll(world.treeRoot, el => el.classList.contains('node-row'))
        .find(row => row._parentElement && String(row._parentElement.dataset.id) === id);

    world.calls.length = 0;
    rowOf('i1').dispatch('dragstart', { dataTransfer: { setData() {} } });
    check('行为：dragstart → 记住拖拽来源并给该行加 dragging 类',
        world.api.dragState() && String(world.api.dragState().nodeId) === 'i1'
        && rowOf('i1')._parentElement.classList.contains('dragging'));

    world.calls.length = 0;
    const overEvent = rowOf('i2').dispatch('dragover', { dataTransfer: {} });
    check('行为：dragover → preventDefault + 落点提示 + 清掉其它提示',
        overEvent.defaultPrevented === true
        && rowOf('i2').classList.contains('drop-after')
        && world.calls.some(call => call[0] === 'clearDropHints'), JSON.stringify(world.calls));

    rowOf('i2').dispatch('dragleave');
    check('行为：dragleave → 去掉落点提示',
        !rowOf('i2').classList.contains('drop-after') && !rowOf('i2').classList.contains('drop-before'));

    world.calls.length = 0;
    rowOf('i2').dispatch('drop', { dataTransfer: {} });
    check('行为：drop → 走 applyDrop（落库仍走原来的 reorder 路径）',
        world.calls.some(call => call[0] === 'applyDrop'), JSON.stringify(world.calls));

    rowOf('i1').dispatch('dragend');
    check('行为：dragend → 清空拖拽状态与 dragging 类',
        world.api.dragState() === null && !rowOf('i1')._parentElement.classList.contains('dragging'));
    check('行为：拖拽期间不会误触"点行切换完成"',
        !world.calls.some(call => call[0] === 'toggleNodeCompletedSafely'), JSON.stringify(world.calls));
    void rows;
}

// ---------------- 筛选：一次遍历 vs 旧的重复遍历 ----------------
{
    const tree = [];
    for (let w = 1; w <= 20; w += 1) {
        const days = [];
        for (let d = 1; d <= 10; d += 1) {
            const items = [];
            for (let i = 1; i <= 50; i += 1) items.push(item(`w${w}d${d}i${i}`, `任务 ${w}-${d}-${i}`));
            days.push(day(`w${w}d${d}`, `单元${d}`, items));
        }
        tree.push(week(`w${w}`, `第${w}周`, days));
    }
    const totalNodes = 20 + 200 + 10000;

    // 新实现：一次遍历
    const world = buildWorld();
    world.calls.length = 0;
    const matched = new Set();
    const any = world.api.collectVisibleNodeIds(tree, matched);
    const visits = world.calls.filter(call => call[0] === 'nodeMatchesOwnFilter').length;
    check('筛选：collectVisibleNodeIds 对每个节点只判断一次',
        visits === totalNodes, `${visits} vs ${totalNodes}`);
    check('筛选：命中集合为空时返回 false（用于"没有符合条件的内容"）', any === false && matched.size === 0);

    // 命中一个深层任务：它自己 + 所有祖先都要在集合里
    world.calls.length = 0;
    world.state.filterMatchedIds = new Set(['w7d3i25']);
    matched.clear();
    const anyDeep = world.api.collectVisibleNodeIds(tree, matched);
    check('筛选：命中一个任务时，集合 = 它自己 + 祖先链（3 个）',
        anyDeep === true && matched.size === 3 && matched.has('w7d3i25') && matched.has('w7d3') && matched.has('w7'),
        [...matched].join(','));
    const deepVisits = world.calls.filter(call => call[0] === 'nodeMatchesOwnFilter').length;
    // 后代已命中的祖先不必再判断自己（childMatched || ... 短路），所以比节点数少 2 个（w7 / w7d3）
    check('筛选：命中一个任务时总判断次数 ≤ 节点数（祖先短路，不再重复进子树）',
        deepVisits === totalNodes - 2, `${deepVisits} vs ${totalNodes - 2}`);

    // 旧实现（顶层 filter + 每层 children.filter）的调用次数，用同一棵树复算
    const ownMatch = id => id === 'w7d3i25';
    const oldHasMatch = node => (ownMatch(String(node.id)) || (node.children || []).some(oldHasMatch));
    let oldVisits = 0;
    const oldOwn = node => { oldVisits += 1; return ownMatch(String(node.id)); };
    const oldHas = node => (oldOwn(node) || (node.children || []).some(oldHas));
    tree.filter(oldHas).forEach(wk => {
        (wk.children || []).filter(oldHas).forEach(dy => { (dy.children || []).filter(oldHas); });
    });
    check('筛选：旧写法在同一棵树上要走更多次（重复进子树）',
        oldVisits > visits, `旧 ${oldVisits} vs 新 ${visits}`);

    // 真正的坏情况：每个单元只有**最后一个**任务命中（匹配稀疏且靠后）。
    // 这时容器自身不命中，旧写法每层都要把整棵子树走完（`.some` 也要走到最后一个孩子），
    // 顶层 1 遍 + 每个容器的 children 再各走一遍 → 约 3N。
    const sparseMatches = new Set();
    tree.forEach(wk => (wk.children || []).forEach(dy => {
        const items = dy.children || [];
        sparseMatches.add(String(items[items.length - 1].id));
    }));
    world.state.filterMatchedIds = sparseMatches;
    world.calls.length = 0;
    const worstMatched = new Set();
    world.api.collectVisibleNodeIds(tree, worstMatched);
    const worstVisits = world.calls.filter(call => call[0] === 'nodeMatchesOwnFilter').length;
    let worstOldVisits = 0;
    const oldOwn2 = node => { worstOldVisits += 1; return sparseMatches.has(String(node.id)); };
    const oldHas2 = node => (oldOwn2(node) || (node.children || []).some(oldHas2));
    tree.filter(oldHas2).forEach(wk => {
        (wk.children || []).filter(oldHas2).forEach(dy => { (dy.children || []).filter(oldHas2); });
    });
    check('筛选：稀疏深匹配时新写法只判断任务自己（祖先短路）',
        worstVisits === 10000, `${worstVisits}`);
    check('筛选：同一情况下旧写法要走两倍以上（N×深度）',
        worstOldVisits > worstVisits * 2, `旧 ${worstOldVisits} vs 新 ${worstVisits}`);
}

const failed = results.filter(result => !result).length;
console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
process.exit(failed ? 1 : 0);
