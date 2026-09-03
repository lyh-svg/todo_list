(function(root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    if (root) root.TodoStudyTools = api;
})(typeof window !== 'undefined' ? window : globalThis, function() {
    'use strict';

    function collectTaskEntries(tree, includeOptional = false) {
        const entries = [];
        function walk(nodes, ancestors, labels) {
            for (const node of nodes || []) {
                if (!node || typeof node !== 'object') continue;
                if (node.type === 'item') {
                    if (!node.completed && (includeOptional || !node.optional)) {
                        entries.push({
                            id: node.id,
                            text: String(node.text || '未命名任务'),
                            optional: Boolean(node.optional),
                            ancestorIds: ancestors.map(parent => parent.id),
                            path: labels.join(' / ')
                        });
                    }
                    continue;
                }
                walk(node.children, [...ancestors, node], [...labels, String(node.text || '')]);
            }
        }
        walk(tree, [], []);
        return entries;
    }

    function chooseRandomTask(entries, random = Math.random) {
        if (!Array.isArray(entries) || entries.length === 0) return null;
        const value = Number(random());
        const index = Math.min(entries.length - 1, Math.max(0, Math.floor((Number.isFinite(value) ? value : 0) * entries.length)));
        return entries[index];
    }

    function getIsoWeek(date) {
        const utc = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
        const day = utc.getUTCDay() || 7;
        utc.setUTCDate(utc.getUTCDate() + 4 - day);
        const yearStart = new Date(Date.UTC(utc.getUTCFullYear(), 0, 1));
        return {
            year: utc.getUTCFullYear(),
            week: Math.ceil((((utc - yearStart) / 86400000) + 1) / 7)
        };
    }

    function calculateProgressStats(tree) {
        const stats = {
            total: 0,
            completed: 0,
            completionRate: 0,
            mainTotal: 0,
            mainCompleted: 0,
            optionalTotal: 0,
            optionalCompleted: 0,
            busiestWeek: null,
            latestCompletion: null
        };
        const weeks = new Map();
        function walk(nodes) {
            for (const node of nodes || []) {
                if (!node || typeof node !== 'object') continue;
                if (node.type === 'item') {
                    stats.total += 1;
                    if (node.optional) stats.optionalTotal += 1;
                    else stats.mainTotal += 1;
                    if (node.completed) {
                        stats.completed += 1;
                        if (node.optional) stats.optionalCompleted += 1;
                        else stats.mainCompleted += 1;
                        const completedDate = node.completedAt ? new Date(node.completedAt) : null;
                        if (completedDate && !Number.isNaN(completedDate.getTime())) {
                            const iso = getIsoWeek(completedDate);
                            const key = `${iso.year}-${String(iso.week).padStart(2, '0')}`;
                            weeks.set(key, { year: iso.year, week: iso.week, count: (weeks.get(key)?.count || 0) + 1 });
                            if (!stats.latestCompletion || completedDate > stats.latestCompletion.date) {
                                stats.latestCompletion = {
                                    id: node.id,
                                    text: String(node.text || '未命名任务'),
                                    completedAt: node.completedAt,
                                    date: completedDate
                                };
                            }
                        }
                    }
                }
                walk(node.children);
            }
        }
        walk(tree);
        stats.completionRate = stats.total > 0 ? Math.round((stats.completed / stats.total) * 100) : 0;
        const orderedWeeks = [...weeks.values()].sort((left, right) => right.count - left.count
            || right.year - left.year || right.week - left.week);
        stats.busiestWeek = orderedWeeks[0] || null;
        if (stats.latestCompletion) delete stats.latestCompletion.date;
        return stats;
    }

    return { collectTaskEntries, chooseRandomTask, calculateProgressStats, getIsoWeek };
});