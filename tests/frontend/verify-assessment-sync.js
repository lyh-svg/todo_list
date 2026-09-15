// 针对 ② 的定向验证：直接从 js/app.js 源码里抽出两个函数的真实实现来跑，
// 断言"加载路径不再重置完成态、手动开关仍然重置"。
// 说明：app.js 是 IIFE、函数外部不可达，也没有 JS 测试框架，所以这里用正则/括号配对
// 抽取源码文本后求值——测的是仓库里的真实代码，而不是复制品。
const fs = require('fs');

const ROOT = require('path').resolve(__dirname, '..', '..');
const SRC = ROOT + '/js/app.js';
const src = fs.readFileSync(SRC, 'utf8');

function extract(name) {
    const start = src.indexOf(`    function ${name}(`);
    if (start < 0) throw new Error(`源码里找不到 ${name}`);
    let depth = 0, seen = false;
    for (let i = start; i < src.length; i++) {
        if (src[i] === '{') { depth++; seen = true; }
        else if (src[i] === '}') {
            depth--;
            if (seen && depth === 0) return src.slice(start, i + 1);
        }
    }
    throw new Error(`${name} 括号不配对`);
}

const factory = new Function(
    'setNodeCompleted', 'markProjectDirty',
    `${extract('applyAssessmentRequirements')}
     ${extract('setProjectAssessmentEnabled')}
     return { applyAssessmentRequirements, setProjectAssessmentEnabled };`
);

const dirtyCalls = [];
const api = factory(
    (node, completed) => { node.completed = Boolean(completed); node.completedAt = completed ? 'stamp' : null; },
    project => dirtyCalls.push(project && project.id)
);

function makeProject() {
    return {
        id: 'p1', assessmentEnabled: true,
        tree: [{
            id: 'w1', type: 'week', children: [{
                id: 'd1', type: 'day', children: [
                    { id: 'a', type: 'item', completed: true, assessmentRequired: false, assessment: { passed: true } },
                    { id: 'b', type: 'item', completed: true, assessmentRequired: false, assessment: null },
                    { id: 'c', type: 'item', completed: false, assessmentRequired: false, assessment: null },
                ]
            }]
        }]
    };
}
const find = (project, id) => project.tree[0].children[0].children.find(n => n.id === id);

const results = [];
function check(name, condition, detail = '') {
    results.push({ name, ok: Boolean(condition) });
    console.log(`${condition ? '   ✔' : '   ✘'} ${name}${condition ? '' : `  [${detail}]`}`);
}

// 场景 1：加载路径（normalizeProjects 用的那个）——不得改动 completed
let project = makeProject();
api.applyAssessmentRequirements(project, true);
check('② 加载路径：已通过验收的 a 仍是 completed', find(project, 'a').completed === true);
check('② 加载路径：无验收记录的 b 仍是 completed（本次修复的关键）', find(project, 'b').completed === true, JSON.stringify(find(project, 'b')));
check('② 加载路径：未完成的 c 保持未完成', find(project, 'c').completed === false);
check('② 加载路径：assessmentRequired 被同步为 true',
    ['a', 'b', 'c'].every(id => find(project, id).assessmentRequired === true));

// 场景 2：加载路径关闭验收——同样不碰完成态
project = makeProject();
api.applyAssessmentRequirements(project, false);
check('② 加载路径(关闭)：completed 全部不变',
    find(project, 'a').completed === true && find(project, 'b').completed === true && find(project, 'c').completed === false);
check('② 加载路径(关闭)：assessmentRequired 同步为 false',
    ['a', 'b', 'c'].every(id => find(project, id).assessmentRequired === false));

// 场景 3：用户手动打开开关——仍然要重置未验收的完成态（原有行为不能丢）
project = makeProject();
dirtyCalls.length = 0;
api.setProjectAssessmentEnabled(project, true);
check('② 手动开关：无验收记录的 b 被重置为未完成', find(project, 'b').completed === false);
check('② 手动开关：已通过验收的 a 保持完成', find(project, 'a').completed === true);
check('② 手动开关：标记为 dirty 以便保存', dirtyCalls.includes('p1'));

// 场景 4：确认 normalizeProjects 调用的是非破坏性版本
const normalizeBody = src.slice(src.indexOf('function normalizeProjects'), src.indexOf('function normalizeProjectSummary'));
check('② normalizeProjects 调用 applyAssessmentRequirements',
    normalizeBody.includes('applyAssessmentRequirements(normalized, normalized.assessmentEnabled)'));
check('② normalizeProjects 不再调用 setProjectAssessmentEnabled',
    !normalizeBody.includes('setProjectAssessmentEnabled'));

// 场景 5：验收弹窗可以从工作台打开（那时 currentProjectId 为 null），
// 所有保存都必须按"节点所属项目"标脏，否则统计缓存不失效、保存只能靠 JSON 差集兜底
for (const [name, argument] of [['验收草稿', 'assessmentNode'], ['生成题目', 'assessmentNode'],
                                ['补题结果', 'assessmentNode'], ['提交结果', 'assessmentNode']]) {
    check(`② ${name} 用 owningProjectOfNode 标脏`,
        new RegExp(`markProjectDirty\\(owningProjectOfNode\\(${argument}\\)\\)`).test(src));
}
check('② 标记脏项目的函数按节点找所属项目',
    /function owningProjectOfNode\(node\) \{[\s\S]{0,300}findNodeById\(project\.tree, node\.id\)/.test(src));

const failed = results.filter(r => !r.ok);
console.log(`\n   通过 ${results.length - failed.length} 项，失败 ${failed.length} 项`);
process.exit(failed.length ? 1 : 0);
