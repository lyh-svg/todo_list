// P4 验证：一次勾选不该付两次"整棵项目树 stringify"。
//
// 做法和 dom-smoke / measure-scale 一致：从 js/app.js 抽出**真实函数**，配最小桩跑，
// 并且把 JSON.stringify 换成会计数的版本——断言的是"到底序列化了几次、序列化了谁"，
// 不是耗时（耗时随机器波动）。
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

const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}

function buildTree(total, prefix) {
    const weeks = 20;
    const perDay = Math.max(1, Math.floor(total / (weeks * 10)));
    let index = 0;
    const tree = [];
    for (let w = 1; w <= weeks; w += 1) {
        const week = { id: `${prefix}w${w}`, type: 'week', text: `第${w}周`, completed: false,
                       expanded: false, createdAt: '2026-09-16', children: [] };
        for (let d = 1; d <= 10; d += 1) {
            const day = { id: `${prefix}w${w}d${d}`, type: 'day', text: `单元${d}`, completed: false,
                          expanded: false, createdAt: '2026-09-16', children: [] };
            for (let i = 0; i < perDay; i += 1) {
                index += 1;
                day.children.push({
                    id: `${prefix}i${index}`, type: 'item', text: `任务 ${index}：解释并举例`,
                    completed: false, completedAt: null, optional: false, assessmentRequired: false,
                    assessmentHistory: 0, assessment: null, createdAt: '2026-09-16', children: [],
                    priority: '', dueDate: '', estimateMinutes: 0, tags: [], note: '', links: [],
                });
            }
            week.children.push(day);
        }
        tree.push(week);
    }
    return tree;
}

function makeProject(id, total) {
    return { id, name: '项目 ' + id, description: '', createdAt: '2026-09-16',
             assessmentEnabled: false, reviewEnabled: true, archived: false, tree: buildTree(total, id) };
}

const PRELUDE = `
    const SAVE_DEBOUNCE_MS = 250;
    let projects = [];
    let dirtyProjectIds = new Set();
    let projectStatsCache = new Map();
    let nodeStatsCache = new Map();
    let savedProjectJsonById = new Map();
    let savedProjectSeqById = new Map();
    let projectMutationSeqById = new Map();
    let saveQueue = Promise.resolve();
    let saveTimer = null;
    let saveWaiters = [];
    let inFlightSaves = 0;
    let inFlightPatches = 0;
    let saveConflict = false;
    const PROJECT_STATE_SKIP_KEYS = new Set(['expanded', '_revision', 'stats']);
    const written = [];
    function setTimeout() { return 1; }
    function clearTimeout() {}
    function armLeaveGuard() {}
    function disarmLeaveGuard() {}
    function setSaveStatus() {}
    function showToast() {}
    function beginProjectConflict() { return Promise.resolve(); }
    function writeStoredProject(project, expectedRevision) {
        written.push(String(project.id));
        return Promise.resolve({ revision: (Number(expectedRevision) || 0) + 1, summary: { stats: {} } });
    }
`;

const BUNDLE = [
    'serializeProject', 'skipViewState', 'projectStateJson',
    'projectMutationSeq', 'markProjectDirty',
    'rememberSavedProjectState', 'rememberProjectBaseline', 'forgetProjectBaseline', 'forgetAllProjectBaselines',
    'canUseNodePatch', 'savePending', 'saveProjects', 'flushProjectsSave',
];

function buildSandbox(loaded) {
    const json = { calls: 0, chars: 0 };
    const warnings = [];
    const realStringify = JSON.stringify;
    const counting = {
        stringify: (...args) => {
            json.calls += 1;
            const text = realStringify.apply(JSON, args);
            if (typeof text === 'string') json.chars += text.length;
            return text;
        },
        parse: JSON.parse,
    };
    // 抽出真实函数；某个函数不存在时退化成空桩，好让"改坏了"表现为断言失败而不是脚本崩溃
    const missing = [];
    const body = BUNDLE.map(name => {
        try {
            return extract(name);
        } catch (error) {
            missing.push(name);
            return `    function ${name}() {}`;
        }
    }).join('\n');
    const factory = new Function('JSON', 'console', PRELUDE + `
        ${body}
        return {
            written,
            setProjects: (value) => { projects = value; },
            setSaveTimer: (value) => { saveTimer = value; },
            canUseNodePatch, flushProjectsSave, saveProjects, savePending,
            markProjectDirty, rememberProjectBaseline, forgetProjectBaseline,
            dirtyIds: () => [...dirtyProjectIds],
            seqOf: (project) => projectMutationSeq(project),
            savedSeqOf: (id) => savedProjectSeqById.get(String(id)),
            baselineOf: (id) => savedProjectJsonById.get(String(id)),
        };`);
    const api = factory(counting, { warn: (message) => warnings.push(String(message)) });
    // 把 warn 收集到 sandbox 内（stubs.warn 在 prelude 里，这里补一条桥）
    api.setProjects(loaded);
    return { api, json, loaded, warnings, missing };
}

async function run() {
    const big = makeProject('big', 10000);
    const mid = makeProject('mid', 1000);
    const small = makeProject('small', 200);

    // ---------- ① canUseNodePatch 不再序列化整棵树 ----------
    let world = buildSandbox([big]);
    world.api.rememberProjectBaseline(big);              // 建基线（这一次允许序列化）
    world.json.calls = 0;
    world.json.chars = 0;
    let allowed = null;
    for (let i = 0; i < 5; i += 1) allowed = world.api.canUseNodePatch(big);
    check('行为：未改动时允许节点级 patch', allowed === true);
    check('行为：patch 判据 5 次调用 0 次整树 stringify',
        world.json.calls === 0, `stringify ${world.json.calls} 次 / ${world.json.chars} 字符`);

    world.api.markProjectDirty(big);
    check('行为：改动计数自增后不再允许 patch',
        world.api.canUseNodePatch(big) === false && world.api.seqOf(big) === 1);
    check('行为：改动后判据仍然不序列化', world.json.calls === 0, String(world.json.calls));

    // ---------- ② flush 只扫脏项目 ----------
    world = buildSandbox([big, mid, small]);
    [big, mid, small].forEach(project => world.api.rememberProjectBaseline(project));
    world.json.calls = 0;
    mid.tree[0].children[0].children[0].text = '改了标题';   // 真的改了内容
    world.api.markProjectDirty(mid);
    await world.api.flushProjectsSave();
    check('行为：只写被标脏的那个项目', world.api.written.join(',') === 'mid', world.api.written.join(','));
    check('行为：flush 只为脏项目算指纹（1 次），不再扫另外两个已加载项目',
        world.json.calls === 1, `stringify ${world.json.calls} 次`);
    check('行为：全量保存后 patch 资格恢复',
        world.api.canUseNodePatch(mid) === true
        && world.api.savedSeqOf('mid') === world.api.seqOf(mid));
    check('行为：保存后不再有脏项目', world.api.dirtyIds().length === 0);

    // ---------- ③ 内容回到基线 → 不写库，但恢复 patch 资格 ----------
    const revert = makeProject('revert', 300);
    world = buildSandbox([revert]);
    world.api.rememberProjectBaseline(revert);
    const restoredText = revert.tree[0].children[0].children[0].text;
    revert.tree[0].children[0].children[0].text = '改了一下';
    world.api.markProjectDirty(revert);
    revert.tree[0].children[0].children[0].text = restoredText;   // 又改回去
    world.json.calls = 0;
    await world.api.flushProjectsSave();
    check('行为：内容回到基线时不做无谓的整树写入', world.api.written.length === 0);
    check('行为：这种情况只序列化脏项目自己一次', world.json.calls === 1, String(world.json.calls));
    check('行为：同步计数后 patch 资格恢复（否则以后每次都要全量保存）',
        world.api.canUseNodePatch(revert) === true);

    // ---------- ④ 漏标 dirty 时的兜底（不丢数据） ----------
    world = buildSandbox([big, mid, small]);
    [big, mid, small].forEach(project => world.api.rememberProjectBaseline(project));
    mid.tree[0].children[0].children[0].completed = true;   // 直接改内容，故意不标脏
    world.json.calls = 0;
    await world.api.flushProjectsSave();
    check('行为：没有任何项目标脏时仍会全量差集兜底，改动不会丢',
        world.api.written.join(',') === 'mid', world.api.written.join(','));
    check('行为：兜底路径会打印"可能漏标 markProjectDirty"的警告',
        world.warnings.some(text => text.includes('漏了 markProjectDirty')), JSON.stringify(world.warnings));

    // ---------- 源码接线 ----------
    check('源码：canUseNodePatch 里不再出现整树序列化',
        !/function canUseNodePatch[\s\S]{0,1200}?projectStateJson/.test(src));
    check('源码：改动计数在 markProjectDirty 里自增',
        /function markProjectDirty\(project\) \{[\s\S]{0,500}?projectMutationSeqById\.set\(/.test(src));
    check('源码：JSON 基准只在成对助手里写/删（不会漏同步计数）',
        (src.match(/savedProjectJsonById\.set\(/g) || []).length === 1
        && (src.match(/savedProjectJsonById\.delete\(/g) || []).length === 1
        && (src.match(/savedProjectSeqById\.set\(/g) || []).length >= 1);
    check('源码：flush 的候选集只取脏项目',
        /let candidates = loaded\.filter\(project => dirtyProjectIds\.has\(/.test(src));
    const jsonClears = (src.match(/savedProjectJsonById\.clear\(\)/g) || []).length;
    const helperCalls = (src.match(/forgetAllProjectBaselines\(\);/g) || []).length;
    check('源码：清空基线与计数成对（clear 只在助手内，调用点都走助手）',
        jsonClears === 1 && helperCalls >= 4, `clear=${jsonClears} helper=${helperCalls}`);
}

run().then(() => {
    const failed = results.filter(r => !r).length;
    console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
    process.exit(failed ? 1 : 0);
}).catch(error => {
    console.error(error);
    process.exit(1);
});
