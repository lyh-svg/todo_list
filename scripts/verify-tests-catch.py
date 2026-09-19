#!/usr/bin/env python3
"""证明"测试真的有牙"：故意把产品代码改坏，确认对应测试立刻失败，然后原样还原。

只读语义的检查（例如"源码里有没有某个字符串"）很容易写成永远为真的空转断言；
这个脚本对每条关键修复做一次反向验证：把修复点改回旧行为 → 跑对应测试 → 必须失败。
任何一条"改坏了测试还是通过"就说明那条测试不可信，脚本以非 0 退出。

用法：
    python3 scripts/verify-tests-catch.py            # 全部
    python3 scripts/verify-tests-catch.py --list     # 只列出用例

注意：脚本会临时改写工作区文件，运行结束（包括异常/中断）会从内存快照还原；
     所以请确保运行前工作区是干净的（有未提交改动也没关系，还原用的是它当时的内容）。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent


def crlf(text: str) -> str:
    """多行模式统一用 CRLF（仓库里代码文件都是 CRLF）。"""
    return text.replace("\n", "\r\n")


# (说明, 文件, 旧代码, 改坏成, 期望失败的测试命令)
CASES: list[tuple[str, str, str, str, list[str]]] = [
    (
        "AI 流式文本：分块边界落在反斜杠之后要回退一格",
        "ai_service.py",
        crlf("                            self.i -= 1\n                            break\n"),
        crlf("                            pass\n"),
        [sys.executable, "-m", "unittest",
         "tests.test_ai_service.ReplyScannerTests.test_escapes_are_decoded"],
    ),
    (
        "AI 读超时/连接中断要变成可读错误",
        "ai_service.py",
        crlf('    except (TimeoutError, OSError) as error:\n'
             '        # 连接建立之后的读超时/连接中断不是 URLError，原样冒出去会变成"未预期错误"。\n'
             '        raise RuntimeError("DeepSeek API 连接中断或超时: %s" % error) from None\n'),
        "",
        [sys.executable, "-m", "unittest",
         "tests.test_ai_service.StreamParsingTests.test_midstream_timeout_becomes_readable_error"],
    ),
    (
        "项目摘要必须以 live 列为准（旧 summary_json 也要带 archived）",
        "storage.py",
        crlf('        summary["archived"] = bool(row["archived"])\n'),
        "",
        [sys.executable, "-m", "unittest",
         "tests.test_views_batch_archive.ArchiveTests.test_summary_reports_live_columns_even_if_json_is_stale"],
    ),
    (
        "工作台收集箱分组不能和日期分组重复统计",
        "storage.py",
        "            if project_id == INBOX_PROJECT_ID and not bucketed:",
        "            if project_id == INBOX_PROJECT_ID:",
        [sys.executable, "-m", "unittest",
         "tests.test_workbench_inbox.WorkbenchTests.test_inbox_items_are_not_counted_twice"],
    ),
    (
        "周期任务的克隆不能带上 children（否则节点 ID 重复）",
        "storage.py",
        crlf('        # 不能连 children 一起深拷贝：子节点 id 会重复，_flatten_nodes 会抛\n'
             '        # "节点 ID 重复" 让整批事务回滚。周期任务的下一次只复制任务本身。\n'
             '        clone["children"] = []\n'),
        "",
        [sys.executable, "-m", "unittest",
         "tests.test_repeat_tasks.RepeatStorageTests.test_spawn_drops_children_to_avoid_duplicate_ids"],
    ),
    (
        "缺少 questionConversations 键时不能删掉验收逐题对话",
        "storage.py",
        crlf("    if not conversations_present:\n"
             "        # 只有 payload 真的带了 questionConversations 键时才做差集删除。\n"
             '        # 否则（例如客户端只发 {"passed": true}）valid_keys 为空，会把该节点已有的逐题对话全部删掉。\n'
             "        return\n"),
        crlf("    if not conversations_present:\n"
             "        # 只有 payload 真的带了 questionConversations 键时才做差集删除。\n"
             '        # 否则（例如客户端只发 {"passed": true}）valid_keys 为空，会把该节点已有的逐题对话全部删掉。\n'
             "        pass\n"),
        [sys.executable, "-m", "unittest",
         "tests.test_node_patch.NodePatchTests."
         "test_assessment_update_without_conversations_key_keeps_them"],
    ),
    (
        "隐藏的恢复临时文件不能被当成备份恢复",
        "backup_service.py",
        '    if Path(text).name != text or text.startswith(".") or not text.endswith(suffix):',
        "    if Path(text).name != text or not text.endswith(suffix):",
        [sys.executable, "-m", "unittest",
         "tests.test_full_backup.FullBackupTests.test_hidden_temp_files_cannot_be_used_as_backups"],
    ),
    (
        "weekly.weekday 必须按 JS getDay() 解释（0=周日）",
        "storage.py",
        "        while (candidate.weekday() + 1) % 7 != target:",
        "        while candidate.weekday() != target:",
        [sys.executable, "-m", "unittest",
         "tests.test_repeat_tasks.RepeatRuleMathTests.test_weekly_targets_weekday"],
    ),
    (
        "视图切换必须覆盖全部视图（否则退不出去）",
        "js/app.js",
        "        [projectsView, detailView, reviewView, reviewSessionView, knowledgeView, workbenchView].forEach(view => {",
        "        [projectsView, detailView, reviewView].forEach(view => {",
        [sys.executable, "-m", "unittest",
         "tests.test_frontend_references.FrontendReferenceTests.test_view_switching_is_centralized"],
    ),
    (
        "元数据筛选条件要参与『正在筛选』判断",
        "js/app.js",
        "            || nodeFilters.priority !== 'all'",
        "            || false",
        ["node", "tests/frontend/verify-r8.js"],
    ),
    (
        "GET 也要校验请求来源",
        "local_server.py",
        '        if path.startswith("/api/") and not allowed_origin(self.headers.get("Origin")):',
        "        if False:",
        [sys.executable, "-m", "unittest",
         "tests.test_http_layer.HttpLayerTests.test_get_rejects_foreign_origin"],
    ),
    (
        "前端归一化必须保留 archived",
        "js/app.js",
        crlf("                // 保留归档标记：丢掉它以后任何一次保存都会把服务端的 archived=1 写成 0。\n"
             "                archived: Boolean(project.archived),\n"),
        "",
        ["node", "tests/frontend/verify-r8.js"],
    ),
    (
        "schema 缓存必须按 (inode, 版本) 失效（否则换文件后不再建表）",
        "storage.py",
        crlf("    with _schema_ready_lock:\n"
             "        return _schema_ready.get(str(path)) == (signature, version)\n"),
        crlf("    with _schema_ready_lock:\n"
             "        return True\n"),
        [sys.executable, "-m", "unittest",
         "tests.test_open_overhead.BootstrapCacheTests."
         "test_deleted_and_recreated_file_is_bootstrapped_again"],
    ),
    (
        "备份校验必须流式读（不能把整个库读进内存）",
        "backup_service.py",
        crlf("            actual, size = sha256_of_zip_member(archive, file_name)\n"),
        crlf("            _data = archive.read(file_name)\n"
             "            actual, size = hashlib.sha256(_data).hexdigest(), len(_data)\n"),
        [sys.executable, "-m", "unittest", "tests.test_backup_memory.BackupMemoryTests."
         "test_describe_backup_streams_checksum"],
    ),
    (
        "恢复暂存必须流式落盘（不能整个读成 bytes）",
        "backup_service.py",
        crlf("                    with archive.open(file_name) as source, staged.open(\"wb\") as target:\n"
             "                        shutil.copyfileobj(source, target, 1024 * 1024)\n"),
        crlf("                    staged.write_bytes(archive.read(file_name))\n"),
        [sys.executable, "-m", "unittest", "tests.test_backup_memory.BackupMemoryTests."
         "test_restore_stages_files_without_loading_them"],
    ),
    (
        "自动归档必须先用 SQL 筛完成度（不能逐个读树）",
        "storage.py",
        crlf("                if total == 0 or completed < total:\n"
             "                    continue\n"),
        crlf("                if False:\n"
             "                    continue\n"),
        [sys.executable, "-m", "unittest", "tests.test_import_export_templates."
         "AutoArchiveTests.test_auto_archive_only_reads_qualifying_projects"],
    ),
    (
        "回收站存在性校验必须走轻量查询（不能全量列一遍）",
        "local_server.py",
        crlf("                    if not trash_id or trash_id not in trash_item_ids([trash_id]):\n"),
        crlf('                    if not trash_id or not any(entry["id"] == trash_id for entry in list_trash_items()):\n'),
        [sys.executable, "-m", "unittest", "tests.test_trash_paths.TrashRouteTests."
         "test_unknown_id_is_404_without_listing"],
    ),
    (
        "被移除项目的节点数必须真的数出来（GROUP BY）",
        "storage.py",
        crlf('                    removed_node_counts[str(row["project_id"])] = int(row["nodes"])\n'),
        crlf('                    removed_node_counts[str(row["project_id"])] = 0\n'),
        [sys.executable, "-m", "unittest", "tests.test_import_preview_cost.ImportPreviewCostTests."
         "test_deleted_nodes_count_matches_project_contents"],
    ),
    (
        "导入预览的本地节点集合必须从库里读（差异统计才有意义）",
        "storage.py",
        crlf('                        f"SELECT project_id,node_id FROM nodes WHERE project_id IN ({placeholders})", chunk):\n'),
        crlf('                        f"SELECT project_id,node_id FROM nodes WHERE 1=0", chunk):\n'),
        [sys.executable, "-m", "unittest", "tests.test_import_preview_cost.ImportPreviewCostTests."
         "test_preview_still_counts_added_and_local_only_nodes"],
    ),
    (
        "队列题面必须一次批量查（不能退回逐条目回查）",
        "review_storage.py",
        crlf('            block = (content_by_code.get(str(item["code"])) or {}).get(kind) or {}\n'),
        crlf("            block: dict[str, Any] = {}\n"),
        [sys.executable, "-m", "unittest", "tests.test_review_queue_batch.QueueBatchingTests."
         "test_queue_fields_match_reference"],
    ),
    (
        "题型轮换必须批量查（不能每个知识点各查一次）",
        "review_storage.py",
        crlf("                         else _question_types_by_code(connection, chosen_codes))\n"),
        crlf("                         else {})\n"),
        [sys.executable, "-m", "unittest", "tests.test_review_queue_batch.QueueBatchingTests."
         "test_batched_rotation_prefers_least_used_type"],
    ),
    (
        "队列接口不能为了设置跑完整 summary",
        "local_server.py",
        crlf("                    settings = review_storage._settings()\n"),
        crlf("                    settings = review_storage.summary(today or server_today)\n"),
        [sys.executable, "-m", "unittest", "tests.test_review_http."
         "ReviewHttpTests.test_queue_does_not_run_full_summary"],
    ),
    (
        "复习计数必须走轻量接口（不能又去拉全部项目摘要）",
        "js/app.js",
        crlf("        return apiFetch(`/api/review/counts?today=${encodeURIComponent(todayStr())}`, { cache: 'no-store' })\n"),
        crlf("        return readStoredState();\n"),
        ["node", "tests/frontend/verify-review-counts.js"],
    ),
    (
        "计数刷新只能改徽标（不能整卡重绘）",
        "js/app.js",
        crlf("        updateReviewBadges();\n    }\n"),
        crlf("        renderProjects();\n    }\n"),
        ["node", "tests/frontend/verify-review-counts.js"],
    ),
    (
        "复习计数口径不能被改（GROUP BY 的两个 SUM）",
        "storage.py",
        crlf('            "SUM(CASE WHEN review_due < ? THEN 1 ELSE 0 END) AS overdue, "\n'),
        crlf('            "SUM(CASE WHEN review_due < ? THEN 0 ELSE 0 END) AS overdue, "\n'),
        [sys.executable, "-m", "unittest", "tests.test_review_counts.ReviewCountsTests."
         "test_matches_reference_implementation"],
    ),
    (
        "树行事件必须挂在 treeRoot 上（不能退回每行挂闭包）",
        "js/app.js",
        crlf("        treeRoot.addEventListener('click', handleTreeClick);\n"),
        "",
        ["node", "tests/frontend/verify-render-delegation.js"],
    ),
    (
        "筛选后必须用预计算的 matchedIds 过滤顶层（不能整棵树照渲染）",
        "js/app.js",
        crlf("            ? project.tree.filter(week => visibleIds.has(String(week.id)))\n"),
        crlf("            ? project.tree\n"),
        ["node", "tests/frontend/verify-render-delegation.js"],
    ),
    (
        "子节点筛选必须 O(1) 查表（不能又回头走子树）",
        "js/app.js",
        crlf("                ? (node.children || []).filter(child => visibleIds.has(String(child.id)))\n"),
        crlf("                ? (node.children || [])\n"),
        ["node", "tests/frontend/verify-render-delegation.js"],
    ),
    (
        "勾选判据必须靠改动计数（不能又退回整树序列化）",
        "js/app.js",
        crlf("        return projectMutationSeq(project) === (savedProjectSeqById.get(key) || 0);\n"),
        crlf("        return projectMutationSeq(project) >= 0;\n"),
        ["node", "tests/frontend/verify-save-paths.js"],
    ),
    (
        "flushProjectsSave 只能扫被标脏的项目",
        "js/app.js",
        crlf("            let candidates = loaded.filter(project => dirtyProjectIds.has(String(project.id)));\n"),
        crlf("            let candidates = loaded;\n"),
        ["node", "tests/frontend/verify-save-paths.js"],
    ),
    (
        "只为结果集算路径时，path/ancestorIds 口径不能变",
        "storage.py",
        crlf("            if parent_entry[1]:\n"
             "                labels.append(parent_entry[1])\n"),
        crlf("            if False:\n"
             "                labels.append(parent_entry[1])\n"),
        [sys.executable, "-m", "unittest",
         "tests.test_workbench_paths.NodeLocationTests."
         "test_matches_reference_implementation"],
    ),
    (
        "工作台变更指纹必须真的短路（否则提醒等于没优化）",
        "storage.py",
        crlf("        if since and str(since) == version:\n"),
        crlf("        if False:\n"),
        [sys.executable, "-m", "unittest",
         "tests.test_workbench_paths.WorkbenchVersionTests.test_unchanged_since_short_circuits"],
    ),
    (
        "提醒在后台标签页必须暂停轮询",
        "js/app.js",
        crlf("        if (document.hidden) return;\n"),
        crlf("        if (false) return;\n"),
        ["node", "tests/frontend/verify-reminders.js"],
    ),
    (
        "内容没变的节点行不能再发 upsert（整项目保存的写放大）",
        "storage.py",
        crlf('        if existing_rows.get(node["node_id"]) == fingerprint:\n'
             "            continue  # 这一行一个字都没变：不再发一条注定空写的 upsert\n"),
        crlf("        if False:\n"
             "            continue  # 这一行一个字都没变：不再发一条注定空写的 upsert\n"),
        [sys.executable, "-m", "unittest",
         "tests.test_write_amplification.WriteAmplificationTests."
         "test_unchanged_rewrite_issues_no_row_writes"],
    ),
]


def run_case(index: int, name: str, path: str, old: str, new: str, command: list[str]) -> bool:
    file = APP_DIR / path
    original = file.read_bytes()
    text = original.decode("utf-8")
    if old not in text:
        print(f"   ✘ [{index}] {name}\n        找不到要改坏的代码片段（产品代码变了？）：{path}")
        return False
    mutated = text.replace(old, new, 1)
    if mutated == text:
        print(f"   ✘ [{index}] {name}\n        改坏动作没有生效")
        return False
    try:
        file.write_bytes(mutated.encode("utf-8"))
        result = subprocess.run(command, cwd=str(APP_DIR), capture_output=True, text=True, timeout=300)
    finally:
        file.write_bytes(original)
    caught = result.returncode != 0
    marker = "✔" if caught else "✘"
    detail = "" if caught else "  ← 改坏了测试还是通过，这条测试不可信！"
    print(f"   {marker} [{index}] {name}{detail}")
    if not caught:
        tail = (result.stdout + result.stderr).strip().splitlines()[-3:]
        for line in tail:
            print(f"        {line}")
    return caught


def main() -> int:
    parser = argparse.ArgumentParser(description="反向验证测试能否抓到回归")
    parser.add_argument("--list", action="store_true", help="只列出用例")
    args = parser.parse_args()

    if args.list:
        for index, (name, path, _old, _new, command) in enumerate(CASES, 1):
            print(f"{index:>2}. [{path}] {name}")
            print(f"    期望失败：{' '.join(command)}")
        return 0

    print(f"反向验证 {len(CASES)} 条关键修复：把产品改回旧行为，对应测试必须失败\n")
    failed = 0
    for index, (name, path, old, new, command) in enumerate(CASES, 1):
        if not run_case(index, name, path, old, new, command):
            failed += 1

    print()
    if failed:
        print(f"有 {failed} 条没有被测试抓到 ✘")
        return 1
    print(f"全部 {len(CASES)} 条都能被测试抓到 ✔（测试不是空转）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
