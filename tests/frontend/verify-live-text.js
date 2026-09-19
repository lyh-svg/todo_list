// P12 验证：直播文本追加文本节点（不再重写 textContent），滚动用 rAF 节流。
//
// 旧写法 `assessmentLiveBody.textContent += token` 每来一个 token 都要把整段文本重新写一遍
// （浏览器得重建文本节点、重新布局），并且每次都同步读 scrollHeight / 写 scrollTop（强制布局）。
// 这里用可计数的 DOM 桩断言："textContent 一次都没被赋值、追加了 N 个文本节点、滚动只发生一帧一次"。
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

function buildWorld() {
    const stats = { textContentSets: 0, textContentChars: 0, scrollTopSets: 0, frames: 0 };
    let body = null;
    const rafQueue = [];
    const makeEl = () => {
        let scrollTop = 0;
        const el = {
            _children: [], scrollHeight: 1234, _text: '',
            get scrollTop() { return scrollTop; },
            set scrollTop(value) { stats.scrollTopSets += 1; scrollTop = value; },
            get textContent() { return this._text; },
            set textContent(value) {
                stats.textContentSets += 1;
                stats.textContentChars += String(value || '').length;
                this._text = String(value || '');
                this._children = [];
            },
            appendChild(child) { this._children.push(child); this._text += child.textContent; return child; },
            get childNodes() { return this._children; },
        };
        return el;
    };
    body = makeEl();
    const documentStub = { createTextNode: text => ({ textContent: String(text), _isText: true }) };
    const windowStub = {
        requestAnimationFrame: callback => { stats.frames += 1; rafQueue.push(callback); return rafQueue.length; },
    };
    const deps = { document: documentStub, window: windowStub, assessmentLiveBody: body, stats };
    const prelude = `
        const { document, window, assessmentLiveBody, stats } = deps;
        let liveScrollFrame = null;
    `;
    const bodySource = `
        ${extract('appendAssessmentLiveText')}
        ${extract('scheduleLiveScroll')}
        return { appendAssessmentLiveText, scheduleLiveScroll };
    `;
    const factory = new Function('deps', `${prelude}\n${bodySource}`);
    return { api: factory(deps), body, stats, rafQueue };
}

const run = () => {
    // ---------- 静态接线 ----------
    check('静态：不再有 textContent += 的直播写法',
        !/assessmentLiveBody\.textContent\s*\+=/.test(src));
    check('静态：直播追加走 appendAssessmentLiveText',
        /appendAssessmentLiveText\(token\)/.test(src) && /function appendAssessmentLiveText\(token\)/.test(src)
        && /assessmentLiveBody\.appendChild\(document\.createTextNode\(token\)\)/.test(src));
    check('静态：滚动用 rAF 节流，不再每个 token 同步滚动',
        /function scheduleLiveScroll\(\)/.test(src)
        && /requestAnimationFrame\(\(\) => \{[\s\S]{0,200}assessmentLiveBody\.scrollTop = assessmentLiveBody\.scrollHeight;/.test(src)
        && !/assessmentLiveBody\.scrollTop = assessmentLiveBody\.scrollHeight;[\s\S]{0,80}appendAssessmentLiveText/.test(src));
    check('静态：整段清空仍然可用（textContent = ""）', /assessmentLiveBody\.textContent = ''/.test(src));

    // ---------- 行为：追加而不是重写 ----------
    const world = buildWorld();
    const tokens = [];
    for (let index = 0; index < 200; index += 1) {
        const token = `词${index} `;
        tokens.push(token);
        world.api.appendAssessmentLiveText(token);
    }
    check('行为：追加 200 个 token 时 textContent 一次都没被赋值',
        world.stats.textContentSets === 0, String(world.stats.textContentSets));
    check('行为：产生了 200 个文本节点', world.body.childNodes.length === 200,
        String(world.body.childNodes.length));
    check('行为：拼出来的正文与 token 串一致', world.body.textContent === tokens.join(''),
        `${world.body.textContent.length} 字符`);

    // ---------- 行为：滚动一帧一次 ----------
    for (let index = 0; index < 50; index += 1) world.api.scheduleLiveScroll();
    check('行为：50 次滚动请求只排了 1 帧', world.stats.frames === 1, String(world.stats.frames));
    check('行为：帧还没跑之前不写 scrollTop', world.stats.scrollTopSets === 0);
    const queued = world.rafQueue.splice(0);
    queued.forEach(callback => callback());
    check('行为：帧执行时写一次 scrollTop 并滚到底', world.stats.scrollTopSets === 1,
        String(world.stats.scrollTopSets));
    world.api.scheduleLiveScroll();
    check('行为：下一批请求会重新排一帧', world.stats.frames === 2, String(world.stats.frames));

    // 空 token / 正文字段缺失时不应该炸
    const empty = buildWorld();
    empty.api.appendAssessmentLiveText('');
    empty.api.appendAssessmentLiveText(null);
    check('行为：空 token 不产生节点', empty.body.childNodes.length === 0 && empty.stats.textContentSets === 0);

    const failed = results.filter(result => !result).length;
    console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
    process.exit(failed ? 1 : 0);
};

run();
