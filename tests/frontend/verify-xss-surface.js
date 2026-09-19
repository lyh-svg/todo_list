// item 6 审计固化：把"XSS 面审查通过"变成可回归的断言，而不是一次性人工结论。
//
// 审查结论（本轮复核后仍然成立）：
// - js/app.js 里所有**非空** innerHTML 写入都走 richToHtml()，而 richToHtml 一进来就
//   对整段文本做一次 escapeHtmlText（`lang` 也取自转义后的切片，见 B7）；
// - 三个前端文件里没有 eval / new Function / insertAdjacentHTML / outerHTML / document.write；
// - index.html 没有内联 <script> 或 on* 属性（CSP 也没有 'unsafe-inline'）；
// - 服务端 CSP：script-src 'self'、object-src 'none'、frame-ancestors 'none'；
// - 任务链接的 URL 只允许 http/https（javascript: 已被 storage.clean_links 挡在写入侧，
//   行为用例见 tests/test_node_metadata.py / test_node_patch.py / test_workbench_inbox.py）。
//
// 这里把这些事实钉成断言：以后新增一处 innerHTML 注入点或引入 eval，这条会直接红。
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..', '..');

function read(relative) {
    return fs.readFileSync(path.join(ROOT, relative), 'utf8');
}

// 去掉行注释与块注释，避免把注释里的示例代码当成产品行为（踩过一次：
// 注释里写着 `innerHTML = ''` 的说明文字）。
function stripComments(source) {
    return source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
}

const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}

const JS_FILES = ['js/app.js', 'js/api-client.js', 'js/study-tools.js'];
const sources = Object.fromEntries(JS_FILES.map(name => [name, read(name)]));
const stripped = Object.fromEntries(JS_FILES.map(name => [name, stripComments(sources[name])]));

// ---------- ① 危险 DOM/执行入口 ----------
const DANGEROUS = [
    [/\beval\s*\(/, 'eval('],
    [/new\s+Function\s*\(/, 'new Function('],
    [/\.insertAdjacentHTML\s*\(/, 'insertAdjacentHTML'],
    [/\.outerHTML\s*=/, 'outerHTML ='],
    [/document\.write\s*\(/, 'document.write('],
    [/createElement\(\s*['"]script['"]\s*\)/, "createElement('script')"],
    [/createElement\(\s*['"]iframe['"]\s*\)/, "createElement('iframe')"],
    [/setAttribute\(\s*['"]on[a-z]+['"]/, "setAttribute('on*')"],
];
for (const [name, source] of Object.entries(stripped)) {
    const hits = DANGEROUS.filter(([pattern]) => pattern.test(source)).map(([, label]) => label);
    check(`${name} 不含 eval / new Function / insertAdjacentHTML / outerHTML / document.write 等入口`,
        hits.length === 0, hits.join(', '));
}

// ---------- ② 非空 innerHTML 必须走 richToHtml ----------
{
    const offenders = [];
    const pattern = /\.innerHTML\s*=\s*([^;]+);/g;
    let match;
    while ((match = pattern.exec(stripped['js/app.js'])) !== null) {
        const rhs = match[1].trim();
        if (rhs === "''" || rhs === '""' || rhs === '``') continue;   // 清空，安全
        if (/^richToHtml\(/.test(rhs)) continue;
        if (/\?\s*richToHtml\([^)]*\)\s*:\s*(''|"")$/.test(rhs)) continue;
        offenders.push(rhs.slice(0, 80));
    }
    check('js/app.js 里所有非空 innerHTML 都经过 richToHtml（整段先转义）',
        offenders.length === 0, offenders.join(' | '));
}

// ---------- ③ richToHtml 的转义顺序不能被绕过 ----------
{
    const source = stripped['js/app.js'];
    const at = source.indexOf('function richToHtml(');
    const body = at < 0 ? '' : source.slice(at, at + 400);
    check('richToHtml 第一步就是整体转义',
        /var esc = escapeHtmlText\(source\);/.test(body), body.slice(0, 120));
    check('布局只使用转义后的文本切片（esc / code / lang）',
        source.includes('var rest = esc;') && source.includes('var code = rest.slice(cursor, close);')
        && source.includes("html += '<span class=\"rich-lang\">' + lang + '</span>'"));
}

// ---------- ④ 页面与响应头 ----------
{
    const html = read('index.html');
    const inlineScript = html.replace(/<script[^>]*src=[^>]*><\/script>/g, '')
        .match(/<script(?![^>]*\bsrc=)[^>]*>/g) || [];
    check('index.html 没有内联 <script>', inlineScript.length === 0, inlineScript.join(' '));
    const inlineHandler = html.match(/\son[a-z]+\s*=\s*["']/g) || [];
    check('index.html 没有内联 on* 事件属性', inlineHandler.length === 0, inlineHandler.join(' '));

    const server = read('local_server.py');
    const csp = (server.match(/Content-Security-Policy",\s*\n?\s*"([^"]+)"/) || [])[1] || '';
    check('CSP 禁止内联脚本并锁死来源',
        csp.includes("script-src 'self'") && csp.includes("object-src 'none'")
        && csp.includes("frame-ancestors 'none'") && !csp.includes('unsafe-inline'), csp);
    check('链接 URL 只允许 http/https（javascript: 在写入侧就被拒）',
        server.includes('Content-Security-Policy') && storageAllowsOnlyHttp());
}

function storageAllowsOnlyHttp() {
    const storage = read('storage.py');
    return /if not \(url\.startswith\("http:\/\/"\) or url\.startswith\("https:\/\/"\)\)/.test(storage)
        && storage.includes('raise ValueError("链接必须以 http:// 或 https:// 开头');
}

const failed = results.filter(ok => !ok).length;
if (failed) {
    console.error(`${failed} 项断言失败`);
    process.exit(1);
}
console.log('XSS 面：全部通过');
