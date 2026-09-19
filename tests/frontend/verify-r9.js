// 批次 4 验证：自然语言解析表 + 周期日期计算（真跑）+ 提醒/预览接线。
const fs = require('fs');
const ROOT = require('path').resolve(__dirname, '..', '..');
function read(relative) {
    return fs.readFileSync(ROOT + '/' + relative, 'utf8');
}
const src = read('js/app.js');
const html = fs.readFileSync(ROOT + '/index.html', 'utf8');
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
const TODAY = '2026-09-15'; // 周二
const pad = v => String(v).padStart(2, '0');
const addDays = (iso, days) => {
    const d = new Date(`${iso}T00:00:00`); d.setDate(d.getDate() + Number(days));
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};
const validIso = value => /^\d{4}-\d{2}-\d{2}$/.test(String(value)) && (() => {
    const [y, m, d] = String(value).split('-').map(Number);
    const probe = new Date(y, m - 1, d);
    return probe.getFullYear() === y && probe.getMonth() === m - 1 && probe.getDate() === d;
})();
const cleanRepeat = new Function('isValidIsoDate', `${extract('cleanRepeat')} return cleanRepeat;`)(validIso);
const api = new Function('todayStr', 'isValidIsoDate', 'addDaysToIso', 'cleanRepeat', 'MAX_TAG_CHARS',
    `${extract('parseQuickAdd')}
     ${extract('nextRepeatDue')}
     return { parseQuickAdd, nextRepeatDue };`
)(() => TODAY, validIso, addDays, cleanRepeat, 40);
const projects = [{ id: 'p-python', name: 'Python 项目' }, { id: 'p-work', name: '工作' }];
const parse = text => api.parseQuickAdd(text, { today: TODAY, projects });

const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}
function expect(text, expected) {
    const draft = parse(text);
    const detail = JSON.stringify(draft);
    const ok = Object.entries(expected).every(([key, value]) => JSON.stringify(draft[key]) === JSON.stringify(value));
    check(`解析「${text}」→ ${JSON.stringify(expected)}`, ok, detail);
}

expect('明天复习 Python 装饰器 #Python !高 30分钟', {
    text: '复习 Python 装饰器', dueDate: '2026-09-16', priority: 'high', tags: ['Python'], estimateMinutes: 30,
});
expect('后天 交周报 !中', { text: '交周报', dueDate: '2026-09-17', priority: 'mid' });
expect('3天后 体检', { text: '体检', dueDate: '2026-09-18' });
expect('周五 复盘', { text: '复盘', dueDate: '2026-09-18' });
expect('下周一 站会', { text: '站会', dueDate: '2026-09-21' });
expect('下周三 评审', { text: '评审', dueDate: '2026-09-23' });
expect('9月30日 交房租 每月30日', { text: '交房租', dueDate: '2026-09-30', repeat: { freq: 'monthly', day: 30 } });
expect('12-25 买礼物', { text: '买礼物', dueDate: '2026-12-25' });
expect('每天 背单词 30分钟', { text: '背单词', repeat: { freq: 'daily', interval: 1 }, estimateMinutes: 30 });
expect('每个工作日 写日报', { text: '写日报', repeat: { freq: 'weekday' } });
expect('每周一 复盘', { text: '复盘', repeat: { freq: 'weekly', weekday: 1 } });
expect('@Python项目 修 bug', { text: '修 bug', projectId: 'p-python', projectName: 'Python 项目' });
expect('!! 紧急修复', { text: '紧急修复', priority: 'high' });
expect('!3 琐事', { text: '琐事', priority: 'low' });
expect('读文档 1.5小时', { text: '读文档', estimateMinutes: 90 });
expect('今天 交作业', { text: '交作业', dueDate: TODAY });
const plain = parse('没有元数据的一句话');
check('解析：无元数据时 matched 为空（走快速路径）', plain.matched.length === 0 && plain.text === '没有元数据的一句话', JSON.stringify(plain));
const badProject = parse('@不存在的项目 做事');
check('解析：项目找不到时保留原文并给出警告',
    badProject.projectId === null && badProject.warnings.length === 1 && badProject.text.includes('@不存在的项目'),
    JSON.stringify(badProject));
const badDate = parse('2月30日 无效日期');
check('解析：不存在的日期不被吃掉', badDate.dueDate === '' && badDate.text.includes('2月30日'), JSON.stringify(badDate));

// 周期日期计算（与 Python 同规则）
check('周期：每天 → 次日', api.nextRepeatDue({ freq: 'daily' }, '2026-09-15') === '2026-09-16');
check('周期：每 2 天', api.nextRepeatDue({ freq: 'daily', interval: 2 }, '2026-09-15') === '2026-09-17');
check('周期：工作日跳过周末', api.nextRepeatDue({ freq: 'weekday' }, '2026-09-18') === '2026-09-21');
check('周期：每周一', api.nextRepeatDue({ freq: 'weekly', weekday: 1 }, '2026-09-15') === '2026-09-21');
check('周期：每月 31 号顺延短月', api.nextRepeatDue({ freq: 'monthly', day: 31 }, '2026-09-15') === '2026-10-31');
check('周期：until 到点即停', api.nextRepeatDue({ freq: 'daily', until: '2026-09-15' }, '2026-09-15') === '');
check('周期：非法规则返回空', api.nextRepeatDue({ freq: 'hourly' }, '2026-09-15') === '');

// 接线
// Q13：周期任务的"下一次"由服务端生成，前端只把响应里的副本拼回本地树并提示
check('接线：完成后由服务端生成下一次并拼回本地树',
    !src.includes('function spawnNextOccurrence(')
    && /function applySpawnedOccurrences\(project, spawned\)[\s\S]{0,900}showToast\(`周期任务：已生成下一次/.test(src));
check('周期：重复标完成不会再次生成（分组连点会指数复制）', /toggleAllChildren[\s\S]{0,600}Boolean\(node\.completed\) !== Boolean\(completed\)/.test(src));
check('周期：保存时保留规则锚点（每周几/每月几号 + until）',
    /function buildRepeatRule[\s\S]{0,1600}keep = !opts\.anchorChanged/.test(src)
    && /const until = prev && prev\.until/.test(src));
check('工作台：findNodeById 用字符串比较（默认项目的数字 ID 也能查到）',
    /function findNodeById[\s\S]{0,200}const wanted = String\(id\)/.test(src));
check('接线：生成规则只在服务端（前端不再深拷贝节点）',
    !src.includes('function spawnNextOccurrence(')
    && /def _next_occurrence_clone\(node[\s\S]{0,900}clone\["assessment"\] = None/.test(read('storage.py')));
check('接线：元数据弹窗有周期选择与下一次提示',
    src.includes("repeatCaption.textContent = '周期'") && src.includes('下一次：${next}') && src.includes("['daily', '每天']"));
check('接线：徽标显示周期', src.includes('repeat-badge') && src.includes('describeRepeat(node.repeat)'));
check('接线：快速添加会解析并预览', src.includes('const parsed = parseQuickAdd(raw, { today: todayStr(), projects })') && src.includes('openQuickAddPreview(raw, parsed)'));
check('接线：无元数据走最短路径（不弹预览）', /if \(!hasMeta\)[\s\S]{0,400}await submitQuickAdd\(\{ text: parsed\.text \|\| raw \}, ''\);/.test(src));
check('接线：预览可改项目/优先级/截止/标签/耗时/周期',
    src.includes("addField('放到', projectSelect)") && src.includes("addField('优先级', prioritySelect)")
    && src.includes("addField('截止日期', dueInput)") && src.includes("addField('周期', repeatSelect)"));
check('接线：可以加到指定项目', src.includes("body: JSON.stringify({ node, projectId: projectId || undefined, parentId: parentId || undefined })"));
check('接线：提醒页面有开关与授权按钮', html.includes('id="reminderToggleBtn"') && html.includes('id="reminderPermissionBtn"'));
check('接线：提醒每分钟检查并去重',
    src.includes('window.setInterval(() => { checkReminders(); }, 60 * 1000);')
    && src.includes('if (reminderState.fired.has(fireKey)) return;'));
check('接线：提醒覆盖逾期/今天/待复习三组', src.includes("[['overdue', '逾期'], ['today', '今天到期'], ['reviewToday', '待复习']]"));
check('接线：提醒设置持久化', src.includes("REMINDER_STORAGE_KEY = 'todo_list_reminders'") && src.includes('window.localStorage.setItem(REMINDER_STORAGE_KEY'));
check('接线：提醒不谎称能后台推送', src.includes('只在页面开着时生效'));
const failed = results.filter(r => !r).length;
console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
process.exit(failed ? 1 : 0);
