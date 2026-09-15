// 第 1 轮（⑧ 状态）验证：从 js/app.js 源码里抽出新增的纯函数，用固定输入断言行为。
// 说明：app.js 是 IIFE、函数外部不可达；这里按函数名抽取真实源码后求值，测的是仓库里的代码而不是复制品。
const fs = require('fs');
const ROOT = require('path').resolve(__dirname, '..', '..');
const src = fs.readFileSync(ROOT + '/js/app.js', 'utf8');

function extract(name) {
    const start = src.indexOf(`    function ${name}(`);
    if (start < 0) throw new Error(`源码里找不到 ${name}`);
    let depth = 0, seen = false;
    for (let i = start; i < src.length; i++) {
        if (src[i] === '{') { depth++; seen = true; }
        else if (src[i] === '}') { depth--; if (seen && depth === 0) return src.slice(start, i + 1); }
    }
    throw new Error(`${name} 括号不配对`);
}

const factory = new Function(
    `${extract('projectsEmptyStateView')}
     ${extract('listStatusText')}
     return { projectsEmptyStateView, listStatusText };`
);
const api = factory();

const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}

// —— 空状态 bug：读失败不能再显示"还没有项目" ——
const failed = api.projectsEmptyStateView('SQLite 服务不可用', 0, 0);
check('⑧ 读失败 → 文案是"读取项目失败：…"', failed && failed.text === '读取项目失败：SQLite 服务不可用', JSON.stringify(failed));
check('⑧ 读失败 → 给重试按钮', failed && failed.retry === true);
check('⑧ 读失败 → 不再出现"还没有项目"', failed && !failed.text.includes('还没有项目'), failed && failed.text);

const trulyEmpty = api.projectsEmptyStateView('', 0, 0);
check('⑧ 真·空库 → 保留原文案且不给重试', trulyEmpty && trulyEmpty.text === '还没有项目，创建一个开始学习吧' && trulyEmpty.retry === false, JSON.stringify(trulyEmpty));

const filtered = api.projectsEmptyStateView('', 3, 0);
check('⑧ 筛选无结果 → "没有符合筛选条件的项目"', filtered && filtered.text === '没有符合筛选条件的项目' && filtered.retry === false, JSON.stringify(filtered));

const normal = api.projectsEmptyStateView('', 3, 3);
check('⑧ 有内容 → 返回 null（不显示空状态）', normal === null, JSON.stringify(normal));

check('⑧ 失败 + 有缓存项目时优先报错', api.projectsEmptyStateView('服务不可用', 2, 2).retry === true);

// —— 统一的列表状态文案 ——
check('⑧ 复习队列 loading', api.listStatusText('review', 'loading') === '正在读取复习队列…', api.listStatusText('review', 'loading'));
check('⑧ 复习队列 failed 带原因', api.listStatusText('review', 'failed', '项目不存在') === '读取复习队列失败：项目不存在');
check('⑧ 备份 failed 带原因', api.listStatusText('backup', 'failed', '服务不可用') === '读取数据库备份失败：服务不可用');
check('⑧ 搜索 loading/failed', api.listStatusText('search', 'loading') === '正在读取项目列表…'
    && api.listStatusText('search', 'failed', 'x') === '读取项目列表失败：x');
check('⑧ failed 无原因时有兜底', api.listStatusText('backup', 'failed', '') === '读取数据库备份失败：未知错误');
check('⑧ loading/failed 之外返回空串', api.listStatusText('review', 'done') === '');

// —— 源码层面的接线检查 ——
check('⑧ loadProjects 会记录 stateLoadError', src.includes("stateLoadError = (error && error.message) || '无法连接本地服务'"));
check('⑧ loadProjects 成功会清空 stateLoadError', src.includes('        stateLoadError = \';\n'.replace("'", "''")) || src.includes("stateLoadError = '';"));
check('⑧ renderProjects 用 projectsEmptyStateView', src.includes('projectsEmptyStateView(stateLoadError, projects.length, visibleProjects.length)'));
check('⑧ 复习队列先显示加载状态', src.includes("renderReviewMessage(listStatusText('review', 'loading'), false)"));
check('⑧ 复习队列失败可重试', src.includes("renderReviewMessage(message, true)"));
check('⑧ 备份失败不再显示"暂无数据库备份"', src.includes("listStatusText('backup', 'failed', backupListError) + '（点击重试）'"));
check('⑧ 备份按钮组可统一禁用', src.includes('function setBackupActionsEnabled(enabled)'));
// R3 起 409 不再静默重试覆盖，而是停写 + 冲突面板（详见 tests/frontend/verify-r3.js）
check('⑧ 409 有明确状态且不静默覆盖',
    src.includes("setSaveStatus('版本冲突', 'error')") && src.includes('await beginProjectConflict(project, current);'));
check('⑧ 三处失败都提供重试入口',
    (src.match(/createRetryButton\(/g) || []).length >= 4);

const failedCount = results.filter(r => !r).length;
console.log(`\n   通过 ${results.length - failedCount} 项，失败 ${failedCount} 项`);
process.exit(failedCount ? 1 : 0);
