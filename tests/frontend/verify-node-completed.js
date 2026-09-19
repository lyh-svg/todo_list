// B2 验证：setNodeCompleted 的判空必须在任何解引用之前。
//
// 旧代码先读 node.completed、写 node.completed / node.completedAt，最后才 `if (!node || ...)`：
// 判空永远来不及（node 为 null 时上面已经 TypeError），是误导维护者的死代码。
//
// 同时钉住一件容易被"顺手改坏"的事：容器节点（周/单元）**仍然**要在函数里被写上完成标记 ——
// 分组复选框靠它，空单元也靠它显示已完成。所以只把判空提前，不能把整条 type 检查一起提前。
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

function buildWorld() {
    const calls = { spawned: [], toasts: [], dirty: [] };
    const deps = {
        calls,
        owningProjectOfNode: () => ({ id: 'p1', assessmentEnabled: false, reviewEnabled: false }),
        spawnNextOccurrence: (project, node) => {
            calls.spawned.push(node.id);
            return { dueDate: '2026-10-01' };
        },
        showToast: message => calls.toasts.push(String(message)),
        projectAutoReview: project => Boolean(project && project.reviewEnabled),
        addDaysToIso: (base, days) => base,
        todayStr: () => '2026-09-19',
        markProjectDirty: project => calls.dirty.push(project && project.id),
    };
    const factory = new Function('deps', `
        const { calls, owningProjectOfNode, spawnNextOccurrence, showToast, projectAutoReview,
                addDaysToIso, todayStr, markProjectDirty } = deps;
        ${extract('setNodeCompleted')}
        return { setNodeCompleted };
    `);
    return { api: factory(deps), calls };
}

const fnSource = extract('setNodeCompleted');

// ---------- 静态：判空必须是第一句，且早于任何 node.X ----------
check('静态：函数体第一句就是判空（允许前面只有注释）',
    /function setNodeCompleted\(node, completed\) \{\s*\r?\n(?:\s*\/\/[^\n]*\r?\n)*\s*if \(!node\)/.test(src));
// 分析前先去掉行注释：注释里提到 "node.X" 不算解引用
const bodyAfterSignature = fnSource.slice(fnSource.indexOf('{') + 1).replace(/\/\/[^\n]*/g, '');
const firstNodeUse = bodyAfterSignature.indexOf('node.');
const guardIndex = bodyAfterSignature.indexOf('if (!node)');
check('静态：判空出现在第一次解引用 node 之前',
    guardIndex >= 0 && firstNodeUse > guardIndex,
    `guard@${guardIndex} firstUse@${firstNodeUse}`);
check('静态：仍然单独保留容器节点的早退（不能把类型检查一起提前）',
    /if \(node\.type !== 'item'\) return \{ spawned: null, project: null \};/.test(fnSource));

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
        result && result.spawned === null && result.project === null, JSON.stringify(result));

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
    check('行为：没有周期规则时不生成下一次', result.spawned === null && world.calls.spawned.length === 0);
    check('行为：标脏了所属项目', world.calls.dirty.includes('p1'));

    world.api.setNodeCompleted(item, false);
    check('行为：取消完成会清掉完成时间', item.completed === false && item.completedAt === null);
}

// ---------- 行为：周期任务只在 false→true 这一次生成 ----------
{
    const world = buildWorld();
    const repeat = { id: 'r1', type: 'item', text: '每日任务', completed: false, repeat: { freq: 'daily' } };
    const first = world.api.setNodeCompleted(repeat, true);
    check('行为：周期任务 false→true 生成下一次并提示',
        first.spawned && world.calls.spawned.length === 1 && world.calls.toasts.length === 1,
        JSON.stringify(world.calls.spawned));
    world.api.setNodeCompleted(repeat, true);
    check('行为：重复标完成不再生成（防止指数级克隆）', world.calls.spawned.length === 1);
}

// ---------- 行为：容器节点仍然要写完成标记（分组复选框依赖它） ----------
{
    const world = buildWorld();
    const week = { id: 'w1', type: 'week', text: '第1周', completed: false };
    const result = world.api.setNodeCompleted(week, true);
    check('行为：容器也会被写上 completed / completedAt',
        week.completed === true && typeof week.completedAt === 'string',
        JSON.stringify(week));
    check('行为：容器不生成周期任务、也不标脏项目',
        result.spawned === null && result.project === null && world.calls.dirty.length === 0);
}

// ---------- 行为：取消完成会清掉复习安排 ----------
{
    const world = buildWorld();
    const task = { id: 'i2', type: 'item', text: '任务', completed: true,
                   review: { due: '2026-09-20', learning: false, log: [] } };
    world.api.setNodeCompleted(task, false);
    check('行为：取消完成会删除 review', task.completed === false && task.review === undefined);
}

// ---------- 行为：项目开了自动复习时，完成任务排明天 ----------
{
    const world = buildWorld();
    const project = { id: 'p1', reviewEnabled: true };
    const factory = new Function('deps', `
        const { calls, owningProjectOfNode, spawnNextOccurrence, showToast, projectAutoReview,
                addDaysToIso, todayStr, markProjectDirty } = deps;
        ${extract('setNodeCompleted')}
        return { setNodeCompleted };
    `);
    const api = factory({
        calls: { spawned: [], toasts: [], dirty: [] },
        owningProjectOfNode: () => project,
        spawnNextOccurrence: () => null,
        showToast: () => {},
        projectAutoReview: () => true,
        addDaysToIso: (base, days) => `${base}+${days}`,
        todayStr: () => '2026-09-19',
        markProjectDirty: () => {},
    });
    const task = { id: 'i3', type: 'item', text: '任务', completed: false, optional: false };
    api.setNodeCompleted(task, true);
    check('行为：自动复习开启时完成任务会排到明天',
        task.review && task.review.due === '2026-09-19+1' && task.review.learning === false,
        JSON.stringify(task.review));
    void world;
}

const failed = results.filter(result => !result).length;
console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
process.exit(failed ? 1 : 0);
