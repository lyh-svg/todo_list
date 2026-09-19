// B12 验证：closeUtilityModal 的备忘录兜底保存只认 pendingMemoId。
//
// 弹窗关闭时如果还有防抖保存没落地，旧代码用
//     memoState.memos.find(m => m.id === pendingMemoId) || currentMemo()
// 兜底。pendingMemoId 查不到时（这条备忘录被删/被换掉）就会退到"当前选中的那条"，
// 而此刻用户可能刚好切到了另一条备忘录 —— 于是 flush 的目标变成了它。
// persistMemo 内部还会按 snapshot.id 再查一次，所以内容不会串条，但目标选择逻辑是错的：
// 该丢弃的时候不该去写别的备忘录。
//
// 这里抽真实的 closeUtilityModal 跑，断言：
// ① pendingMemoId 指向存在的备忘录 → 保存它；
// ② pendingMemoId 已查不到 → 一次都不保存（绝不 fallback 到 currentMemo()）；
// ③ 没有 pending 时不动 persistMemo；④ 关窗本身照常完成。
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
    const world = {
        saved: [], cleared: 0, modals: [],
        memoState: { saveTimer: 7, pendingMemoId: null, memos: [] },
        persistMemo(memo) { world.saved.push(memo); return Promise.resolve(memo); },
    };
    world.currentMemo = () => world.memoState.memos.find(m => m.id === world.memoState.selectedId) || null;
    const utilityModal = { hidden: false };
    const utilityBody = { innerHTML: 'x' };
    const document = { body: { classList: { remove(name) { world.modals.push(name); } } } };
    const deps = { memoState: world.memoState, currentMemo: world.currentMemo,
                   persistMemo: world.persistMemo, utilityModal, utilityBody, document,
                   clearTimeout: () => { world.cleared += 1; } };
    const prelude = `
        const { memoState, currentMemo, persistMemo, utilityModal, utilityBody, document, clearTimeout } = deps;
    `;
    const factory = new Function('deps', `${prelude}\n${extract('closeUtilityModal')}\nreturn closeUtilityModal;`);
    world.close = factory(deps);
    world.utilityModal = utilityModal;
    world.utilityBody = utilityBody;
    return world;
}

// ① pendingMemoId 指向存在的备忘录：保存的是它（不是当前选中的那条）
{
    const world = buildWorld();
    world.memoState.memos = [{ id: 'm1', content: '草稿1' }, { id: 'm2', content: '草稿2' }];
    world.memoState.pendingMemoId = 'm1';
    world.memoState.selectedId = 'm2';          // 用户已经切到另一条
    world.close();
    check('pendingMemoId 存在时保存的是那条备忘录',
        world.saved.length === 1 && world.saved[0] && world.saved[0].id === 'm1',
        JSON.stringify(world.saved.map(m => m.id)));
}

// ② pendingMemoId 已查不到：丢弃，绝不 fallback 到 currentMemo()
{
    const world = buildWorld();
    world.memoState.memos = [{ id: 'm2', content: '草稿2' }];
    world.memoState.pendingMemoId = '已经被删掉的-m1';
    world.memoState.selectedId = 'm2';
    world.close();
    check('pendingMemoId 查不到时一次都不保存（不写别的备忘录）',
        world.saved.length === 0, JSON.stringify(world.saved.map(m => m.id)));
}

// ③ 没有 pending 保存：不动 persistMemo
{
    const world = buildWorld();
    world.memoState.saveTimer = null;
    world.memoState.memos = [{ id: 'm2', content: '草稿2' }];
    world.memoState.pendingMemoId = null;
    world.memoState.selectedId = 'm2';
    world.close();
    check('没有防抖保存时不动 persistMemo', world.saved.length === 0,
        JSON.stringify(world.saved.map(m => m.id)));
}

// ④ 关窗行为不变：清定时器、清空弹窗内容、移除 modal-open
{
    const world = buildWorld();
    world.memoState.memos = [{ id: 'm1', content: '草稿1' }];
    world.memoState.pendingMemoId = 'm1';
    world.memoState.selectedId = 'm1';
    world.close();
    check('关窗仍然清定时器 + 清空内容 + 移除 modal-open',
        world.cleared === 1 && world.memoState.saveTimer === null
        && world.memoState.pendingMemoId === null
        && world.utilityModal.hidden === true && world.utilityBody.innerHTML === ''
        && world.modals.includes('modal-open'),
        JSON.stringify({ cleared: world.cleared, hidden: world.utilityModal.hidden,
                         inner: world.utilityBody.innerHTML, modals: world.modals }));
}

const failed = results.filter(ok => !ok).length;
if (failed) {
    console.error(`${failed} 项断言失败`);
    process.exit(1);
}
console.log('关窗兜底保存：全部通过');
