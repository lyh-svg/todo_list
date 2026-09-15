// study-tools.js（复习统计 / ISO 周 / 随机抽题）的行为断言。
// 这个文件是 UMD 模块，Node 里可以直接 require；期望值用 Python date.isocalendar() 核对过。
//
// 旧版应用曾在 js/study-tools.js 里手写 ISO 周算法，很容易在跨年那一周出错，
// 所以这里把已知的边界日期全部钉死。
const path = require('path');
const ROOT = path.resolve(__dirname, '..', '..');
const tools = require(path.join(ROOT, 'js', 'study-tools.js'));

const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}
const same = (left, right) => JSON.stringify(left) === JSON.stringify(right);

// ---------- ISO 周 ----------
const isoCases = [
    [[2026, 0, 1], { year: 2026, week: 1 }, '2026-01-01 周四 → 2026-W01'],
    [[2025, 11, 29], { year: 2026, week: 1 }, '2025-12-29 周一属于下一年 W01'],
    [[2026, 0, 4], { year: 2026, week: 1 }, '2026-01-04 周日仍属 W01'],
    [[2026, 0, 5], { year: 2026, week: 2 }, '2026-01-05 周一起进入 W02'],
    [[2021, 0, 1], { year: 2020, week: 53 }, '2021-01-01 周五属于上一年 W53'],
    [[2020, 11, 31], { year: 2020, week: 53 }, '2020 有 53 周'],
    [[2023, 0, 1], { year: 2022, week: 52 }, '2023-01-01 周日属于 2022-W52'],
    [[2024, 11, 30], { year: 2025, week: 1 }, '2024-12-30 周一是 2025-W01'],
    [[2019, 11, 30], { year: 2020, week: 1 }, '2019-12-30 周一是 2020-W01'],
    [[2027, 0, 3], { year: 2026, week: 53 }, '2027-01-03 周日属于 2026-W53'],
    [[2027, 0, 4], { year: 2027, week: 1 }, '2027-01-04 周一起是 2027-W01'],
    [[2022, 0, 2], { year: 2021, week: 52 }, '2022-01-02 周日属于 2021-W52'],
    [[2022, 0, 3], { year: 2022, week: 1 }, '2022-01-03 周一起是 2022-W01'],
    [[2026, 8, 15], { year: 2026, week: 38 }, '普通日期：2026-09-15 → W38'],
];
isoCases.forEach(([args, expected, label]) => {
    check(`ISO 周：${label}`, same(tools.getIsoWeek(new Date(...args)), expected),
        JSON.stringify(tools.getIsoWeek(new Date(...args))));
});

// 带时分秒的本地时间不应该因为 UTC 转换而跳到前一天/后一天
check('ISO 周：当天 23:30 与 00:10 属于同一周',
    same(tools.getIsoWeek(new Date(2026, 8, 15, 23, 30)), tools.getIsoWeek(new Date(2026, 8, 15, 0, 10))));
check('ISO 周：跨年当天的深夜仍按本地日期算（2025-12-29 23:59 → 2026-W01）',
    same(tools.getIsoWeek(new Date(2025, 11, 29, 23, 59)), { year: 2026, week: 1 }));

// ---------- collectTaskEntries ----------
function sampleTree() {
    return [{
        id: 'w1', type: 'week', text: '第1周', children: [{
            id: 'd1', type: 'day', text: '单元1', children: [
                { id: 'i1', type: 'item', text: '未完成任务', completed: false, optional: false },
                { id: 'i2', type: 'item', text: '已完成任务', completed: true, optional: false },
                { id: 'i3', type: 'item', text: '选做任务', completed: false, optional: true },
                { id: 'i4', type: 'item', text: '', completed: false, optional: false },
            ],
        }, {
            id: 'd2', type: 'day', text: '单元2', children: [
                { id: 'i5', type: 'item', text: '第二个单元的任务', completed: false, optional: false,
                  children: [{ id: 'i5c', type: 'item', text: '不该被当成任务', completed: false }] },
            ],
        }],
    }, null, 'not-an-object'];
}
const mainEntries = tools.collectTaskEntries(sampleTree());
check('任务清单：跳过已完成项', !mainEntries.some(entry => entry.id === 'i2'));
check('任务清单：默认不含选做', !mainEntries.some(entry => entry.id === 'i3'));
check('任务清单：空标题回退为"未命名任务"',
    mainEntries.find(entry => entry.id === 'i4').text === '未命名任务');
check('任务清单：路径带周/单元', mainEntries.find(entry => entry.id === 'i1').path === '第1周 / 单元1');
check('任务清单：祖先 id 顺序从外到内',
    same(mainEntries.find(entry => entry.id === 'i5').ancestorIds, ['w1', 'd2']));
check('任务清单：item 的子节点不再遍历（任务视为叶子）',
    !mainEntries.some(entry => entry.id === 'i5c'));
check('任务清单：坏节点/null 不会抛异常', mainEntries.length === 3, String(mainEntries.length));
const withOptional = tools.collectTaskEntries(sampleTree(), true);
check('任务清单：includeOptional=true 时包含选做',
    withOptional.some(entry => entry.id === 'i3') && withOptional.length === 4,
    String(withOptional.length));
check('任务清单：空树返回空数组', same(tools.collectTaskEntries([]), []));
check('任务清单：undefined 也不崩', same(tools.collectTaskEntries(undefined), []));

// ---------- chooseRandomTask ----------
const entries = [{ id: 'a' }, { id: 'b' }, { id: 'c' }];
check('随机抽题：空清单返回 null', tools.chooseRandomTask([]) === null
    && tools.chooseRandomTask(null) === null);
check('随机抽题：random=0 取第一条', tools.chooseRandomTask(entries, () => 0).id === 'a');
check('随机抽题：random 接近 1 取最后一条', tools.chooseRandomTask(entries, () => 0.999999).id === 'c');
check('随机抽题：random=1 不越界', tools.chooseRandomTask(entries, () => 1).id === 'c');
check('随机抽题：random 返回 NaN 时退化为第一条', tools.chooseRandomTask(entries, () => NaN).id === 'a');
check('随机抽题：random 返回负数也不越界', tools.chooseRandomTask(entries, () => -1).id === 'a');
check('随机抽题：0.5 → 中间那条', tools.chooseRandomTask(entries, () => 0.5).id === 'b');
check('随机抽题：单条清单永远返回它', tools.chooseRandomTask([{ id: 'only' }], () => 0.99).id === 'only');

// ---------- calculateProgressStats ----------
check('统计：空树全是 0', same(tools.calculateProgressStats([]), {
    total: 0, completed: 0, completionRate: 0, mainTotal: 0, mainCompleted: 0,
    optionalTotal: 0, optionalCompleted: 0, busiestWeek: null, latestCompletion: null
}));
check('统计：undefined 不崩', tools.calculateProgressStats(undefined).total === 0);

function progressTree() {
    return [{
        id: 'w1', type: 'week', text: '第1周', children: [{
            id: 'd1', type: 'day', text: '单元1', children: [
                { id: 'a', type: 'item', text: 'A', completed: true, optional: false, completedAt: '2026-09-15T10:00:00' },
                { id: 'b', type: 'item', text: 'B', completed: false, optional: false },
                { id: 'c', type: 'item', text: 'C', completed: true, optional: true, completedAt: '2026-09-15T12:00:00' },
            ],
        }, {
            id: 'd2', type: 'day', text: '单元2', children: [
                { id: 'd', type: 'item', text: 'D', completed: true, optional: false, completedAt: '2026-09-22T09:00:00' },
                { id: 'e', type: 'item', text: 'E', completed: false, optional: true },
            ],
        }],
    }];
}
const stats = tools.calculateProgressStats(progressTree());
check('统计：总数/完成数', stats.total === 5 && stats.completed === 3, JSON.stringify(stats));
check('统计：主线与选做分开计数',
    stats.mainTotal === 3 && stats.mainCompleted === 2
    && stats.optionalTotal === 2 && stats.optionalCompleted === 1, JSON.stringify(stats));
check('统计：完成率四舍五入（3/5 = 60）', stats.completionRate === 60, String(stats.completionRate));
check('统计：最忙的一周按 ISO 周聚合（W38 两条）',
    same(stats.busiestWeek, { year: 2026, week: 38, count: 2 }), JSON.stringify(stats.busiestWeek));
check('统计：最近完成取最新的那条并去掉内部 date 字段',
    stats.latestCompletion && stats.latestCompletion.id === 'd'
    && stats.latestCompletion.completedAt === '2026-09-22T09:00:00'
    && !('date' in stats.latestCompletion), JSON.stringify(stats.latestCompletion));

const oddStats = tools.calculateProgressStats([
    { id: 'x', type: 'item', text: '坏时间', completed: true, completedAt: '不是日期' },
    { id: 'y', type: 'item', text: '没时间', completed: true },
    { id: 'z', type: 'item', text: '没完成', completed: false, completedAt: '2026-09-15T10:00:00' },
]);
check('统计：非法/缺失完成时间不计入周聚合',
    oddStats.completed === 2 && oddStats.busiestWeek === null && oddStats.latestCompletion === null,
    JSON.stringify(oddStats));
check('统计：完成率取整（1/3 → 33）',
    tools.calculateProgressStats([
        { id: '1', type: 'item', text: '1', completed: true },
        { id: '2', type: 'item', text: '2', completed: false },
        { id: '3', type: 'item', text: '3', completed: false },
    ]).completionRate === 33);
check('统计：并列时按年份/周次倒序取第一',
    same(tools.calculateProgressStats([
        { id: 'a', type: 'item', text: 'A', completed: true, completedAt: '2026-09-15T10:00:00' },
        { id: 'b', type: 'item', text: 'B', completed: true, completedAt: '2026-09-22T10:00:00' },
    ]).busiestWeek, { year: 2026, week: 39, count: 1 }));

const failed = results.filter(result => !result).length;
console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
process.exit(failed ? 1 : 0);
