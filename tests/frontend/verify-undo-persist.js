// B11 验证：撤销栈持久化不再每步整栈 stringify，且写入量真的被 MAX_UNDO_BYTES 约束。
//
// 旧实现（每次 pushUndoStep / 撤销 / 重做都同步走一遍）：
//     const payload = JSON.stringify({ undo: undoStack, redo: redoStack });
//     if (payload.length > MAX_UNDO_BYTES) localStorage.setItem(..., JSON.stringify(最近 3 步));
//     else localStorage.setItem(..., payload);
// 实测（node，同一份数据结构）：300 节点 × 2000 字草稿的批量步骤、栈里 3 步约 15MB 时，
// 整栈 stringify 82ms，超限后再 stringify 一遍共 153ms —— 全在交互主线程上。
// 更糟的是"最近 3 步"挡不住单步超大：还是 15MB 写进 localStorage，被配额直接拒绝，
// 异常被 catch 掉，撤销历史从此静默不再落盘。
//
// 这里用可计数的 JSON.stringify / localStorage 桩，从 js/app.js 抽真实函数断言：
// ① 写入的负载永不超过 MAX_UNDO_BYTES（单步就超限时宁可不写这一步）；
// ② 每步大小只算一次（第二次持久化不再重新序列化步骤本身）；
// ③ 同一轮的多次变更合并成一次写入；
// ④ 正常小栈照旧完整往返，pagehide 仍有兜底 flush。
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

const realStringify = JSON.stringify;

function buildWorld() {
    const stats = { stringifyCalls: 0, stringifyChars: 0, writes: [], idleCallbacks: [] };
    const json = {
        stringify(value) {
            stats.stringifyCalls += 1;
            const out = realStringify(value);
            stats.stringifyChars += out.length;
            return out;
        },
    };
    const localStorage = { setItem(key, value) { stats.writes.push({ key, value }); } };
    const window = {
        requestIdleCallback(callback) { stats.idleCallbacks.push(callback); return stats.idleCallbacks.length; },
        setTimeout(callback) { stats.idleCallbacks.push(callback); return stats.idleCallbacks.length; },
    };
    const deps = { JSON: json, localStorage, window, console: { warn() {} } };
    const prelude = `
        const { JSON, localStorage, window } = deps;
        const UNDO_STORAGE_KEY = 'todo_list_undo_v1';
        const MAX_UNDO_BYTES = 200 * 1024;
        const undoStepBytes = new WeakMap();
        let undoPersistScheduled = false;
        let undoStack = [];
        let redoStack = [];
    `;
    const body = `
        ${extract('undoStepSize')}
        ${extract('recentUndoSteps')}
        ${extract('persistUndoStack')}
        ${extract('scheduleUndoPersist')}
        return {
            persistUndoStack, scheduleUndoPersist, recentUndoSteps,
            setUp(undo, redo) { undoStack = undo; redoStack = redo; },
            stacks() { return { undo: undoStack, redo: redoStack }; },
            isScheduled() { return undoPersistScheduled; },
        };
    `;
    return { api: new Function('deps', `${prelude}\n${body}`)(deps), stats };
}

function step(label, chars) {
    return { label, ops: [{ kind: 'node-fields', projectId: 'p1', payload: 'x'.repeat(chars) }] };
}

const MAX = 200 * 1024;

// ---------- ① 超限时写入被真正约束住 ----------
{
    const world = buildWorld();
    const huge = step('超大批量', 400 * 1024);
    world.api.setUp([huge], []);
    world.api.persistUndoStack();
    const written = world.stats.writes[world.stats.writes.length - 1].value;
    check('单步超过 MAX_UNDO_BYTES 时不写这一步（负载不再超限）',
        written.length <= MAX, `${(written.length / 1024).toFixed(0)}KB`);
    const parsed = JSON.parse(written);
    check('超限的单步被整体丢弃，不留半截历史',
        parsed.undo.length === 0 && parsed.redo.length === 0, JSON.stringify(parsed.undo.length));
}

// ---------- ② 每步大小只算一次 ----------
{
    const world = buildWorld();
    const steps = [step('批量一', 40 * 1024), step('批量二', 40 * 1024)];
    const small = step('小步', 1000);
    world.api.setUp(steps.concat([small]), []);
    world.api.persistUndoStack();
    const firstChars = world.stats.stringifyChars;
    const firstCalls = world.stats.stringifyCalls;
    world.api.persistUndoStack();      // 同样的栈再存一次
    const secondChars = world.stats.stringifyChars - firstChars;
    const secondCalls = world.stats.stringifyCalls - firstCalls;
    check('第一次持久化之后，步骤本身不再被重复序列化（第二次只序列化要写的那份负载）',
        secondCalls === 1 && secondChars < firstChars * 0.6,
        `第一次 ${firstChars} 字符 / ${firstCalls} 次，第二次 ${secondChars} 字符 / ${secondCalls} 次`);
}

// ---------- ③ 同一轮多次变更合并成一次写入 ----------
{
    const world = buildWorld();
    world.api.setUp([step('一', 100)], []);
    world.api.scheduleUndoPersist();
    world.api.scheduleUndoPersist();
    world.api.scheduleUndoPersist();
    check('合并前不写、只排一个回调',
        world.stats.writes.length === 0 && world.stats.idleCallbacks.length === 1,
        JSON.stringify({ writes: world.stats.writes.length, queued: world.stats.idleCallbacks.length }));
    world.stats.idleCallbacks.forEach(callback => callback());
    check('回调执行后只落盘一次', world.stats.writes.length === 1,
        JSON.stringify(world.stats.writes.length));
    check('落盘后允许再次排队（标志位复位）', world.api.isScheduled() === false);
}

// ---------- ④ 正常小栈照旧往返 ----------
{
    const world = buildWorld();
    const undo = [step('删除任务', 200), step('移动任务', 300)];
    const redo = [step('重做一步', 150)];
    world.api.setUp(undo, redo);
    world.api.persistUndoStack();
    const parsed = JSON.parse(world.stats.writes[0].value);
    check('正常小栈完整落盘（undo/redo 都在，顺序不变）',
        parsed.undo.length === 2 && parsed.redo.length === 1
        && parsed.undo[0].label === '删除任务' && parsed.undo[1].label === '移动任务'
        && parsed.redo[0].label === '重做一步',
        JSON.stringify({ undo: parsed.undo.map(s => s.label), redo: parsed.redo.map(s => s.label) }));
}

// ---------- ⑤ 关页兜底 ----------
check('pagehide 里仍有排队的撤销历史 flush',
    src.includes('if (undoPersistScheduled) persistUndoStack();'),
    '找不到 pagehide flush');

const failed = results.filter(ok => !ok).length;
if (failed) {
    console.error(`${failed} 项断言失败`);
    process.exit(1);
}
console.log('撤销栈持久化：全部通过');
