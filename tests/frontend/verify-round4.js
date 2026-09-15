// 第 4 轮（⑦ 列表懒加载全文）验证：抽出真实源码里的守卫与接线来断言。
// 最关键的属性：只有拿到全文才允许写回，绝不能用 200 字预览覆盖原文。
const fs = require('fs');
const ROOT = require('path').resolve(__dirname, '..', '..');
const src = fs.readFileSync(ROOT + '/js/app.js', 'utf8');

function extract(name) {
    const start = src.indexOf(`    function ${name}(`);
    const asyncStart = src.indexOf(`    async function ${name}(`);
    const at = start >= 0 ? start : asyncStart;
    if (at < 0) throw new Error(`源码里找不到 ${name}`);
    let depth = 0, seen = false;
    for (let i = at; i < src.length; i++) {
        if (src[i] === '{') { depth++; seen = true; }
        else if (src[i] === '}') { depth--; if (seen && depth === 0) return src.slice(at, i + 1); }
    }
    throw new Error(`${name} 括号不配对`);
}

const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}

// —— 守卫本身：真实源码抽取后调用 ——
const memoContentReady = new Function(`${extract('memoContentReady')} return memoContentReady;`)();
const summaryFromListApi = { id: 'm1', title: '标题', contentPreview: '前 200 字…', contentLength: 5000, revision: 3 };
const loadedMemo = { id: 'm1', title: '标题', content: '完整正文', revision: 3 };
check('⑦ 只有预览 → 判定为未就绪（不许保存）', memoContentReady(summaryFromListApi) === false);
check('⑦ 已取全文 → 判定为就绪', memoContentReady(loadedMemo) === true);
check('⑦ null/空对象 → 未就绪', memoContentReady(null) === false && memoContentReady({}) === false);
check('⑦ 空字符串算已加载（允许保存空备忘录）', memoContentReady({ id: 'x', content: '' }) === true);

// —— 接线检查 ——
check('⑦ persistMemo 有"未加载就拒绝写回"的守卫',
    /function persistMemo\(memo\) \{[\s\S]{0,220}if \(!memoContentReady\(memo\)\) \{[\s\S]{0,120}Promise\.reject/.test(src));
check('⑦ 守卫消息说明了原因（避免覆盖原文）', src.includes('已取消保存以免覆盖原文'));
check('⑦ ensureMemoLoaded 走 GET /api/memo?id=',
    /async function ensureMemoLoaded\(memo\)[\s\S]{0,320}\/api\/memo\?id=/.test(src));
check('⑦ 面板在渲染编辑框前 await ensureMemoLoaded',
    /async function renderMemoPanel\(\)[\s\S]{0,400}await ensureMemoLoaded\(selected\);[\s\S]{0,4000}contentInput\.value = memo\.content;/.test(src));
check('⑦ 列表预览优先用已加载的实时正文，否则用服务端预览',
    src.includes("const liveText = typeof memo.content === 'string' ? memo.content : (memo.contentPreview || '');")
    && !src.includes("preview.textContent = memo.content.replace"));
check('⑦ 编辑器输入不再逐字重建列表（走防抖）',
    src.includes("const refreshList = debounce(() => renderMemoList(list, editor), SEARCH_DEBOUNCE_MS);")
    && (src.match(/refreshList\(\);/g) || []).length === 2);
check('⑦ 列表不再前端过滤 content',
    !/visible = memoState\.memos\.filter\(memo => !query[\s\S]{0,80}memo\.content/.test(src));
check('⑦ 搜索改为服务端 ?q=',
    src.includes("await loadMemos(memoState.query.trim());") && src.includes('`/api/memos${suffix}`'));
check('⑦ loadMemos 支持 q 参数', src.includes("const suffix = query ? `?q=${encodeURIComponent(query)}` : '';"));
check('⑦ 搜索前先落盘未保存的编辑', /search\.addEventListener\('input', debounce\(async \(\) => \{[\s\S]{0,200}if \(memoState\.saveTimer\) await saveMemoNow/.test(src));
check('⑦ 重新加载时保留已取得的全文',
    src.includes('loadedContent') && src.includes('Object.assign(summary, { content: loadedContent.get(summary.id) })'));
check('⑦ 打开备忘录时清空上一次的搜索词', /async function openMemoTool\(\)[\s\S]{0,220}memoState\.query = '';/.test(src));
check('⑦ 列表显示更新时间与字数',
    src.includes('memo.updatedAt.slice(0, 10)') && src.includes('memo.contentLength'));

// —— 服务端契约（对应的 python 测试在 tests/test_memo_summaries.py）——
check('⑦ /api/memos 只回预览字段（服务端测试覆盖）', fs.existsSync(ROOT + '/tests/test_memo_summaries.py'));

const failed = results.filter(r => !r).length;
console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
process.exit(failed ? 1 : 0);
