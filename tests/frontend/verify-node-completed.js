// B2 + Q13 验证：setNodeCompleted 的判空必须在任何解引用之前；周期任务的"下一次"
// 由**服务端**生成，前端只负责把响应里的副本拼回本地树。
//
// 历史：旧代码先读 node.completed、写 node.completed / node.completedAt，最后才
// `if (!node || ...)`（判空永远来不及，是误导维护者的死代码）；同时前端还自己克隆一份
// "下一次"（spawnNextOccurrence），与服务端批量完成里的那份规则各写一遍，容易走偏。
// 现在统一到服务端（Q13），这里同时钉住两件事：
//   1. 判空仍在第一句，容器节点仍然要写完成标记（分组复选框依赖它）；
//   2. 前端不再克隆，而是把保存响应里的 spawned 拼进本地树。
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

function buildWorld(projectTree) {
    const calls = { toasts: [], dirty: [], rendered: 0 };
    const project = { id: 'p1', assessmentEnabled: false, reviewEnabled: false,
                      tree: projectTree || [] };
    const deps = {
        calls,
        project,
        owningProjectOfNode: () => project,
        showToast: message => calls.toasts.push(String(message)),
        projectAutoReview: value => Boolean(value && value.reviewEnabled),
        addDaysToIso: (base, days) => base + '+' + days,
        todayStr: () => '2026-09-19',
        markProjectDirty: value => calls.dirty.push(value && value.id),
        currentProjectId: 'p1',
        renderDetail: () => { calls.rendered += 1; },
        document: { querySelector: () => null },
        findParentList: (nodes, targetId) => {
            for (const node of nodes || []) {
                if (String(node.id) === String(targetId)) return node.children || [];
                const found = deps.findParentList(node.children || [], targetId);
                if (found) return found;
            }
            return null;
        },
    };
    const factory = new Function('deps', `
        const { owningProjectOfNode, showToast, projectAutoReview, addDaysToIso, todayStr,
                markProjectDirty, currentProjectId, findParentList, renderDetail, document } = deps;
        const currentProjectIdValue = currentProjectId;
        ${extract('setNodeCompleted')}
        ${extract('applySpawnedOccurrences')}
        return { setNodeCompleted, applySpawnedOccurrences, project: deps.project };
    `);
    return { api: factory(deps), calls, project };
}

const fnSource = extract('setNodeCompleted');

// ---------- 静态：判空必须是第一句，且早于任何 node.X ----------
check('静态：函数体第一句就是判空（允许前面只有注释）',
    /function setNodeCompleted\(node, completed\) \{\s*\r?\n(?:\s*\/\/[^\n]*\r?\n)*\s*if \(!node\)/.test(src));
const bodyAfterSignature = fnSource.slice(fnSource.indexOf('{') + 1).replace(/\/\/[^\n]*/g, '');
const firstNodeUse = bodyAfterSignature.indexOf('node.');
const guardIndex = bodyAfterSignature.indexOf('if (!node)');
check('静态：判空出现在第一次解引用 node 之前',
    guardIndex >= 0 && firstNodeUse > guardIndex,
    `guard@${guardIndex} firstUse@${firstNodeUse}`);
check('静态：仍然单独保留容器节点的早退（不能把类型检查一起提前）',
    /if \(node\.type !== 'item'\) return \{ project: null \};/.test(fnSource));
check('静态：前端不再自己克隆"下一次"',
    !src.includes('function spawnNextOccurrence(') && !fnSrcContains('spawnNextOccurrence')
    && !src.includes("op: 'append'"));
function fnSrcContains(needle) {
    return fnSource.includes(needle);
}
check('静态：两条保存路径都会把响应里的 spawned 拼回本地树',
    (src.match(/applySpawnedOccurrences\(/g) || []).length >= 3
    && /applySpawnedOccurrences\(project, payload\.spawned\)[\s\S]{0,200}rememberProjectBaseline/.test(src)
    && /applySpawnedOccurrences\(project, payload\.spawned\)[\s\S]{0,300}rememberSavedProjectState/.test(src));

// ---------- 行为：空值不再抛 ----------
{
    const world = buildWorld();
    let threw = null;
    let result = null;
    try {
        result = world.api.setNodeCompleted(null, true);
    } catch (error) {
        threw = error;
    }
    check('行为：setNodeCompleted(null) 不抛异常', threw === null, threw && threw.message);
    check('行为：setNodeCompleted(null) 返回空结果',
        result && result.project === null, JSON.stringify(result));

    const world2 = buildWorld();
    let threw2 = null;
    try {
        world2.api.setNodeCompleted(undefined, true);
    } catch (error) {
        threw2 = error;
    }
    check('行为：setNodeCompleted(undefined) 不抛异常', threw2 === null, threw2 && threw2.message);
}

// ---------- 行为：任务节点照旧 ----------
{
    const world = buildWorld();
    const item = { id: 'i1', type: 'item', text: '任务', completed: false, optional: false };
    const result = world.api.setNodeCompleted(item, true);
    check('行为：任务被标完成并写完成时间',
        item.completed === true && typeof item.completedAt === 'string' && item.completedAt.length > 0);
    check('行为：前端不再自己生成下一次（等服务端响应）',
        result && result.project === world.project && world.calls.toasts.length === 0);
    check('行为：标脏了所属项目', world.calls.dirty.includes('p1'));

    world.api.setNodeCompleted(item, false);
    check('行为：取消完成会清掉完成时间', item.completed === false && item.completedAt === null);
}

// ---------- 行为：拼接服务端回传的副本 ----------
{
    const parent = { id: 'd1', type: 'day', text: '单元1', children: [] };
    const world = buildWorld([parent, { id: 'w1', type: 'week', text: '第1周', children: [] }]);
    const spawned = [
        { parentId: 'd1', node: { id: 'new-1', type: 'item', text: '下一次', dueDate: '2026-09-20' } },
        { parentId: null, node: { id: 'new-2', type: 'item', text: '根层下一次', dueDate: '2026-09-21' } },
    ];
    const applied = world.api.applySpawnedOccurrences(world.project, spawned);
    check('行为：副本按 parentId 拼到对应父节点下', applied === 2
        && parent.children.length === 1 && parent.children[0].id === 'new-1'
        && world.project.tree.length === 3 && world.project.tree[2].id === 'new-2',
        JSON.stringify(world.project.tree.map(node => node.id)));
    check('行为：拼进去时给出提示（含下一次日期）',
        world.calls.toasts.length === 2 && world.calls.toasts[0].includes('2026-09-20'),
        JSON.stringify(world.calls.toasts));
    const again = world.api.applySpawnedOccurrences(world.project, spawned);
    check('行为：同一条副本重复回传不会拼两次', again === 0
        && parent.children.length === 1 && world.project.tree.length === 3);
    check('行为：拼完会重绘当前项目的详情页', world.calls.rendered >= 1);
}

// ---------- 行为：容器节点仍然要写完成标记（分组复选框依赖它） ----------
{
    const world = buildWorld();
    const week = { id: 'w1', type: 'week', text: '第1周', completed: false };
    const result = world.api.setNodeCompleted(week, true);
    check('行为：容器也会被写上 completed / completedAt',
        week.completed === true && typeof week.completedAt === 'string',
        JSON.stringify(week));
    check('行为：容器不标脏项目、也不返回项目',
        result.project === null && world.calls.dirty.length === 0);
}

// ---------- 行为：取消完成会清掉复习安排 ----------
{
    const world = buildWorld();
    const task = { id: 'i2', type: 'item', text: '任务', completed: true,
                   review: { due: '2026-09-20', learning: false, log: [] } };
    world.api.setNodeCompleted(task, false);
    check('行为：取消完成会删除 review', task.completed === false && task.review === undefined);
}

// ---------- 行为：完成时按项目开关排复习 ----------
{
    const world = buildWorld();
    world.project.reviewEnabled = true;
    const task = { id: 'i3', type: 'item', text: '任务', completed: false, optional: false };
    world.api.setNodeCompleted(task, true);
    check('行为：自动复习开启时完成任务会排到明天',
        task.review && task.review.due === '2026-09-19+1' && task.review.learning === false,
        JSON.stringify(task.review));
}

const failed = results.filter(result => !result).length;
console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
process.exit(failed ? 1 : 0);
