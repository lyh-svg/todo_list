// 第 2 轮（① textContent / ② 防抖 / ③ DocumentFragment）验证。
// 防抖是纯逻辑 → 真跑行为；三处 DOM 改动是源码级断言（app.js 是 IIFE，无浏览器环境）。
const fs = require('fs');
const ROOT = require('path').resolve(__dirname, '..', '..');
const src = fs.readFileSync(ROOT + '/js/app.js', 'utf8');

function extract(name) {
    const start = src.indexOf(`    function ${name}(`);
    if (!start) throw new Error(`源码里找不到 ${name}`);
    let depth = 0, seen = false;
    for (let i = start; i < src.length; i++) {
        if (src[i] === '{') { depth++; seen = true; }
        else if (src[i] === '}') { depth--; if (seen && depth === 0) return src.slice(start, i + 1); }
    }
    throw new Error(`${name} 括号不配对`);
}

const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
    // —— ② 防抖：真实行为 ——
    const debounce = new Function(`${extract('debounce')} return debounce;`)();
    let calls = [];
    const fn = debounce((...args) => calls.push(args), 30);
    fn(1); fn(2); fn(3); fn(4); fn(5);
    check('② 连续 5 次输入只触发 1 次', calls.length === 0, `触发 ${calls.length} 次`);
    await sleep(70);
    check('② 等待后只触发 1 次', calls.length === 1, `触发 ${calls.length} 次`);
    check('② 用的是最后一次的参数', JSON.stringify(calls[0]) === '[5]', JSON.stringify(calls));
    fn('a'); await sleep(10); fn('b'); await sleep(70);
    check('② 窗口内被后一次覆盖（只剩 b）', calls.length === 2 && calls[1][0] === 'b', JSON.stringify(calls));
    fn('x'); await sleep(70); fn('y'); await sleep(70);
    check('② 窗口外各自触发', calls.length === 4 && calls[3][0] === 'y', JSON.stringify(calls));
    check('② 去抖窗口是 180ms 常量', src.includes('const SEARCH_DEBOUNCE_MS = 180;'));
    check('② 项目搜索走防抖', src.includes('debouncedRenderProjects();'));
    check('② 任务搜索走防抖', src.includes('debouncedRenderDetail();'));
    check('② 两个预绑定都用了 debounce()',
        src.includes('const debouncedRenderProjects = debounce(renderProjects, SEARCH_DEBOUNCE_MS);')
        && src.includes('const debouncedRenderDetail = debounce(renderDetail, SEARCH_DEBOUNCE_MS);'));
    check('② 备忘录搜索防抖（且因改为服务端搜索而为 async）',
        /search\.addEventListener\('input', debounce\(async \(\) => \{\s*memoState\.query = search\.value;/.test(src));
    check('② 模板搜索防抖', src.includes(`search.addEventListener('input', debounce(render, SEARCH_DEBOUNCE_MS));`));

    // —— ① 错误信息不再拼 innerHTML ——
    const innerHtmlAssignments = src.match(/\.innerHTML\s*=\s*[^;]*/g) || [];
    const unsafe = innerHtmlAssignments.filter(s => s.includes('${') || s.includes(' + '));
    check('① 没有任何 innerHTML 拼接（插值/加号）', unsafe.length === 0, JSON.stringify(unsafe.slice(0, 3)));
    const nonRich = innerHtmlAssignments.filter(s => {
        const value = s.split('=').slice(1).join('=').trim();
        return value !== "''" && !value.includes('richToHtml(');
    });
    check('① innerHTML 只剩清空与 richToHtml()', nonRich.length === 0, JSON.stringify(nonRich.slice(0, 3)));
    check('① 静态图标也改用 textContent', !/\.innerHTML = '(&#9675;|✎|✕|\+)'/.test(src));

    // 真的验证 richToHtml 会先转义：注入内容不能变成活的标签
    const escapeHtmlText = new Function(`${extract('escapeHtmlText')} return escapeHtmlText;`)();
    const richToHtml = new Function('escapeHtmlText', `${extract('fmtInline')}
        ${extract('fmtBold')}
        ${extract('richToHtml')}
        return richToHtml;`)(escapeHtmlText);
    const injected = richToHtml('<img src=x onerror=alert(1)>');
    check('① richToHtml 转义 HTML 标签', !injected.includes('<img') && injected.includes('&lt;img'), injected);
    const scripted = richToHtml('<script>alert(1)</script>');
    check('① richToHtml 拦掉 script 注入', !scripted.includes('<script'), scripted);
    const fenced = richToHtml('```python\n<script>bad()</script>\n```');
    check('① 代码块内注入也被转义', fenced.includes('<pre class="rich-code">') && !fenced.includes('<script'), fenced);
    check('① 正常 Markdown 仍生效',
        richToHtml('**粗**').includes('<strong>粗</strong>') && richToHtml('`code`').includes('<code>code</code>'));
    check('① 已无模板串拼 innerHTML', !/innerHTML = `/.test(src));
    const utilityCalls = (src.match(/renderUtilityMessage\(/g) || []).length;
    check('① 弹窗状态统一走 renderUtilityMessage', utilityCalls >= 9, `出现 ${utilityCalls} 次（1 定义 + ${utilityCalls - 1} 调用）`);
    check('① 不再用 innerHTML 拼 <p class="utility-empty">', !src.includes("utilityBody.innerHTML = '<p class=\"utility-empty\">"));
    check('① renderUtilityMessage 用 textContent',
        /function renderUtilityMessage\(text\)[\s\S]{0,220}message\.textContent = text;/.test(src));

    // —— ③ DocumentFragment ——
    const fragmentCount = (src.match(/createDocumentFragment\(\)/g) || []).length;
    check('③ 至少 12 处 fragment 批量挂载', fragmentCount >= 12, `实际 ${fragmentCount}`);
    const leftovers = [
        'projectGrid.appendChild(card)',
        'treeRoot.appendChild(renderNode',
        'container.appendChild(button)',
        'list.appendChild(card)',
        'group.appendChild(projectBlock)',
        'grid.appendChild(item)',
        'databaseBackupMenu.appendChild(row)',
        'assessmentTemplateCustomBar.appendChild(btn)',
        'ul.appendChild(renderNode',
        'childrenUl.appendChild(renderNode',
    ].filter(s => src.includes(s));
    check('③ 循环内逐个挂载的写法已清除', leftovers.length === 0, leftovers.join(', '));
    check('③ 项目卡片一次挂载', src.includes('projectGrid.replaceChildren(cardFragment);'));
    check('③ 详情树一次挂载', src.includes('treeRoot.replaceChildren(treeFragment);'));
    check('③ 备忘录列表一次挂载', src.includes('container.replaceChildren(memoFragment);'));
    check('③ 复习分组一次挂载', src.includes('group.appendChild(blockFragment);'));
    check('③ 摘要卡片一次挂载', src.includes('grid.replaceChildren(summaryFragment);'));
    check('③ 回收站一次挂载', src.includes('list.replaceChildren(trashFragment);'));
    check('③ 今日聚焦用 replaceChildren(...map())',
        src.includes('list.replaceChildren(...entries.slice(0, visibleCount).map(entry => createTaskButton(entry, project.id)));'));
    check('③ 懒展开分支一次挂载', src.includes('ul.appendChild(branchFragment);'));

    // —— 回归自查：空状态/提前 return 时不能留下旧 DOM ——
    check('③ 项目空/失败状态会清空网格', /function renderProjectsMessage\(state\)[\s\S]{0,160}projectGrid\.replaceChildren\(\);/.test(src));
    check('③ 详情树在空状态前已清空', src.includes('treeRoot.replaceChildren();'));
    check('③ 备忘录空状态用 replaceChildren', src.includes('container.replaceChildren(empty);'));

    const failed = results.filter(r => !r).length;
    console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
    process.exit(failed ? 1 : 0);
})();
