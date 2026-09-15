// 批次 1（元数据）前端验证：normalizeNodeMeta 真跑 + 徽标/编辑弹窗接线断言。
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
const cleanRepeat = new Function('isValidIsoDate', `${extract('cleanRepeat')} return cleanRepeat;`)(
    value => /^\d{4}-\d{2}-\d{2}$/.test(String(value)) && !Number.isNaN(new Date(`${value}T00:00:00`).getTime()));
const normalizeNodeMeta = new Function(
    'isValidIsoDate', 'NODE_PRIORITIES', 'MAX_TAGS', 'MAX_TAG_CHARS', 'MAX_NOTE_CHARS', 'MAX_LINKS', 'MAX_LINK_CHARS', 'MAX_ESTIMATE_MINUTES', 'cleanRepeat',
    `${extract('normalizeNodeMeta')} return normalizeNodeMeta;`
)(
    new Function(`${extract('isValidIsoDate')} return isValidIsoDate;`)(),
    ['high', 'mid', 'low'], 20, 40, 20000, 20, 2000, 60 * 24 * 30, cleanRepeat
);
const formatEstimate = new Function(`${extract('formatEstimate')} return formatEstimate;`)();

const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}

// 正常值
const full = normalizeNodeMeta({
    priority: 'high', dueDate: '2026-09-20', estimateMinutes: 45,
    tags: ['Python', '复习'], note: '备注', links: [{ label: '文档', url: 'https://docs.python.org' }],
});
check('元数据：正常值原样保留',
    full.priority === 'high' && full.dueDate === '2026-09-20' && full.estimateMinutes === 45
    && full.tags.join(',') === 'Python,复习' && full.note === '备注' && full.links[0].url === 'https://docs.python.org',
    JSON.stringify(full));

// 非法值
const bad = normalizeNodeMeta({ priority: 'URGENT', dueDate: '2026-02-30', estimateMinutes: -5, tags: 'x', note: null, links: 'x' });
check('元数据：非法优先级/日期/耗时/标签/链接被清洗',
    bad.priority === '' && bad.dueDate === '' && bad.estimateMinutes === 0
    && Array.isArray(bad.tags) && bad.tags.length === 0 && bad.note === '' && bad.links.length === 0,
    JSON.stringify(bad));
check('元数据：javascript: 链接被丢弃',
    normalizeNodeMeta({ links: [{ url: 'javascript:alert(1)' }] }).links.length === 0);
check('元数据：estimate 上限被夹住',
    normalizeNodeMeta({ estimateMinutes: 1e12 }).estimateMinutes === 60 * 24 * 30);
check('元数据：标签去重且截断到 20 个',
    normalizeNodeMeta({ tags: ['A', 'A', ...Array.from({ length: 30 }, (_, i) => 't' + i)] }).tags.length === 20);
check('元数据：缺省值安全',
    JSON.stringify(normalizeNodeMeta({})) === JSON.stringify({ priority: '', dueDate: '', estimateMinutes: 0, tags: [], links: [], note: '', repeat: null }),
    JSON.stringify(normalizeNodeMeta({})));

// 耗时展示
check('耗时展示：0 不显示，30→30 分，120→2 小时',
    formatEstimate(0) === '' && formatEstimate(30) === '30 分' && formatEstimate(120) === '2 小时' && formatEstimate(90) === '90 分',
    `${formatEstimate(0)}|${formatEstimate(30)}|${formatEstimate(120)}|${formatEstimate(90)}`);

// 接线
check('接线：normalizeNode 会给 item 挂元数据', src.includes("...(type === 'item' ? normalizeNodeMeta(node) : {})"));
check('接线：行内徽标函数存在并渲染优先级/截止/标签/耗时/备注/链接',
    src.includes('function createNodeMetaBadges(node)') && src.includes("priority-badge priority-${node.priority}")
    && src.includes('dueBadgeInfo(node)') && src.includes('tag-badge') && src.includes('estimate-badge')
    && src.includes("'备注'") && src.includes('link-badge'));
check('接线：徽标点击打开元数据弹窗', /wrap\.addEventListener\('click', \(event\) => \{\s*event\.stopPropagation\(\);\s*openNodeMeta\(node\);/.test(src));
check('接线：行内 ⋯ 按钮打开弹窗', src.includes("metaBtn.textContent = '⋯'") && src.includes('openNodeMeta(node);'));
check('接线：弹窗含六类字段与快捷按钮',
    src.includes("addField('优先级', prioritySelect)") && src.includes("addField('截止日期', dueInput)")
    && src.includes("addField('预计耗时（分钟）', estimateInput)") && src.includes("addField('标签', tagsInput)")
    && src.includes("addField('备注', noteInput)") && src.includes("addField('资料链接', linksBox)"));
check('接线：保存走 applyNodeMeta + 落库 + 重渲染',
    /save\.addEventListener\('click', async \(\) => \{[\s\S]{0,900}applyNodeMeta\(node, \{[\s\S]{0,900}saveProjects\(\);[\s\S]{0,200}if \(getCurrentProject\(\)\) renderDetail\(\);/.test(src));
check('接线：截止日期快捷（今天/明天/3 天后/下周/清除）', src.includes("['今天', 0]") && src.includes("['清除', null]"));
check('接线：链接数量上限提示', src.includes('最多 ${MAX_LINKS} 个链接'));
const failed = results.filter(r => !r).length;
console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
process.exit(failed ? 1 : 0);
