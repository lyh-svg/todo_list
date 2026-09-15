// R3（① 冲突 + ⑥ 离开页面 + ⑦ 日期）验证：纯函数真跑 + 接线源码断言。
const fs = require('fs');
const ROOT = require('path').resolve(__dirname, '..', '..');
const src = fs.readFileSync(ROOT + '/js/app.js', 'utf8');
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
const api = new Function(
    'cloneData',
    `${extract('walkTreeEntriesForDiff')}
     ${extract('nodeFieldDifferences')}
     ${extract('diffProject')}
     ${extract('mergeProjects')}
     return { diffProject, mergeProjects };`
)(value => JSON.parse(JSON.stringify(value)));

const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}
const item = (id, text, completed) => ({ id, type: 'item', text, completed, completedAt: completed ? '2026-09-15T10:00:00' : null, optional: false, assessmentRequired: false, assessmentHistory: 0, assessment: null, createdAt: '2026-09-15', children: [] });
function project(name, items) {
    return { id: 'p1', name, description: 'd', createdAt: '2026-09-15', assessmentEnabled: true, reviewEnabled: false, tree: [{ id: 'w1', type: 'week', text: '第1周', expanded: true, children: [{ id: 'd1', type: 'day', text: '单元1', expanded: true, children: items }] }] };
}
const local = project('本地名', [item('i1', '任务1', true), item('i2', '本地新增', false)]);
const remote = project('服务端名', [item('i1', '任务1', false), item('i3', '服务端新增', false)]);

// —— ① 差异 ——
const diff = api.diffProject(local, remote);
check('① 报出项目名差异', diff.projectFields.some(f => f.field === '项目名' && f.local === '本地名' && f.remote === '服务端名'), JSON.stringify(diff.projectFields));
check('① 报出被改任务及其字段', diff.changed.length === 1 && diff.changed[0].id === 'i1' && diff.changed[0].fields.some(f => f.field === '完成'), JSON.stringify(diff.changed));
check('① 报出"仅本地有"的节点（带路径）', diff.onlyLocal.length === 1 && diff.onlyLocal[0].path.includes('单元1') && diff.onlyLocal[0].path.includes('本地新增'), JSON.stringify(diff.onlyLocal));
check('① 报出"仅服务端有"的节点', diff.onlyRemote.length === 1 && diff.onlyRemote[0].path.includes('服务端新增'), JSON.stringify(diff.onlyRemote));
const same = api.diffProject(local, JSON.parse(JSON.stringify(local)));
check('① 完全一致时无差异', same.projectFields.length === 0 && same.changed.length === 0 && same.onlyLocal.length === 0 && same.onlyRemote.length === 0);

// —— ① 合并 ——
const merged1 = api.mergeProjects(local, remote, { project: 'local', nodes: { i1: 'remote' }, keepLocalOnly: new Set(['i2']), keepRemoteOnly: new Set(['i3']) });
const items1 = merged1.tree[0].children[0].children;
check('① 合并：项目名取本地', merged1.name === '本地名', merged1.name);
check('① 合并：i1 按选择取服务端', items1.find(n => n.id === 'i1').completed === false);
check('① 合并：本地独有节点被保留', Boolean(items1.find(n => n.id === 'i2')));
check('① 合并：服务端独有节点被采纳', Boolean(items1.find(n => n.id === 'i3')));
check('① 合并：不产生 _revision/stats 字段', merged1._revision === undefined && merged1.stats === undefined);
const merged2 = api.mergeProjects(local, remote, { project: 'remote', nodes: {}, keepLocalOnly: new Set(), keepRemoteOnly: new Set() });
check('① 合并：project=remote 时用服务端名且丢弃两边独有节点',
    merged2.name === '服务端名' && merged2.tree[0].children[0].children.length === 1
    && merged2.tree[0].children[0].children[0].id === 'i1', JSON.stringify(merged2.tree[0].children[0].children.map(n => n.id)));
const merged3 = api.mergeProjects(local, remote, { project: 'remote', nodes: { i1: 'local' }, keepLocalOnly: new Set(['i2']), keepRemoteOnly: new Set() });
const items3 = merged3.tree[0].children[0].children;
check('① 合并：project=remote 但 i1 选本地 → 用本地值', items3.find(n => n.id === 'i1').completed === true);

// —— 接线断言 ——
check('① 409 不再自动覆盖服务端（旧的 fresh + 重写已移除）',
    !/const fresh = await readStoredProject\(projectId\);[\s\S]{0,160}writeStoredProject\(project, Number\(fresh\.revision\)\)/.test(src));
check('① 409 走 beginProjectConflict', src.includes('await beginProjectConflict(project, current);'));
check('① 冲突时停止写入（saveConflict 置位）', /async function beginProjectConflict[\s\S]{0,200}saveConflict = true;/.test(src));
check('① 冲突面板有三个出口', src.includes("keepLocal.textContent = '保留本地并覆盖服务端'")
    && src.includes("keepRemote.textContent = '保留服务端并丢弃本地'")
    && src.includes("merge.textContent = '手动合并…'"));
check('① 冲突面板可再次打开（toast 动作）', src.includes("showToast('两个页面改了同一项目，已停止写入', { label: '解决冲突', onClick: () => openConflictPanel() })"));
check('① 采用服务端版本会替换内存对象并重渲染', /function resolveConflictTakeRemote[\s\S]{0,600}projects\[index\] = remote;[\s\S]{0,400}renderDetail\(\);/.test(src));
check('① 冲突未解决时保存会被挡住', /if \(saveConflict\) \{[\s\S]{0,300}conflictError[\s\S]{0,200}throw conflictError;/.test(src));
check('① 冲突挂起时不再误报"SQLite 保存失败"', src.includes('if (error && error.conflict)'));
check('① 冲突挂起时离开守卫仍然生效', /savePending\(\)[\s\S]{0,200}saveConflict[\s\S]{0,200}dirtyProjectIds\.size > 0/.test(src));

check('⑥ settleSaves 同时等待防抖与在飞请求',
    /async function settleSaves\(\)[\s\S]{0,220}await saveQueue\.catch/.test(src));
check('⑥ 四处离开路径都用 settleSaves', (src.match(/await settleSaves\(\);/g) || []).length === 4, String((src.match(/await settleSaves\(\);/g) || []).length));
check('⑥ 小项目写入带 keepalive', src.includes('keepalive: body.length <= 60000'));
check('⑥ 有未完成保存时才拦关闭', src.includes('function savePending()') && src.includes("window.addEventListener('beforeunload', warnBeforeUnload)"));
check('⑥ 保存完成后解除守卫', src.includes('if (!savePending()) disarmLeaveGuard();'));

check('⑦ 读列表带浏览器本地日期', src.includes('`/api/projects?today=${encodeURIComponent(todayStr())}`'));
check('⑦ 时区不一致会提示一次', src.includes('stored.serverToday !== todayStr() && !timezoneWarned'));

const failed = results.filter(r => !r).length;
console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
process.exit(failed ? 1 : 0);
