// R4/R5 前端接线验证：统一备份 UI + 回收站批量 UI + 大批量改动前快照。
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
// R4 备份 UI
// 备份 UI 按冗余审计瘦身：只留 列表 / 下载 / 删除 / 恢复；"创建、重命名、查看内容"取消
check('R4 ⑧ 备份操作只剩 列表/下载/删除/恢复',
    html.includes('id="downloadDatabaseBackupBtn"') && html.includes('id="restoreDatabaseBackupBtn"')
    && !html.includes('id="createDatabaseBackupBtn"') && !html.includes('id="renameDatabaseBackupBtn"')
    && !html.includes('id="inspectDatabaseBackupBtn"') && !src.includes('/api/backup/inspect')
    && !src.includes("action: 'create'") && !src.includes("action: 'rename'"));
check('R4 ⑧ 备份列表区分完整备份与旧格式', src.includes("backup.kind === 'legacy' ? ' · 旧格式' : ''"));
check('R4 ⑧ 恢复前有确认（说明会先自动备份并重载页面）',
    /function restoreDatabaseBackupFromUi[\s\S]{0,400}确认恢复数据库备份/.test(src));
check('R4 ⑧ 备份仍可删除（下拉里的 ×）', /deleteDatabaseBackupByName/.test(src));
check('R4 ⑧ 导出仍然是 JSON（与备份分开）', src.includes("await apiFetch(`/api/export?format="));
check('R4 ⑧ 导出/备份下载不再把 token 放进 URL（改走请求头 + Blob）',
    !src.includes('?token=') && src.includes('function saveBlobAs(blob, fileName)')
    && src.includes("apiFetch(`/api/backup/download?name="));
// R4 快照
check('R4 ⑨ 有 createSnapshot 辅助', src.includes('async function createSnapshot(reason)'));
check('R4 ⑨ 清空已完成前先快照', src.includes("await createSnapshot('before-clear-completed');"));
check('R4 ⑨ 清理验收记录前先快照', src.includes("await createSnapshot('before-clear-history');"));
check('R4 ⑨ 清空已完成有确认', src.includes('确认清空 ${completedIds.length} 项已完成任务'));
// R5 回收站
check('R5 ⑩ 有全选/批量恢复/批量删除/立即清空',
    src.includes("selectAll.textContent = '全选'") && src.includes("restoreMany.textContent = '批量恢复'")
    && src.includes("deleteMany.textContent = '批量删除'") && src.includes("purgeAll.textContent = '立即清空回收站'"));
check('R5 ⑩ 每条带勾选框', src.includes("box.type = 'checkbox'") && src.includes('trash-head'));
check('R5 ⑩ 显示自动清理日期与保留说明',
    src.includes('自动清理') && src.includes('按设置里的保留天数自动清理'));
check('R5 ⑩ 批量删除/清空先确认并快照',
    src.includes('此操作不可撤销') && src.includes('确认立即清空回收站？') && src.includes("await createSnapshot('before-trash-purge');"));
check('R5 ⑩ 单条恢复也确认', src.includes('确认恢复“'));
check('R5 ⑩ 批量结果含失败明细', src.includes('条失败：${failed[0].error}'));
check('R5 ⑩ 批量恢复后刷新项目列表',
    /projects = payload\.projects\.map\(normalizeProjectSummary\);\s*\r?\n\s*renderProjects\(\);/.test(src));
check('R5 ⑩ 回收站样式已加', css.includes('.trash-head') && css.includes('.trash-action-bar'));
const failed = results.filter(r => !r).length;
console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
process.exit(failed ? 1 : 0);
