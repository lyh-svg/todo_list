// P6 验证：勾选/复习操作之后只刷复习计数徽标，不再整卡重绘、不再拉全项目摘要。
//
// 用真实抽出来的 loadReviewCounts / reviewBadgeText / updateReviewBadges + 最小 DOM 桩，
// 断言：① 请求打到 /api/review/counts；② 卡片元素**没有被重建**（同一批对象）；
// ③ 徽标按新计数原地增加/更新/移除；④ renderProjects 一次都没被调用。
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

function makeEl(tag = 'div') {
    const el = {
        tagName: String(tag).toUpperCase(), _children: [], _parentElement: null, dataset: {}, style: {},
        textContent: '', className: '', 
        classList: {
            _s: new Set(),
            add(...names) { names.forEach(n => this._s.add(n)); },
            remove(...names) { names.forEach(n => this._s.delete(n)); },
            toggle(name, force) {
                const on = force === undefined ? !this._s.has(name) : Boolean(force);
                if (on) this._s.add(name); else this._s.delete(name);
                return on;
            },
            contains(name) { return this._s.has(name); },
        },
        appendChild(child) { if (child) { child._parentElement = this; this._children.push(child); } return child; },
        append(...children) { children.forEach(c => this.appendChild(c)); },
        remove() {
            if (this._parentElement) {
                this._parentElement._children = this._parentElement._children.filter(c => c !== this);
            }
        },
        querySelector(selector) {
            return findAll(this, el => matches(el, selector))[0] || null;
        },
        querySelectorAll(selector) { return findAll(this, el => matches(el, selector)); },
        get children() { return this._children; },
    };
    Object.defineProperty(el, 'className', {
        get() { return [...el.classList._s].join(' '); },
        set(value) { el.classList._s = new Set(String(value || '').split(/\s+/).filter(Boolean)); },
    });
    return el;
}

function findAll(root, predicate, out = []) {
    (root._children || []).forEach(child => {
        if (predicate(child)) out.push(child);
        findAll(child, predicate, out);
    });
    return out;
}

function matches(el, selector) {
    const classOnly = /^\.([\w-]+)$/.exec(String(selector || '').trim());
    return classOnly ? el.classList.contains(classOnly[1]) : false;
}

function makeCard(projectId, withBadge) {
    const card = makeEl('div');
    card.classList.add('project-card');
    card.dataset.id = projectId;
    const meta = makeEl('div');
    meta.classList.add('card-meta');
    if (withBadge) {
        const badge = makeEl('span');
        badge.classList.add('review-card-badge');
        badge.textContent = '待复习 9';
        meta.appendChild(badge);
    }
    card.appendChild(meta);
    return card;
}

function buildWorld({ cards, response }) {
    const calls = { urls: [], renderProjects: 0, toasts: [], preview: 0 };
    const documentStub = { createElement: tag => makeEl(tag) };
    const projectGrid = makeEl('div');
    cards.forEach(card => projectGrid.appendChild(card));
    const reviewQueueCount = makeEl('span');
    const reviewQueueBtn = makeEl('button');
    const state = { reviewCounts: { byProject: new Map(), today: 0, overdue: 0 }, timezoneWarned: false };
    const projectsView = makeEl('div');
    projectsView.classList.add('active');
    const deps = {
        document: documentStub, projectGrid, reviewQueueCount, reviewQueueBtn, state, projectsView,
        // 旧实现（修复前）用 readStoredState 拉全量摘要；新实现不再引用，留着只为让
        // "跑在旧代码上"能走到断言，并能在断言里看见它到底请求了哪个接口。
        readStoredState: () => {
            calls.urls.push('/api/projects?today=2026-09-19');
            return Promise.resolve({ projects: [], reviewTotals: { today: 0, overdue: 0 },
                                     serverToday: '2026-09-19' });
        },
        todayStr: () => '2026-09-19',
        showToast: message => calls.toasts.push(String(message)),
        renderProjects: () => { calls.renderProjects += 1; },
        // 首页「今天要复习」预览：刷新计数时顺带刷新，这里只数调用次数
        loadTodayPreview: () => { calls.preview += 1; },
        apiFetch: url => {
            calls.urls.push(String(url));
            if (!response) return Promise.reject(new Error('服务不可用'));
            return Promise.resolve({ ok: true, json: () => Promise.resolve(response), status: 200 });
        },
    };
    const prelude = `
        const { document, projectGrid, reviewQueueCount, reviewQueueBtn, state, todayStr, showToast,
                renderProjects, apiFetch, projectsView, readStoredState, loadTodayPreview } = deps;
        let reviewCounts = state.reviewCounts;
        let timezoneWarned = state.timezoneWarned;
    `;
    // 函数不存在时退化成空桩，好让"改坏了"表现为断言失败而不是脚本崩溃
    const tolerant = name => {
        try {
            return extract(name);
        } catch (error) {
            return `    function ${name}() {}`;
        }
    };
    const body = [
        tolerant('reviewBadgeText'), tolerant('updateReviewBadges'),
        tolerant('readReviewCounts'), tolerant('loadReviewCounts'),
    ].join('\n');
    const factory = new Function('deps', `${prelude}\n${body}\n
        return { loadReviewCounts, updateReviewBadges, reviewBadgeText,
                 counts: () => reviewCounts,
                 setCounts: value => { reviewCounts = value; state.reviewCounts = value; } };`);
    return { api: factory(deps), calls, projectGrid, reviewQueueCount, reviewQueueBtn, cards };
}

async function run() {
    // ---------- 静态接线 ----------
    check('静态：loadReviewCounts 走轻量计数接口', /\/api\/review\/counts\?today=/.test(src));
    check('静态：loadReviewCounts 里不再调 renderProjects（改成刷新徽标）',
        /async function loadReviewCounts\(\)[\s\S]{0,1600}updateReviewBadges\(\)/.test(src)
        && !/async function loadReviewCounts\(\)[\s\S]{0,1600}renderProjects\(\)/.test(src));
    check('静态：不再为了计数拉全项目摘要',
        !/async function loadReviewCounts\(\)[\s\S]{0,900}readStoredState\(\)/.test(src));
    check('静态：徽标文案只有一处定义（renderProjects 也用同一个函数）',
        (src.match(/function reviewBadgeText\(/g) || []).length === 1
        && /reviewBadgeText\(projectCounts\)/.test(src));

    // ---------- 行为：徽标原地更新，不重建卡片 ----------
    const cardA = makeCard('p1', false);
    const cardB = makeCard('p2', false);
    const cardC = makeCard('p3', true);      // 之前有徽标，这次计数归零 → 应移除
    const world = buildWorld({
        cards: [cardA, cardB, cardC],
        response: {
            byProject: { p1: { today: 2, overdue: 1 }, p3: { today: 0, overdue: 0 } },
            totals: { today: 2, overdue: 1 },
            serverToday: '2026-09-19',
            usedToday: '2026-09-19',
        },
    });
    const gridChildrenBefore = [...world.projectGrid.children];
    await world.api.loadReviewCounts();

    check('行为：请求打到 /api/review/counts（带本机日期）',
        world.calls.urls.length === 1 && world.calls.urls[0].startsWith('/api/review/counts?today=2026-09-19'),
        JSON.stringify(world.calls.urls));
    check('行为：不再调用 renderProjects（不整卡重绘）',
        world.calls.renderProjects === 0, String(world.calls.renderProjects));
    check('行为：卡片元素是同一批对象（没有被重建）',
        world.projectGrid.children.length === gridChildrenBefore.length
        && world.projectGrid.children.every((child, index) => child === gridChildrenBefore[index]));

    const badgeA = cardA.querySelector('.review-card-badge');
    check('行为：拿到计数的卡片原地长出徽标，文案与样式正确',
        Boolean(badgeA) && badgeA.textContent === '待复习 2　逾期 1' && badgeA.classList.contains('overdue'),
        badgeA ? badgeA.textContent : '(没有徽标)');
    check('行为：没有计数的卡片不加徽标',
        cardB.querySelector('.review-card-badge') === null);
    check('行为：计数归零的卡片把旧徽标移除',
        cardC.querySelector('.review-card-badge') === null);
    check('行为：顶栏计数同步', world.reviewQueueCount.textContent === '3',
        world.reviewQueueCount.textContent);
    check('行为：刷新计数时顺带刷新首页今日预览', world.calls.preview === 1, String(world.calls.preview));
    // 计数全为 0：顶栏归零并置 empty
    const zeroWorld = buildWorld({
        cards: [makeCard('p1', false)],
        response: { byProject: {}, totals: { today: 0, overdue: 0 }, serverToday: '2026-09-19', usedToday: '2026-09-19' },
    });
    await zeroWorld.api.loadReviewCounts();
    check('行为：计数为 0 时顶栏显示 0 并置 empty',
        zeroWorld.reviewQueueCount.textContent === '0' && zeroWorld.reviewQueueBtn.classList.contains('empty'),
        `${zeroWorld.reviewQueueCount.textContent} / ${zeroWorld.reviewQueueBtn.className}`);

    // 接口失败：保留旧计数、只打日志，不抛也不清空徽标
    const failing = buildWorld({ cards: [makeCard('p1', false)], response: null });
    failing.api.setCounts({ byProject: new Map([['p1', { today: 5, overdue: 0 }]]), today: 5, overdue: 0 });
    await failing.api.loadReviewCounts();
    check('行为：接口失败时保留旧计数并照常刷徽标（不抛异常）',
        failing.api.counts().today === 5
        && Boolean(failing.cards[0].querySelector('.review-card-badge'))
        && failing.cards[0].querySelector('.review-card-badge').textContent === '待复习 5',
        failing.cards[0].querySelector('.review-card-badge')
            ? failing.cards[0].querySelector('.review-card-badge').textContent : '(没有徽标)');
}

run().then(() => {
    const failed = results.filter(result => !result).length;
    console.log(`\n   通过 ${results.length - failed} 项，失败 ${failed} 项`);
    process.exit(failed ? 1 : 0);
}).catch(error => {
    console.error(error);
    process.exit(1);
});
