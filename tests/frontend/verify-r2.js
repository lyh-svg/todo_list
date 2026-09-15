// R2（④ 导入 ID 校验）前端部分：抽取真实 findImportDuplicateIds 跑用例。
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
const findImportDuplicateIds = new Function(`${extract('findImportDuplicateIds')} return findImportDuplicateIds;`)();
const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}
function project(id, name, items) {
    return { id, name, tree: [{ id: id + 'w', type: 'week', text: '第1周', children: [{ id: id + 'd', type: 'day', text: '单元1', children: items }] }] };
}
const item = (id, text) => ({ id, type: 'item', text, children: [] });

check('R2 ④ 正常文件没有问题', findImportDuplicateIds([project('p1', '项目一', [item('i1', '任务1')])]).length === 0);
const dupProject = findImportDuplicateIds([project('p1', '项目一', [item('i1', '任务1')]), project('p1', '项目二', [item('i2', '任务2')])]);
check('R2 ④ 重复项目 ID 被报出', dupProject.length === 1 && dupProject[0].includes('重复项目 ID') && dupProject[0].includes('p1') && dupProject[0].includes('项目一') && dupProject[0].includes('项目二'), JSON.stringify(dupProject));
const dupNode = findImportDuplicateIds([project('p1', '项目一', [item('i1', '任务1'), item('i1', '任务2')])]);
check('R2 ④ 重复节点 ID 带完整路径', dupNode.length === 1 && dupNode[0].includes('重复节点 ID') && dupNode[0].includes('项目一 / 第1周 / 单元1 / 任务2'), JSON.stringify(dupNode));
check('R2 ④ 跨项目的同名节点 ID 不算重复（与服务端一致）',
    findImportDuplicateIds([project('p1', '项目一', [item('same', '任务1')]), project('p2', '项目二', [item('same', '任务2')])]).length === 0);
check('R2 ④ 缺失 ID 不报问题（交给自动生成）', findImportDuplicateIds([{ id: null, name: '无 ID', tree: [{ type: 'week', text: '第1周', children: [item(undefined, 'x')] }] }]).length === 0);
check('R2 ④ 空/异常输入不抛异常', findImportDuplicateIds([]).length === 0 && findImportDuplicateIds(null).length === 0);
check('R2 ④ 导入流程会先校验再规范化', src.indexOf('findImportDuplicateIds(imported)') > 0 && src.indexOf('导入被拒绝') > 0);
const failed = results.filter(r => !r).length;
console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
process.exit(failed ? 1 : 0);
