// P3 验证：提醒轮询的"数据没变就短路"（since/unchanged）与"切到后台暂停"。
//
// 这里既做源码接线断言，也用真实抽取出来的 checkReminders / startReminders 跑行为：
// 假 apiFetch + 假 document.hidden + 假 window.setInterval，断言的是"发了几次请求、
// 请求里带没带 since、隐藏时到底有没有轮询、unchanged 会不会误弹提醒"。
const fs = require('fs');
const ROOT = require('path').resolve(__dirname, '..', '..');
const src = fs.readFileSync(ROOT + '/js/app.js', 'utf8');

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

const TODAY = '2026-09-15';

function build({ hidden, responses }) {
    const calls = { urls: [], toasts: [], interval: null, timeout: null };
    const state = { enabled: true, timer: null, fired: new Set(), permission: 'default', version: '' };
    const doc = { hidden };
    const win = {
        setInterval: (fn, ms) => { calls.interval = { fn, ms }; return 1; },
        setTimeout: (fn, ms) => { calls.timeout = { fn, ms }; return 2; },
        clearInterval: () => { calls.interval = null; },
    };
    let index = 0;
    const apiFetch = (url) => {
        calls.urls.push(url);
        const body = responses[Math.min(index, responses.length - 1)];
        index += 1;
        return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
    };
    const factory = new Function(
        'reminderState', 'document', 'window', 'apiFetch', 'todayStr', 'showToast',
        'Notification', 'saveReminderSettings',
        `${extract('checkReminders')}\n${extract('startReminders')}\nreturn { checkReminders, startReminders };`,
    );
    const api = factory(state, doc, win, apiFetch, () => TODAY,
        text => calls.toasts.push(text), undefined, () => {});
    return { api, state, calls, doc };
}

async function run() {
    // ---------- 源码接线 ----------
    check('提醒：轮询请求带 since（服务端才能短路）',
        /checkReminders[\s\S]{0,400}since=\$\{encodeURIComponent\(reminderState\.version\)\}/.test(src));
    check('提醒：整个 app.js 只有提醒这一处传 since',
        (src.match(/since=/g) || []).length === 1, String((src.match(/since=/g) || []).length));
    check('提醒：响应里的 version 会存下来', /if \(board\.version\) reminderState\.version = board\.version;/.test(src));
    check('提醒：unchanged 直接返回、不看分组', /if \(board\.unchanged\) return;/.test(src));
    check('提醒：隐藏时不轮询（checkReminders 早退）',
        /async function checkReminders\(\) \{\s*\r?\n\s*if \(!reminderState\.enabled \|\| document\.hidden\) return;/.test(src));
    check('提醒：隐藏时不启动定时器', /function startReminders\(immediate = false\) \{[\s\S]{0,200}if \(document\.hidden\) return;/.test(src));
    check('提醒：visibilitychange 切后台时停止轮询',
        /document\.addEventListener\('visibilitychange'[\s\S]{0,400}stopReminders\(\)/.test(src));
    check('提醒：visibilitychange 回前台时立刻补一次',
        /document\.addEventListener\('visibilitychange'[\s\S]{0,600}if \(reminderState\.enabled\) startReminders\(true\);/.test(src));

    // ---------- 行为：首次轮询 / 第二次带 since / unchanged 不误弹 ----------
    const first = build({
        hidden: false,
        responses: [
            { version: 'v1', groups: { today: [{ projectId: 'p', nodeId: 'n1', text: 'A' }] } },
            { version: 'v1', unchanged: true, groups: { today: [{ projectId: 'p', nodeId: 'n2', text: 'B' }] } },
        ],
    });
    await first.api.checkReminders();
    check('行为：第一次轮询不带 since', !first.calls.urls[0].includes('since='), first.calls.urls[0]);
    check('行为：第一次轮询带 today', first.calls.urls[0].includes('today=' + TODAY), first.calls.urls[0]);
    check('行为：第一次轮询后记住 version', first.state.version === 'v1', first.state.version);
    check('行为：今天到期的任务会提醒', first.calls.toasts.length === 1, JSON.stringify(first.calls.toasts));
    check('行为：这次能弹提醒的话术带任务名', first.calls.toasts[0].includes('A'), first.calls.toasts[0]);

    await first.api.checkReminders();
    check('行为：第二次轮询带上 since=v1', first.calls.urls[1].includes('since=v1'), first.calls.urls[1]);
    check('行为：unchanged 时即使分组里有新任务也不提醒（走短路）',
        first.calls.toasts.length === 1, JSON.stringify(first.calls.toasts));

    // 服务端说变了：分组长出新任务 → 应该弹
    const changed = build({
        hidden: false,
        responses: [
            { version: 'v1', groups: { today: [] } },
            { version: 'v2', groups: { today: [{ projectId: 'p', nodeId: 'n9', text: '变了' }] } },
        ],
    });
    await changed.api.checkReminders();
    await changed.api.checkReminders();
    check('行为：数据变了（没有 unchanged）时正常提醒',
        changed.calls.toasts.length === 1 && changed.calls.toasts[0].includes('变了'),
        JSON.stringify(changed.calls.toasts));
    check('行为：version 跟着更新到 v2', changed.state.version === 'v2', changed.state.version);

    // ---------- 行为：后台不轮询 ----------
    const hidden = build({ hidden: true, responses: [{ version: 'v1', groups: { today: [] } }] });
    await hidden.api.checkReminders();
    check('行为：页面隐藏时 checkReminders 不发请求', hidden.calls.urls.length === 0, String(hidden.calls.urls.length));
    hidden.api.startReminders();
    check('行为：页面隐藏时 startReminders 不建定时器', hidden.calls.interval === null);

    // ---------- 行为：可见时的启动语义 ----------
    const visible = build({ hidden: false, responses: [{ version: 'v1', groups: { today: [] } }] });
    visible.api.startReminders();
    check('行为：每 60 秒轮询一次', Boolean(visible.calls.interval) && visible.calls.interval.ms === 60000);
    check('行为：首次开启仍走 3 秒预热（原有语义不变）',
        Boolean(visible.calls.timeout) && visible.calls.timeout.ms === 3000 && visible.calls.urls.length === 0);

    const resumed = build({ hidden: false, responses: [{ version: 'v1', groups: { today: [] } }] });
    resumed.api.startReminders(true);
    check('行为：回到前台立刻补一次（不等 3 秒）',
        resumed.calls.urls.length === 1 && resumed.calls.timeout === null,
        `${resumed.calls.urls.length} / ${JSON.stringify(resumed.calls.timeout)}`);
    check('行为：补完这一次之后定时器仍在', Boolean(resumed.calls.interval) && resumed.calls.interval.ms === 60000);
}

run().then(() => {
    const failed = results.filter(r => !r).length;
    console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
    process.exit(failed ? 1 : 0);
}).catch(error => {
    console.error(error);
    process.exit(1);
});
