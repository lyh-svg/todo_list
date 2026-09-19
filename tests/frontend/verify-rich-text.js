// B7 验证：代码块语言标签只转义一次（不再把 &、' 变成 &amp;amp;、&amp;#39;）。
//
// richToHtml 先对整段文本做一次 escapeHtmlText，再按 ``` 切出语言标签；旧代码对切出来的
// lang 又 escape 了一次——lang 取自已经转义过的文本，于是 "c&" 显示成 "c&amp;"、"it's"
// 显示成 "it&#39;s"。后者是纯外观问题，但 AI 回复里的 c++、c& 这类语言名会直接露馅。
//
// 这里从 js/app.js 抽出真实函数跑：断言语言标签是"单次转义"、正文也只转义一次，
// 并且转义后的标签仍然不可能注入标签（lang 取自 esc，本身已经安全）。
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..', '..');
const src = fs.readFileSync(path.join(ROOT, 'js', 'app.js'), 'utf8');

function extract(name) {
    let at = src.indexOf(`    async function ${name}(`);
    if (at < 0) at = src.indexOf(`    function ${name}(`);
    if (at < 0) throw new Error('找不到 ' + name);
    let depth = 0, seen = false;
    for (let i = at; i < src.length; i++) {
        if (src[i] === '{') { depth++; seen = true; }
        else if (src[i] === '}') { depth--; if (seen && depth === 0) return src.slice(at, i + 1); }
    }
    throw new Error(name + ' 括号不配对');
}

const results = [];
function check(name, ok, detail = '') {
    results.push(Boolean(ok));
    console.log(`${ok ? '   ✔' : '   ✘'} ${name}${ok ? '' : `  [${detail}]`}`);
}

const escapeHtmlText = new Function(`${extract('escapeHtmlText')} return escapeHtmlText;`)();
const fmtInline = new Function(`${extract('fmtInline')} return fmtInline;`)();
const fmtBold = new Function('fmtInline', `${extract('fmtBold')} return fmtBold;`)(fmtInline);
const richToHtml = new Function('escapeHtmlText', 'fmtBold',
    `${extract('richToHtml')} return richToHtml;`)(escapeHtmlText, fmtBold);

function lang(html) {
    const match = html.match(/<span class="rich-lang">([\s\S]*?)<\/span>/);
    return match ? match[1] : null;
}

const nl = String.fromCharCode(10);
const fence = (info, body) => '```' + info + nl + body + nl + '```';

// ---------- 1. & 与 ' 只转义一次 ----------
const amp = richToHtml(fence('c&', 'int x = 1;'));
check('语言名含 & 只转义一次（c& → c&amp;，不是 c&amp;amp;）',
    lang(amp) === 'c&amp;', JSON.stringify(lang(amp)));
check('语言名里的 & 没有被二次转义',
    !amp.includes('&amp;amp;') && !amp.includes('&amp;#39;'), JSON.stringify(lang(amp)));

const quote = richToHtml(fence("it's", 'x'));
check("语言名含 ' 只转义一次（it's → it&#39;s）",
    lang(quote) === 'it&#39;s', JSON.stringify(lang(quote)));

const plus = richToHtml(fence('c++ <fast>', 'x'));
check('c++ / 尖括号语言名按单次转义显示',
    lang(plus) === 'c++ &lt;fast&gt;', JSON.stringify(lang(plus)));
check('尖括号没有被二次转义', !plus.includes('&amp;lt;'), JSON.stringify(lang(plus)));

// ---------- 2. 安全：语言标签仍然不可能注入 ----------
const evil = richToHtml(fence('"><img src=x onerror=alert(1)>', 'code'));
check('恶意语言名不会留下真实标签',
    !evil.includes('<img') && lang(evil) !== null && !lang(evil).includes('<'),
    JSON.stringify(lang(evil)));

// ---------- 3. 正文与加粗：口径不变 ----------
const body = richToHtml(fence('js', 'if (a < b) { x &= 1; }'));
check('代码正文仍然只转义一次',
    body.includes('a &lt; b') && body.includes('x &amp;= 1') && !body.includes('&amp;lt;'),
    JSON.stringify(body));
check('代码块结构不变', body.includes('<pre class="rich-code"><code>'), JSON.stringify(body));

const nolang = richToHtml(fence('', 'plain'));
check('没有语言标签时不生成 rich-lang', lang(nolang) === null && nolang.includes('<code>'),
    JSON.stringify(nolang));

const bold = richToHtml('**粗**');
check('加粗仍然生效', bold.includes('<strong>粗</strong>'), JSON.stringify(bold));

const failed = results.filter(ok => !ok).length;
if (failed) {
    console.error(`${failed} 项断言失败`);
    process.exit(1);
}
console.log('语言标签转义：全部通过');
