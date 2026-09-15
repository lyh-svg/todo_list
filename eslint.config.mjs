// ESLint 扁平配置：只启用"能抓到真 bug"的规则（不追求风格统一，避免噪声淹没信号）。
// 重点规则是 no-undef —— 本会话踩过的"DOM 引用没声明"就是这个规则能抓的（Python 侧也有对应静态测试）。
import globals from "globals";

const rules = {
    "no-undef": "error",
    "no-redeclare": "error",
    "no-dupe-keys": "error",
    "no-dupe-args": "error",
    "no-dupe-else-if": "error",
    "no-unreachable": "error",
    "no-func-assign": "error",
    "no-obj-calls": "error",
    "no-sparse-arrays": "error",
    "no-cond-assign": ["error", "except-parens"],
    "no-self-assign": "error",
    "no-self-compare": "error",
    "no-fallthrough": "error",
    "no-unsafe-negation": "error",
    "no-constant-binary-expression": "error",
    "no-async-promise-executor": "error",
    "use-isnan": "error",
    "valid-typeof": "error",
};

export default [
    {
        ignores: ["node_modules/**", "todo_venv/**", "data/**", "**/*.min.js"],
    },
    {
        files: ["js/**/*.js"],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: "script",
            // study-tools.js 是 UMD：在 typeof module === 'object' 保护下引用 module.exports
            globals: { ...globals.browser, module: "readonly" },
        },
        rules,
    },
    {
        // 前端验证脚本是 CommonJS（Node 里跑），用 Node 全局变量
        files: ["tests/frontend/**/*.js"],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: "commonjs",
            globals: { ...globals.node },
        },
        rules,
    },
    {
        files: ["eslint.config.mjs"],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: "module",
            globals: { ...globals.node },
        },
        rules,
    },
];
