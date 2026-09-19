// 批次 3 验证：筛选语义（纯函数真跑）+ 归档/视图/批量编辑接线。
const fs = require('fs');
const ROOT = require('path').resolve(__dirname, '..', '..');
const src = fs.readFileSync(ROOT + '/js/app.js', 'utf8');
const html = fs.readFileSync(ROOT + '/index.html', 'utf8');
const css = fs.readFileSync(ROOT + '/css/style.css', 'utf8');
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
const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}

// —— 元数据筛选语义（真跑）——
function metaMatcher(filters) {
    return new Function('nodeFilters', 'todayStr', 'daysBetween',
        `${extract('nodeMatchesMetaFilter')} return nodeMatchesMetaFilter;`
    )(filters, () => '2026-09-15', (from, to) => Math.round(
        (new Date(`${to}T00:00:00`) - new Date(`${from}T00:00:00`)) / 86400000));
}
const high = { priority: 'high', dueDate: '2026-09-15', tags: ['Python', '复习'] };
const overdueItem = { priority: '', dueDate: '2026-09-10', tags: ['Old'] };
const noMeta = {};
const in3Days = { priority: 'mid', dueDate: '2026-09-18', tags: [] };
check('筛选：优先级精确匹配', metaMatcher({ priority: 'high', due: 'all', tag: '' })(high) === true);
check('筛选：优先级不匹配被排除', metaMatcher({ priority: 'low', due: 'all', tag: '' })(high) === false);
check('筛选：未设优先级（none）只留空值', metaMatcher({ priority: 'none', due: 'all', tag: '' })(noMeta) === true
    && metaMatcher({ priority: 'none', due: 'all', tag: '' })(high) === false);
check('筛选：标签包含匹配（大小写不敏感）', metaMatcher({ priority: 'all', due: 'all', tag: 'pyt' })(high) === true
    && metaMatcher({ priority: 'all', due: 'all', tag: 'c++' })(high) === false);
check('筛选：今天到期', metaMatcher({ priority: 'all', due: 'today', tag: '' })(high) === true
    && metaMatcher({ priority: 'all', due: 'today', tag: '' })(overdueItem) === false);
check('筛选：逾期', metaMatcher({ priority: 'all', due: 'overdue', tag: '' })(overdueItem) === true
    && metaMatcher({ priority: 'all', due: 'overdue', tag: '' })(high) === false);
check('筛选：未来 1-7 天（不含今天，不含逾期）', metaMatcher({ priority: 'all', due: 'week', tag: '' })(in3Days) === true
    && metaMatcher({ priority: 'all', due: 'week', tag: '' })(high) === false
    && metaMatcher({ priority: 'all', due: 'week', tag: '' })(overdueItem) === false);
check('筛选：7 天内到期（含今天）', metaMatcher({ priority: 'all', due: 'soon', tag: '' })(high) === true
    && metaMatcher({ priority: 'all', due: 'soon', tag: '' })(in3Days) === true
    && metaMatcher({ priority: 'all', due: 'soon', tag: '' })(overdueItem) === false);
check('筛选：无截止日期', metaMatcher({ priority: 'all', due: 'none', tag: '' })(noMeta) === true
    && metaMatcher({ priority: 'all', due: 'none', tag: '' })(high) === false);
check('筛选：多个条件是与关系', metaMatcher({ priority: 'high', due: 'today', tag: 'python' })(high) === true
    && metaMatcher({ priority: 'high', due: 'overdue', tag: 'python' })(high) === false);

// —— 归档筛选语义 ——
const projectMatchesFilter = new Function('projectFilters', 'getProjectTotal', 'getProjectRemaining',
    `${extract('projectMatchesFilter')} return projectMatchesFilter;`
)({ query: '', status: 'active' }, () => 5, () => 2);
check('归档：默认（进行中）排除已归档', projectMatchesFilter({ archived: true, name: 'x' }) === false);
check('归档：默认包含未归档的活跃项目', projectMatchesFilter({ archived: false, name: 'x' }) === true);
const archivedOnly = new Function('projectFilters', 'getProjectTotal', 'getProjectRemaining',
    `${extract('projectMatchesFilter')} return projectMatchesFilter;`
)({ query: '', status: 'archived' }, () => 5, () => 2);
check('归档：切到"已归档"只看归档项目', archivedOnly({ archived: true, name: 'x' }) === true
    && archivedOnly({ archived: false, name: 'x' }) === false);

// 元数据筛选本身也算"正在筛选"：只选优先级/截止/标签时 isNodeFiltering 必须为真，
// 否则 renderDetail 会走"整棵树原样渲染"的分支，筛选条件被完全忽略。
const isNodeFilteringFactory = new Function('nodeFilters',
    `${extract('isNodeFiltering')} return isNodeFiltering;`);
const isNodeFiltering = filters => isNodeFilteringFactory(filters)(filters);
check('筛选：只选元数据条件也算正在筛选',
    isNodeFiltering({ query: '', status: 'all', priority: 'high', due: 'all', tag: '' }) === true
    && isNodeFiltering({ query: '', status: 'all', priority: 'all', due: 'overdue', tag: '' }) === true
    && isNodeFiltering({ query: '', status: 'all', priority: 'all', due: 'all', tag: 'x' }) === true
    && isNodeFiltering({ query: '', status: 'all', priority: 'all', due: 'all', tag: '' }) === false
    && isNodeFiltering({ query: 'a', status: 'all', priority: 'all', due: 'all', tag: '' }) === true);

// —— 接线断言 ——
check('归档：页面有"已归档"筛选项', html.includes('<option value="archived">已归档</option>'));
check('归档：卡片与详情都有归档入口', src.includes("archiveBtn.textContent = project.archived ? '↩' : '▣'")
    && html.includes('id="projectArchiveBtn"'));
check('归档：切换走 ensureProjectLoaded + 落库', /async function toggleProjectArchived[\s\S]{0,500}await ensureProjectLoaded\(projectId\);[\s\S]{0,200}await saveProjects\(\);/.test(src));
// 前后端都要保留 archived：前端归一化丢掉它时，刷新后"已归档"恒为空、按钮永远是"归档"
const normalizeProjectsSrc = extract('normalizeProjects');
check('归档：normalizeProjects 保留 archived 字段', /archived:\s*Boolean\(project\.archived\)/.test(normalizeProjectsSrc));
check('归档：normalizeProjectSummary 保留 archived 字段',
    /archived:\s*Boolean\(project\.archived\)/.test(extract('normalizeProjectSummary')));
check('归档：冲突合并结果也带 archived', /archived:\s*Boolean\(projectChoice === 'remote'/.test(extract('mergeProjects')));
// 收集箱是快速添加的落点：归档后工作台看不见它、任务像丢了，所以三处都要拦住
check('归档：收集箱不能归档（切换函数直接拦下并提示）',
    /async function toggleProjectArchived\(projectId\) \{[\s\S]{0,300}INBOX_PROJECT_ID[\s\S]{0,300}return;/.test(src));
check('归档：收集箱卡片不显示归档按钮',
    /String\(project\.id\) !== INBOX_PROJECT_ID[\s\S]{0,120}actions\.appendChild\(archiveBtn\)/.test(src));
check('归档：收集箱详情页归档按钮置灰',
    /projectArchiveBtn\.disabled = isInbox/.test(src));
// 筛选视图（保存/应用/删除）已按冗余审计取消：这里改成"不许再长回来"的守卫。
check('视图：筛选视图功能已取消（页面/接口/存储都不该再有）',
    !html.includes('id="viewBar"') && !html.includes('id="saveViewBtn"')
    && !src.includes('/api/views') && !src.includes('function currentFilterSnapshot')
    && !src.includes('function applySavedView'));
check('批量：页面有开关与工具栏', html.includes('id="batchToggleBtn"') && html.includes('id="batchToolbar"'));
check('批量：模式切换会清空选择并重渲染', /function setBatchMode[\s\S]{0,300}if \(!batchState\.active\) batchState\.selected\.clear\(\);[\s\S]{0,200}renderDetail\(\);/.test(src));
check('批量：动作齐全（优先级/标签/截止/延期/完成/移动）',
    src.includes("addButton('高', () => runBatch('set-priority', 'high')")
    && src.includes("addButton('加标签…'") && src.includes("addButton('设截止…'")
    && src.includes("addButton('延期 +1 天', () => runBatch('shift-due', 1))")
    && src.includes("addButton('标为完成'") && src.includes("addButton('移动到项目…', openBatchMovePicker)"));
check('批量：提交 /api/batch 并按项目刷新', /async function runBatch[\s\S]{0,700}'\/api\/batch'[\s\S]{0,1400}await reloadProjectFromServer\(projectId\);/.test(src));
check('批量：跳过项会提示原因', src.includes('项被跳过：${failed[0].error}'));
check('批量：同步服务端统计', src.includes('projects[index].stats = summary.stats;'));
check('批量：样式已加', css.includes('.batch-toolbar') && css.includes('.batch-selected'));
const failed = results.filter(r => !r).length;
console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
process.exit(failed ? 1 : 0);
