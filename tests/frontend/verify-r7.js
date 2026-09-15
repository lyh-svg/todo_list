// 批次 2 前端接线验证：今日工作台 / 收集箱 / 最近入口。
const fs = require('fs');
const ROOT = require('path').resolve(__dirname, '..', '..');
const src = fs.readFileSync(ROOT + '/js/app.js', 'utf8');
const html = fs.readFileSync(ROOT + '/index.html', 'utf8');
const css = fs.readFileSync(ROOT + '/css/style.css', 'utf8');
const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}
check('批次2 页面有工作台视图与两个入口', html.includes('id="workbenchView"') && html.includes('id="openWorkbenchBtn"') && html.includes('id="openRecentBtn"'));
check('批次2 视图含快速添加输入与刷新', html.includes('id="quickAddInput"') && html.includes('id="quickAddBtn"') && html.includes('id="workbenchRefreshBtn"'));
check('批次2 工作台拉取接口带本地日期', src.includes('`/api/workbench?today=${encodeURIComponent(todayStr())}`'));
check('批次2 五个分组都渲染', src.includes("overdue: '逾期'") && src.includes("today: '今天到期'") && src.includes("next7: '未来 7 天'") && src.includes("reviewToday: '今天要复习'") && src.includes("inbox: '收集箱（待归类）'"));
check('批次2 每个分组显示数量', src.includes("count.textContent = String(items.length)"));
check('批次2 行内动作齐全（完成/延期/归类/详情/打开）',
    src.includes("done.textContent = '完成'") && src.includes("tomorrow.textContent = '延期到明天'")
    && src.includes("fileIt.textContent = '归类'") && src.includes("detail.textContent = '详情'")
    && src.includes("open.textContent = '打开'"));
check('批次2 完成按钮走既有完成/验收逻辑', /async function completeWorkbenchItem[\s\S]{0,400}toggleNodeCompleted\(node\);/.test(src));
check('批次2 完成后先落库再刷新工作台', /async function completeWorkbenchItem[\s\S]{0,500}await saveProjects\(\);[\s\S]{0,80}showWorkbench\(\)/.test(src));
check('批次2 延期到明天并落库', /async function postponeWorkbenchItem[\s\S]{0,400}node\.dueDate = addDaysToIso\(todayStr\(\), 1\);[\s\S]{0,200}await saveProjects\(\);/.test(src));
check('批次2 详情复用元数据弹窗', src.includes('openWorkbenchItemMeta(item)') && /withWorkbenchNode\(item, \(node\) => openNodeMeta\(node, \{ onSaved/.test(src));
check('批次2 打开任务用祖先链定位', /async function locateNodeById[\s\S]{0,700}await locateStudyTask\(projectId, \{ id: nodeId, ancestorIds/.test(src));
check('批次2 快速添加进收集箱并刷新',
    /async function submitQuickAdd[\s\S]{0,400}'\/api\/inbox\/add'/.test(src)
    && /if \(!hasMeta\)[\s\S]{0,700}await loadProjects\(\);[\s\S]{0,120}showWorkbench\(\);/.test(src));
check('批次2 快速添加支持回车', src.includes("quickAddInput.addEventListener('keydown'") && src.includes("if (event.key === 'Enter')"));
check('批次2 归类弹窗两级选择（项目 + 周/单元）',
    src.includes("projectCaption.textContent = '目标项目'") && src.includes("parentCaption.textContent = '放到哪一周 / 单元'")
    && src.includes('flattenParentOptions(project)'));
check('批次2 归类调用 /api/inbox/move 并刷新项目与工作台',
    /'\/api\/inbox\/move'[\s\S]{0,900}renderProjects\(\);[\s\S]{0,120}showWorkbench\(\);/.test(src));
check('批次2 归类后清空已保存 JSON 基准（避免假脏）', src.includes('savedProjectJsonById.clear();'));
check('批次2 最近弹窗三段（打开/修改/完成）',
    src.includes("addSection('最近打开'") && src.includes("addSection('最近修改'") && src.includes("addSection('最近完成'"));
check('批次2 最近完成点击定位到任务', /completedRow[\s\S]{0,900}locateNodeById\(entry\.projectId, entry\.nodeId\)/.test(src));
check('批次2 工作台失败可重试', src.includes('renderReviewMessageInto(workbenchBody, error.message') && src.includes("createRetryButton('重试', retryHandler || showWorkbench)"));
check('批次2 返回按钮回项目列表', src.includes("workbenchBackBtn.addEventListener('click', () => { showProjectsView(); })"));
check('批次2 工作台快捷输入有样式', css.includes('.workbench-quick input'));
const failed = results.filter(r => !r).length;
console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
process.exit(failed ? 1 : 0);
