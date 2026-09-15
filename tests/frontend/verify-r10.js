// 第五批（中等难度任务管理）前端接线断言：
// 拖拽排序 / 跨周跨单元移动 / 复制 / 撤销重做（含持久化）/ 导入预览三模式 /
// 多格式导出 / 模板与复制项目 / 活动历史与自动归档 / 回收站恢复目标 / 删除影响面。
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..', '..');
const src = fs.readFileSync(path.join(ROOT, 'js', 'app.js'), 'utf8');
const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const css = fs.readFileSync(path.join(ROOT, 'css', 'style.css'), 'utf8');

const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}
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

// ① 拖拽排序：行可拖拽 + 落点提示 + 调 reorder 接口
check('拖拽：树行设为可拖拽并挂上 drag 事件',
    /function attachDragHandlers\(li, row, node\)[\s\S]{0,300}row\.draggable = true[\s\S]{0,600}dragstart[\s\S]{0,900}dragover[\s\S]{0,600}drop/.test(src));
check('拖拽：renderNode 里真的调用了 attachDragHandlers',
    /attachDragHandlers\(li, row, node\);/.test(src));
check('拖拽：落点提示有样式', css.includes('.drop-before') && css.includes('.drop-after') && css.includes('.drop-inside'));
check('拖拽：跨单元/跨周通过 /api/node/reorder 落库',
    /async function reorderNodeRemote[\s\S]{0,200}\/api\/node\/reorder/.test(src));
check('拖拽：同父节点内向下移动会修正下标',
    /sourcePosition >= 0 && sourcePosition < position/.test(src));

// ② 跨周跨单元（和跨项目）移动
check('移动：有"移动到…"对话框（项目 + 周/单元 + 位置）',
    /async function openMoveNodeDialog\(node\)[\s\S]{0,1200}目标项目[\s\S]{0,800}放到哪一周 \/ 单元[\s\S]{0,400}位置/.test(src));
check('移动：跨项目走 /api/inbox/move，同项目走 reorder',
    /openMoveNodeDialog[\s\S]{0,3000}reorderNodeRemote[\s\S]{0,3000}\/api\/inbox\/move/.test(src));
check('移动：行内有 ⇄ 按钮', /moveBtn\.textContent = '⇄'/.test(src));

// ③ 复制任务 / 整枝
check('复制：行内有 ⧉ 按钮并打开选项对话框',
    /copyBtn\.textContent = '⧉'/.test(src) && /duplicateNodeWithOptions/.test(src));
check('复制：选项包含子任务/完成状态/AI 历史/复习',
    /includeChildren[\s\S]{0,200}keepCompletion[\s\S]{0,200}keepAssessment[\s\S]{0,200}keepReview/.test(src));
check('复制：调 /api/node/duplicate', /\/api\/node\/duplicate/.test(src));

// ④⑤ 撤销 / 重做 + 持久化
check('撤销：有 undo/redo 两步栈与 localStorage 持久化',
    src.includes('UNDO_STORAGE_KEY')
    && src.includes('localStorage.getItem(UNDO_STORAGE_KEY')
    && src.includes('function persistUndoStack')
    && src.includes('JSON.stringify({ undo: undoStack, redo: redoStack })'));
check('撤销：Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y 快捷键',
    /function handleHistoryShortcut[\s\S]{0,900}key === 'z' && event\.shiftKey[\s\S]{0,200}performRedo\(\)[\s\S]{0,300}performUndo\(\)/.test(src));
check('撤销：输入框里不劫持快捷键',
    /tag === 'input' \|\| tag === 'textarea' \|\| tag === 'select'/.test(src));
check('撤销：页面加载时恢复上次的历史', /loadUndoStack\(\);/.test(src));
check('撤销：详情页有撤销/重做按钮', html.includes('id="undoBtn"') && html.includes('id="redoBtn"'));
check('撤销：没有可撤销内容时按钮置灰', /undoBtn\.disabled = undoStack\.length === 0/.test(src));
check('撤销：移动、删除、复制、批量、清空、导入都记了历史',
    ['label: \'移动任务\'', 'kind: \'node-delete\'', 'kind: \'node-duplicate\'', 'kind: \'node-fields\'',
     'kind: \'restore-backup\''].every(needle => src.includes(needle)));

// ⑥ 清空/批量前有恢复入口
check('恢复入口：清空前先做快照并把快照写进撤销栈',
    /const snapshotName = await createSnapshot\('before-clear-completed'\)[\s\S]{0,2000}kind: 'restore-backup'/.test(src));
check('恢复入口：批量修改记录字段前后值（可撤销可重做）',
    /function captureBatchFields[\s\S]{0,600}BATCH_FIELD_KEYS/.test(src)
    && /kind: 'node-fields'/.test(src));

// ⑦⑧ 导入预览与三种模式
check('导入：先预览再确认（不再直接 confirm + 覆盖）',
    src.includes("showUtilityModal('导入预览'") && src.includes('/api/import/preview'));
check('导入：三种模式可选', src.includes('替换全部') && src.includes('合并到现有项目') && src.includes('导入为新项目'));
check('导入：报告显示新增/更新/移除/重复/AI 历史处理方式',
    /重复 ID[\s\S]{0,600}新增项目：[\s\S]{0,600}更新项目：[\s\S]{0,600}将被移除[\s\S]{0,900}AI 历史：/.test(src));
check('导入：可勾选是否保留 AI 历史', /保留文件里的 AI 验收历史与复习安排/.test(src));
check('导入：有重复 ID 时禁用确认按钮', /confirm\.disabled = true;/.test(src) && /preview\.duplicates/.test(src));
check('导入：成功后把"导入前快照"写进撤销栈（可整体回退）',
    /result\.backup[\s\S]{0,300}kind: 'restore-backup'/.test(src));

// ⑨ 三种导出格式
check('导出：JSON / Markdown / CSV 三个入口', html.includes('id="exportBtn"')
    && html.includes('id="exportMarkdownBtn"') && html.includes('id="exportCsvBtn"'));
check('导出：按格式带 format 参数与扩展名',
    /async function exportBackup\(format = 'json'\)[\s\S]{0,900}format=\$\{encodeURIComponent\(format\)\}[\s\S]{0,400}meta\.ext/.test(src));

// ⑩ 项目模板与复制项目
check('模板：内置 + 自定义模板列表接口', /\/api\/templates/.test(src) && /function renderTemplateList/.test(src));
check('模板：从模板创建项目', /\/api\/project\/from-template/.test(src) && /function createProjectFromTemplate/.test(src));
check('模板：可以把当前项目存为模板', /async function saveCurrentProjectAsTemplate[\s\S]{0,400}\/api\/templates/.test(src));
check('模板：页面有模板下拉与"用模板新建"', html.includes('id="templateSelect"') && html.includes('id="createFromTemplateBtn"'));
check('复制项目：可选保留完成状态/AI 历史/复习',
    /async function duplicateCurrentProject[\s\S]{0,700}keepAssessment[\s\S]{0,300}\/api\/project\/duplicate/.test(src));
check('复制项目：详情页有入口', html.includes('id="duplicateProjectBtn"') && html.includes('id="saveTemplateBtn"'));

// ⑪ 活动历史 + 自动归档 + 已完成筛选
check('活动：拉取并渲染活动历史', /\/api\/activity\?limit=50/.test(src) && /function renderActivity/.test(src));
check('活动：可以清空历史', /clearActivityBtn\.addEventListener/.test(src) && /callApi\('\/api\/activity', 'DELETE'\)/.test(src));
check('设置：回收站保留天数与自动归档可配置', html.includes('id="trashRetentionInput"')
    && html.includes('id="autoArchiveDaysInput"') && html.includes('id="autoArchiveToggle"'));
check('设置：保存走 /api/settings', /async function saveSettingsFromUi[\s\S]{0,500}\/api\/settings/.test(src));
check('自动归档：有"立即归档已完成项目"入口', html.includes('id="runAutoArchiveBtn"') && /\/api\/archive\/auto/.test(src));
check('已完成筛选仍在（项目列表过滤器）', html.includes('<option value="completed">已完成</option>')
    && /projectFilters\.status === 'completed'/.test(src));

// ⑫ 回收站恢复目标
check('回收站：展示恢复目标（原位/孤立任务箱/不可恢复）',
    /restoreTarget === 'orphan'|restoreTarget/.test(src) && /孤立任务箱/.test(src));
check('回收站：批量恢复与整项目恢复仍可用',
    src.includes("'restore-many'") && /kind: 'project'/.test(src)
    && src.includes("action: 'restore'"));

// ⑬ 删除前显示影响面
check('删除：先查影响面再确认', /async function verifyDeleteImpact[\s\S]{0,300}\/api\/node\/delete-impact/.test(src)
    && /const detail = describeImpact\(impact\)[\s\S]{0,200}window\.confirm/.test(src));
check('删除：影响面包含子节点/任务数/已完成/耗时', /function describeImpact[\s\S]{0,600}descendantCount[\s\S]{0,200}itemCount[\s\S]{0,200}completedCount[\s\S]{0,200}estimateMinutes/.test(src));
check('删除：进回收站后可撤销', /kind: 'node-delete'/.test(src) && /pushUndoStep\(\{[\s\S]{0,200}trashId/.test(src));

// 版本号与样式
check('资源版本号已更新', /app\.js\?v=\d+/.test(html) && /style\.css\?v=\d+/.test(html));
check('新面板样式已加', css.includes('.template-row') && css.includes('.activity-row')
    && css.includes('.import-report') && css.includes('.option-row'));

const failed = results.filter(result => !result).length;
console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
process.exit(failed ? 1 : 0);
