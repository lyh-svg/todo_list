// R2（④ 导入 ID 校验）：重复 ID 由**服务端**在 /api/import/preview 里报告
// （storage.find_import_duplicate_ids，用例在 tests/test_import_export_templates.py），
// 前端只负责"先预览再确认"。
const fs = require('fs');
const ROOT = require('path').resolve(__dirname, '..', '..');
const src = fs.readFileSync(ROOT + '/js/app.js', 'utf8');
const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}
// 第五批之后：导入改成"先预览再确认"，重复 ID 由后端 /api/import/preview 报告并在界面上禁用确认
check('R2 ④ 导入流程会先预览（含重复 ID 检查）再让用户确认',
    src.indexOf('openImportPreview(imported)') > 0
    && src.indexOf('/api/import/preview') > 0
    && src.indexOf('导入会被拒绝') > 0
    && src.indexOf('confirm.disabled = true;') > 0);
const failed = results.filter(r => !r).length;
console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
process.exit(failed ? 1 : 0);
