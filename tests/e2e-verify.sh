#!/usr/bin/env bash
# 一次性端到端验证：临时库 + 8766 端口 + TODO_AI_MOCK，不触碰 data/todo.sqlite3。
set -uo pipefail

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP"
WORK=$(mktemp -d /tmp/todo-e2e-XXXXXX)
export TODO_SQLITE_FILE="$WORK/todo.sqlite3"
export TODO_SQLITE_BACKUP_DIR="$WORK/backups"
export TODO_MEMO_SQLITE_FILE="$WORK/memo.sqlite3"
export TODO_SESSION_TOKEN_FILE="$WORK/session.token"
export TODO_SESSION_TOKEN="e2e-token-$$"
export TODO_AI_MOCK=1
PORT=$(( 20000 + RANDOM % 20000 ))
export TODO_AI_PORT=$PORT
export TODO_IDLE_SHUTDOWN_SECONDS=600
BASE="http://127.0.0.1:$PORT"

cleanup() {
    if [ -n "${SERVER_PID:-}" ]; then
        kill "$SERVER_PID" 2>/dev/null
        for _ in $(seq 1 20); do kill -0 "$SERVER_PID" 2>/dev/null || break; sleep 0.1; done
        kill -9 "$SERVER_PID" 2>/dev/null
    fi
    rm -rf "$WORK"
}
trap cleanup EXIT

echo "### 工作目录: $WORK  端口: $PORT"

echo "### 1) 造数据（2 个项目，p1 含已完成任务 + 验收记录 + 复习安排）"
python3 - "$APP" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import storage

def make(pid, name, completed=False, with_assessment=False):
    item = {
        "id": f"{pid}-i1", "type": "item", "text": "任务1：解释机制",
        "completed": completed,
        "completedAt": "2026-09-15T10:00:00" if completed else None,
        "optional": False, "assessmentRequired": True, "assessmentHistory": 1 if with_assessment else 0,
        "assessment": None, "createdAt": "2026-09-15",
        "review": {"due": "2026-09-16", "learning": False,
                   "log": [{"at": "2026-09-15", "result": "good"}]} if completed else None,
        "children": [],
    }
    if with_assessment:
        item["assessment"] = {
            "passed": True, "score": 91, "stage": "implementation",
            "summary": "核心机制讲清了", "reply": "通过",
            "questionConversations": [[{"role": "user", "content": "我的回答"},
                                       {"role": "assistant", "content": "通过"}]],
        }
    return {"id": pid, "name": name, "description": "e2e", "createdAt": "2026-09-15",
            "assessmentEnabled": True, "reviewEnabled": True,
            "tree": [{"id": f"{pid}-w1", "type": "week", "text": "第1周", "completed": False,
                      "expanded": False, "createdAt": "2026-09-15", "children": [
                          {"id": f"{pid}-d1", "type": "day", "text": "单元1", "completed": False,
                           "expanded": False, "createdAt": "2026-09-15", "children": [item]}]}]}

storage.write_project(make("p1", "项目一", completed=True, with_assessment=True), None)
storage.write_project(make("p2", "项目二"), None)
print("   已写入:", [s["name"] for s in storage.read_project_summaries()])

import memo_storage
memo_storage.initialize()
memo_storage.write_memo({"title": "长备忘录",
                         "content": "短开头。" + "内容" * 500 + "深层关键词ALPHA",
                         "pinned": False})
print("   已写入备忘录:", [m["title"] for m in memo_storage.list_memo_summaries()])
PY

echo "### 2) 启动服务 (127.0.0.1:$PORT)"
if curl -sf --max-time 1 "$BASE/api/health" >/dev/null 2>&1; then
    echo "   端口已被占用，放弃（避免误测到别的服务）"; exit 1
fi
cd "$APP"
nohup python3 local_server.py >"$WORK/server.log" 2>&1 &
SERVER_PID=$!
cd - >/dev/null
for _ in $(seq 1 40); do
    if curl -sf --max-time 1 "$BASE/api/health" >/dev/null 2>&1; then break; fi
    sleep 0.1
done
curl -sf --max-time 1 "$BASE/api/health" >/dev/null || { echo "服务未启动"; cat "$WORK/server.log"; exit 1; }
kill -0 "$SERVER_PID" 2>/dev/null || { echo "进程已退出（端口冲突？）"; cat "$WORK/server.log"; exit 1; }
echo "   健康检查 OK (pid $SERVER_PID)"

echo "### 3) HTTP 断言"
python3 - "$TODO_SESSION_TOKEN" "$BASE" <<'PY'
import json, re, sys, urllib.error, urllib.parse, urllib.request

TOKEN = sys.argv[1]
BASE = sys.argv[2]
import datetime as _dt
from datetime import date, timedelta
TODAY_STR = _dt.date.today().isoformat()
passed, failed = [], []

def check(name, condition, detail=""):
    (passed if condition else failed).append(name)
    print(("   ✔ " if condition else "   ✘ ") + name + (f"  [{detail}]" if detail and not condition else ""))

def call(path, method="GET", body=None, token=TOKEN, header_token=True):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, method=method, data=data)
    if header_token and token:
        req.add_header("X-Todo-Session", token)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()

# --- ① /api/export ---
status, _, _ = call("/api/export", token=None, header_token=False)
check("① /api/export 无 token 且无 header → 401", status == 401, f"status={status}")

status, headers, body = call("/api/export")
check("① /api/export 仅带 header（不带 query token）→ 200", status == 200, f"status={status}")

query_status, _, _ = call(f"/api/export?token={TOKEN}", header_token=False)
# token 只认请求头：查询串会留在浏览器历史与服务端日志里（前端已改成 fetch + Blob）。
check("① /api/export?token= → 401（下载只认请求头）", query_status == 401, f"status={query_status}")
disposition = headers.get("Content-Disposition", "")
check("① 带 attachment 且文件名是 .json", "attachment" in disposition and disposition.endswith('.json"'), disposition)

snapshot = json.loads(body.decode("utf-8"))
check("① schemaVersion == 2（前端 DATA_SCHEMA_VERSION）", snapshot.get("schemaVersion") == 2, str(snapshot.get("schemaVersion")))
check("① exportedAt 存在", bool(snapshot.get("exportedAt")))
projects = snapshot.get("projects") or []
check("① 导出 2 个项目", len(projects) == 2, f"len={len(projects)}")
check("① 每个项目都带完整 tree（不是摘要）",
      all(p.get("tree") and p["tree"][0].get("children") for p in projects))
by_id = {p["id"]: p for p in projects}
item1 = by_id["p1"]["tree"][0]["children"][0]["children"][0]
check("① p1 任务保持 completed=true", item1.get("completed") is True)
check("① p1 复习安排被导出", (item1.get("review") or {}).get("due") == "2026-09-16")
assessment = item1.get("assessment") or {}
check("① p1 验收记录被导出", assessment.get("passed") is True and assessment.get("score") == 91)
check("① p1 逐题对话被导出",
      assessment.get("questionConversations", [[{}]])[0][0].get("content") == "我的回答")
check("① 未打开的项目 p2 也是完整树", len(by_id["p2"]["tree"][0]["children"]) == 1)

# --- 保存导出前的服务端视图，稍后比对往返一致性 ---
_, _, before_p1 = call("/api/project?id=p1")
_, _, before_p2 = call("/api/project?id=p2")
before_p1, before_p2 = json.loads(before_p1), json.loads(before_p2)

# --- ② 删除全部项目后用导出的 JSON 还原（模拟真实"换机/回滚"）---
_, _, listing = call("/api/projects")
revisions = {s["id"]: s["_revision"] for s in json.loads(listing)["projects"]}
for pid in ("p1", "p2"):
    status, _, body = call(f"/api/project?id={pid}&revision={revisions[pid]}", method="DELETE")
    payload = json.loads(body) if status == 200 else {}
    check(f"② 删除 {pid} → 200 且带回回收站条目 id", status == 200 and payload.get("trashId"),
          f"status={status} body={body[:120]}")
_, _, listing = call("/api/projects")
check("② 删除后项目数为 0", len(json.loads(listing)["projects"]) == 0)

status, _, body = call("/api/import", method="POST",
                       body={"projects": snapshot["projects"]})
check("② 导入导出的 JSON → 200", status == 200, f"status={status} body={body[:200]}")
check("② 导入后回到 2 个项目", len(json.loads(body)["projects"]) == 2)

_, _, after_p1 = call("/api/project?id=p1")
_, _, after_p2 = call("/api/project?id=p2")
check("② p1 往返完全一致（项目+节点+完成态+复习+验收）",
      json.loads(after_p1) == before_p1)
check("② p2 往返完全一致", json.loads(after_p2) == before_p2)

# --- ③ 数据库备份仍可用（证明删别名没伤到手动备份）---
status, _, body = call("/api/backup", method="POST", body={"action": "snapshot", "reason": "e2e"})
payload = json.loads(body)
check("③ 改动前快照 → 200 + 完整备份 zip", status == 200 and payload.get("name", "").endswith(".zip"), body[:200])
backup_name = payload.get("name", "")
status, _, blob = call(f"/api/backup/download?name={backup_name}")
check("③ 下载选中的备份 → 200 且是 zip（统一备份）",
      status == 200 and blob.startswith(b"PK"), f"status={status} head={blob[:16]!r}")

# --- ⑥ 静态资源缓存 ---
def raw_headers(path):
    req = urllib.request.Request(BASE + path)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, response.headers
    except urllib.error.HTTPError as error:
        return error.code, error.headers

# 版本号直接从 index.html 读，避免每次改前端都来同步这个脚本
_, _, _index_html = call("/index.html", header_token=False)
_versions = dict(re.findall(r"(js/app\.js|css/style\.css|js/api-client\.js|js/study-tools\.js)\?v=(\d+)",
                            _index_html.decode("utf-8")))
assert set(_versions) == {"js/app.js", "css/style.css", "js/api-client.js", "js/study-tools.js"}, _versions
for path in (f"/js/app.js?v={_versions['js/app.js']}", f"/css/style.css?v={_versions['css/style.css']}",
             f"/js/api-client.js?v={_versions['js/api-client.js']}", f"/js/study-tools.js?v={_versions['js/study-tools.js']}"):
    status, headers = raw_headers(path)
    values = headers.get_all("Cache-Control") or []
    check(f"⑥ {path} → public, max-age=86400 且不重复",
          status == 200 and values == ["public, max-age=86400"], f"{status} {values}")

for path in ("/", "/index.html"):
    status, headers = raw_headers(path)
    values = headers.get_all("Cache-Control") or []
    check(f"⑥ 入口 {path} → no-store", status == 200 and values == ["no-store"], f"{status} {values}")

status, headers = raw_headers("/api/config")
check("⑥ /api/*（未带 token 的 401 也算）仍为 no-store",
      status == 401 and (headers.get_all("Cache-Control") or []) == ["no-store"],
      f"{status} {headers.get_all('Cache-Control')}")

# --- ⑦ 备忘录列表懒加载全文 ---
LONG_BODY = "短开头。" + "内容" * 500 + "深层关键词ALPHA"
status, _, body = call("/api/memos")
memos = json.loads(body)["memos"]
check("⑦ /api/memos 返回两条（含默认占位）", len(memos) == 2, f"len={len(memos)}")
check("⑦ 列表项不带全文 content", all("content" not in m for m in memos))
check("⑦ 列表项带预览/长度/更新时间",
      all("contentPreview" in m and "contentLength" in m and m.get("updatedAt") for m in memos))
long_memo = next(m for m in memos if m["title"] == "长备忘录")
check("⑦ 预览不超过 200 字", len(long_memo["contentPreview"]) <= 200, f"len={len(long_memo['contentPreview'])}")
check("⑦ contentLength 等于全文长度", long_memo["contentLength"] == len(LONG_BODY), f"{long_memo['contentLength']}")

status, _, body = call("/api/memos?q=" + urllib.parse.quote("深层关键词ALPHA"))
hits = json.loads(body)["memos"]
check("⑦ 全文搜索命中预览之外的正文", [m["title"] for m in hits] == ["长备忘录"], str(hits))
status, _, body = call("/api/memos?q=" + urllib.parse.quote("%"))
check("⑦ LIKE 通配符已转义（搜 % 命中 0 条）", json.loads(body)["memos"] == [], body[:120])

status, _, body = call("/api/memo?id=" + long_memo["id"])
full = json.loads(body)["memo"]
check("⑦ 单条接口返回完整全文",
      full["content"] == LONG_BODY and len(full["content"]) == long_memo["contentLength"])
status, _, body = call("/api/memo", method="POST",
                       body={"id": full["id"], "title": full["title"], "content": full["content"],
                             "pinned": False, "expectedRevision": full["revision"]})
check("⑦ 取全文后写回成功且未截断",
      status == 200 and len(json.loads(body)["memo"]["content"]) == len(LONG_BODY), body[:160])

# --- R1 请求校验：非法输入必须返回 JSON，不能空回复 ---
import http.client
RAW_HOST, RAW_PORT = "127.0.0.1", int(BASE.rsplit(":", 1)[1])

def raw(method, path, body=None, headers=None, declare_length=None):
    conn = http.client.HTTPConnection(RAW_HOST, RAW_PORT, timeout=15)
    hdrs = {"X-Todo-Session": TOKEN}
    if declare_length is not None:
        hdrs["Content-Length"] = str(declare_length)
    hdrs.update(headers or {})
    conn.request(method, path, body=body, headers=hdrs)
    response = conn.getresponse()
    result = (response.status, response.getheader("Content-Type", "") or "", response.read())
    conn.close()
    return result

def check_json_error(name, status, ctype, data, expect_status):
    ok = status == expect_status and ctype.startswith("application/json") and bool(data)
    detail = f"status={status} ctype={ctype!r} body={data[:120]!r}"
    if ok:
        try:
            ok = "error" in json.loads(data.decode("utf-8"))
        except Exception as error:
            ok = False
            detail += f" JSON 解析失败: {error}"
    check(name, ok, detail)

# /api/memo 的请求上限必须 ≥ 备忘录本身的 50 MB 上限；声明一个远超上限的长度测 413
status, ctype, data = raw("POST", "/api/memo", declare_length=200 * 1024 * 1024)
check_json_error("R1 ② 超过该接口上限 → 413 JSON", status, ctype, data, 413)

# 6 MB 的备忘录正文必须能存进去（旧上限 5 MB 会把 5–50 MB 的备忘录永远挡在门外）
big_memo = json.dumps({"title": "大备忘录", "content": "备" * (6 * 1024 * 1024)}).encode("utf-8")
status, ctype, data = raw("POST", "/api/memo", body=big_memo,
                          headers={"Content-Type": "application/json"})
check("R1 ④ 6 MB 备忘录可以保存（HTTP 上限已对齐 50 MB）",
      status == 200 and json.loads(data).get("ok") is True, f"{status} {data[:120]}")

# 来源校验：GET / DELETE 也要和 POST 一样拒绝陌生 Origin，且 403 不能报成 401
status, ctype, data = raw("GET", "/api/projects", headers={"Origin": "http://evil.example"})
check_json_error("R1 ⑤ GET 陌生 Origin → 403 JSON", status, ctype, data, 403)
status, ctype, data = raw("DELETE", "/api/project?id=nope&revision=0", headers={"Origin": "http://evil.example"})
check_json_error("R1 ⑤ DELETE 陌生 Origin → 403 JSON（不是 401）", status, ctype, data, 403)

# 备份名校验只走恢复动作：不存在与路径穿越都必须回 JSON 400（不能再是空回复）
for bad_name in ("nope.zip", "..%2Fetc%2Fpasswd.zip"):
    status, ctype, data = raw("POST", "/api/backup",
                              body=json.dumps({"action": "restore", "name": bad_name}).encode("utf-8"),
                              headers={"Content-Type": "application/json"})
    check_json_error(f"R1 ⑧ 恢复非法/不存在的备份（{bad_name}）→ 400 JSON", status, ctype, data, 400)

status, ctype, data = raw("DELETE", "/api/memo?id=x")
check_json_error("R1 ③ DELETE memo 缺 revision → 400 JSON", status, ctype, data, 400)
status, ctype, data = raw("DELETE", "/api/memo?id=x&revision=abc")
check_json_error("R1 ③ DELETE memo revision 非数字 → 400 JSON", status, ctype, data, 400)
status, ctype, data = raw("DELETE", "/api/memo?id=not-exist&revision=1")
check_json_error("R1 ③ DELETE memo 不存在 → 404 JSON", status, ctype, data, 404)

status, _, body = call("/api/memo", method="POST", body={"title": "删除测试", "content": "x", "pinned": False})
created = json.loads(body)["memo"]
status, ctype, data = raw("DELETE", "/api/memo?id=%s&revision=%d" % (created["id"], int(created["revision"]) + 5))
check_json_error("R1 ③ DELETE memo 版本不符 → 409 JSON", status, ctype, data, 409)

status, ctype, data = raw("DELETE", "/api/project")
check_json_error("R1 ③ DELETE project 缺 id → 400 JSON", status, ctype, data, 400)
status, ctype, data = raw("DELETE", "/api/project?id=nope&revision=0")
check_json_error("R1 ③ DELETE project 不存在 → 404 JSON", status, ctype, data, 404)
status, headers, data = call("/api/trash", method="POST", body={"action": "restore", "id": "nope"})
check_json_error("R1 ③ 回收站恢复不存在条目 → 404 JSON", status, headers.get("Content-Type", ""), data, 404)
status, headers, data = call("/api/project", method="POST", body={"project": "not-a-dict"})
check_json_error("R1 ③ 项目格式错误 → 400 JSON", status, headers.get("Content-Type", ""), data, 400)
status, headers, data = call("/api/project")
check_json_error("R1 ③ GET project 缺 id → 400 JSON", status, headers.get("Content-Type", ""), data, 400)

# --- 其它接口没被带崩 ---
status, _, body = call("/api/storage")
check("④ /api/storage → 200 且 projectCount=2",
      status == 200 and json.loads(body)["projectCount"] == 2)
status, _, body = call("/api/config")
check("④ /api/config → 200（mock 模式 ready）", status == 200 and json.loads(body)["ready"] is True)
status, _, body = call("/index.html", header_token=False)
html = body.decode("utf-8")
check("④ 页面已带新的下载按钮与文案",
      status == 200 and 'downloadDatabaseBackupBtn' in html and '导出 JSON' in html
      and re.search(r'js/app\.js\?v=\d+', html) is not None)


# --- R3 ⑦ 复习计数按客户端日期计算 ---
_, _, body = call("/api/projects?today=2026-09-16")
payload = json.loads(body)
check("R3 ⑦ today=到期当天 → 今天到期 1、逾期 0",
      payload["reviewTotals"] == {"today": 1, "overdue": 0}, json.dumps(payload["reviewTotals"]))
check("R3 ⑦ 回显 usedToday 与服务端日期", payload["usedToday"] == "2026-09-16" and bool(payload["serverToday"]),
      f'{payload.get("usedToday")} / {payload.get("serverToday")}')
_, _, body = call("/api/projects?today=2026-09-20")
payload = json.loads(body)
check("R3 ⑦ today=之后 → 变成逾期 1",
      payload["reviewTotals"] == {"today": 0, "overdue": 1}, json.dumps(payload["reviewTotals"]))
_, _, body = call("/api/projects?today=not-a-date")
payload = json.loads(body)
check("R3 ⑦ 非法 today 回落到服务端日期（不报错）",
      payload["usedToday"] == payload["serverToday"], body[:120])

# --- R4 统一备份：快照 / 列表 / 下载（创建、重命名、查看内容已取消）---
status, headers, data = call("/api/backup", method="POST", body={"action": "snapshot", "reason": "e2e-r4"})
payload = json.loads(data)
R4_BACKUP = payload.get("name", "")
check("R4 ⑧ 改动前快照 → .zip", status == 200 and R4_BACKUP.endswith(".zip"), data[:160])

status, headers, data = call("/api/backups")
entries = json.loads(data)["backups"]
entry = next((item for item in entries if item["name"] == R4_BACKUP), None)
check("R4 ⑧ 列表可见且标记 kind=full", entry is not None and entry["kind"] == "full", str(entries)[:200])
check("R4 ⑨ 启动时已生成每日快照", any(item["name"].startswith("daily-") for item in entries), str([i["name"] for i in entries])[:200])

status, ctype, data = raw("GET", "/api/backup/download?name=%s" % R4_BACKUP)
check("R4 ⑧ 下载完整备份是 zip", status == 200 and data[:2] == b"PK", f"{status} {data[:8]!r}")

# --- R2 导入校验（放最后：会替换全部项目）---
import copy
good = snapshot["projects"]

dup_project = copy.deepcopy(good)
dup_project[1]["id"] = dup_project[0]["id"]
dup_project[1]["name"] = "重复 ID 的项目"
status, headers, data = call("/api/import", method="POST", body={"projects": dup_project})
check_json_error("R2 ④ 重复项目 ID → 400 JSON", status, headers.get("Content-Type", ""), data, 400)
message = json.loads(data).get("error", "")
check("R2 ④ 报出重复的项目 ID 与两个项目名",
      "重复的项目 ID" in message and str(dup_project[0]["id"]) in message
      and "重复 ID 的项目" in message, message[:160])

dup_node = copy.deepcopy(good[:1])
item = dup_node[0]["tree"][0]["children"][0]["children"][0]
dup_node[0]["tree"][0]["children"][0]["children"].append({**copy.deepcopy(item), "text": "任务2"})
status, headers, data = call("/api/import", method="POST", body={"projects": dup_node})
check_json_error("R2 ④ 重复节点 ID → 400 JSON", status, headers.get("Content-Type", ""), data, 400)
message = json.loads(data).get("error", "")
check("R2 ④ 报出重复节点的完整路径", "第1周 / 单元1 / 任务2" in message, message[:160])

missing = copy.deepcopy(good[:1])
missing[0].pop("id", None)
missing[0]["tree"][0].pop("id", None)
status, headers, data = call("/api/import", method="POST", body={"projects": missing})
check("R2 ④ 缺失 ID 自动生成（不拒绝）", status == 200, f"{status} {data[:160]}")
generated_id = json.loads(data)["projects"][0]["id"]
_, _, body = call("/api/project?id=" + generated_id)
stored = json.loads(body)["project"]
check("R2 ④ 生成的 ID 是 uuid 且树完整",
      len(str(stored["id"])) == 36 and len(str(stored["tree"][0]["id"])) == 36
      and str(stored["tree"][0]["children"][0]["children"][0]["text"]).startswith("任务1"),
      json.dumps(stored)[:160])


# --- R4 恢复：把数据还原回备份时的状态（放在最后，会覆盖两个库）---
status, headers, data = call("/api/backup", method="POST", body={"action": "restore", "name": R4_BACKUP})
restored = json.loads(data).get("restored") if status == 200 else None
check("R4 ⑧ 恢复完整备份 → 两个库都被替换",
      status == 200 and sorted(restored or []) == ["memo.sqlite3", "todo.sqlite3"], data[:200])
_, _, body = call("/api/projects")
check("R4 ⑧ 恢复后项目数回到备份时的 2", len(json.loads(body)["projects"]) == 2, body[:120])
_, _, body = call("/api/memos")
check("R4 ⑧ 恢复后备忘录也回来了", len(json.loads(body)["memos"]) >= 2, body[:120])

status, headers, data = call("/api/backups")
names = [item["name"] for item in json.loads(data)["backups"]]
check("R4 ⑧ 恢复前自动留了应急快照", any(name.startswith("before-restore-") for name in names), str(names[:8]))

status, headers, data = call("/api/backup", method="POST", body={"action": "snapshot", "reason": "before-bulk-test"})
check("R4 ⑨ 大批量改动前可点名要快照",
      status == 200 and json.loads(data)["name"].startswith("before-before-bulk-test-"), data[:160])

# --- R5 ⑩ 回收站：批量恢复/批量删除/立即清空 + 到期提示 ---
def trash_ids():
    _, _, body = call("/api/trash")
    return json.loads(body)["items"]

_, _, body = call("/api/projects")
listing = json.loads(body)["projects"]
for entry in listing[:2]:
    call("/api/project?id=%s&revision=%s" % (entry["id"], entry["_revision"]), method="DELETE")
items = trash_ids()
check("R5 ⑩ 回收站列表带自动清理时间", len(items) >= 2 and all(item.get("expiresAt") for item in items), json.dumps(items)[:200])

status, headers, data = call("/api/trash", method="POST", body={"action": "restore-many", "ids": [items[0]["id"]]})
payload = json.loads(data)
check("R5 ⑩ 批量恢复 → 只恢复选中那条",
      status == 200 and payload["restored"] == [items[0]["id"]] and payload["failed"] == []
      and len(payload["projects"]) == 1, data[:200])

status, headers, data = call("/api/trash", method="POST", body={"action": "delete-many", "ids": [items[1]["id"]]})
payload = json.loads(data)
check("R5 ⑩ 批量删除 → 永久删除且不再出现在列表里",
      status == 200 and payload["deleted"] == [items[1]["id"]]
      and all(entry["id"] != items[1]["id"] for entry in payload["items"]), data[:200])

status, headers, data = call("/api/trash", method="POST", body={"action": "delete-many", "ids": ["不存在的-id"]})
check_json_error("R5 ⑩ 批量操作含未知 ID → 404 JSON", status, headers.get("Content-Type", ""), data, 404)

status, headers, data = call("/api/trash", method="POST", body={"action": "restore-many", "ids": []})
check_json_error("R5 ⑩ 批量操作空选择 → 400 JSON", status, headers.get("Content-Type", ""), data, 400)

_, _, body = call("/api/projects")
for entry in json.loads(body)["projects"]:
    call("/api/project?id=%s&revision=%s" % (entry["id"], entry["_revision"]), method="DELETE")
status, headers, data = call("/api/trash", method="POST", body={"action": "purge"})
payload = json.loads(data)
check("R5 ⑩ 立即清空回收站", status == 200 and payload["purged"] >= 1 and payload["items"] == [], data[:200])


# --- 批次 1：任务元数据（优先级/截止/标签/耗时/备注/链接）---
_, _, body = call("/api/storage")
check("批次1 schema 版本已 >= 6（元数据列）",
      isinstance(json.loads(body)["schemaVersion"], int) and json.loads(body)["schemaVersion"] >= 6, body[:120])

meta_project = {
    "id": "meta-e2e", "name": "元数据项目", "description": "", "createdAt": "2026-09-15",
    "assessmentEnabled": False, "reviewEnabled": False,
    "tree": [{"id": "meta-w", "type": "week", "text": "第1周", "completed": False, "expanded": False,
              "createdAt": "2026-09-15", "children": [
                  {"id": "meta-d", "type": "day", "text": "单元1", "completed": False, "expanded": False,
                   "createdAt": "2026-09-15", "children": [
                       {"id": "meta-i", "type": "item", "text": "带元数据的任务", "completed": False,
                        "completedAt": None, "optional": False, "assessmentRequired": False,
                        "assessmentHistory": 0, "assessment": None, "createdAt": "2026-09-15",
                        "priority": "high", "dueDate": "2026-09-20", "estimateMinutes": 45,
                        "tags": ["Python", "复习"], "note": "先看装饰器",
                        "links": [{"label": "文档", "url": "https://docs.python.org/3/"}],
                        "children": []}]}]}],
}
status, headers, data = call("/api/project", method="POST", body={"project": meta_project, "expectedRevision": 0})
check("批次1 写入元数据 → 200", status == 200, data[:160])
_, _, body = call("/api/project?id=meta-e2e")
stored_item = json.loads(body)["project"]["tree"][0]["children"][0]["children"][0]
check("批次1 元数据原样回读",
      stored_item["priority"] == "high" and stored_item["dueDate"] == "2026-09-20"
      and stored_item["estimateMinutes"] == 45 and stored_item["tags"] == ["Python", "复习"]
      and stored_item["note"] == "先看装饰器" and stored_item["links"][0]["url"] == "https://docs.python.org/3/",
      json.dumps(stored_item, ensure_ascii=False)[:240])

revision = json.loads(call("/api/project?id=meta-e2e")[2])["revision"]
meta_project["tree"][0]["children"][0]["children"][0]["priority"] = "URGENT"
status, headers, data = call("/api/project", method="POST", body={"project": meta_project, "expectedRevision": revision})
_, _, body = call("/api/project?id=meta-e2e")
stored_item = json.loads(body)["project"]["tree"][0]["children"][0]["children"][0]
check("批次1 非法优先级被清洗为空", status == 200 and stored_item["priority"] == "", json.dumps(stored_item, ensure_ascii=False)[:160])

revision = json.loads(call("/api/project?id=meta-e2e")[2])["revision"]
meta_project["tree"][0]["children"][0]["children"][0]["links"] = [{"url": "javascript:alert(1)"}]
status, headers, data = call("/api/project", method="POST", body={"project": meta_project, "expectedRevision": revision})
check_json_error("批次1 非 http 链接 → 400 JSON", status, headers.get("Content-Type", ""), data, 400)
message = json.loads(data).get("error", "")
check("批次1 链接错误说明要求 http", "http" in message, message[:120])


# --- 批次 2：收集箱 / 今日工作台 / 最近入口 ---
status, headers, data = call("/api/inbox/add", method="POST",
                             body={"node": {"text": "工作台测试任务", "priority": "high",
                                            "dueDate": TODAY_STR, "tags": ["批次2"], "estimateMinutes": 20}})
added = json.loads(data)
check("批次2 快速添加进收集箱", status == 200 and added["node"]["text"] == "工作台测试任务"
      and added["node"]["priority"] == "high", data[:200])
inbox_node = added["node"]["id"]

status, headers, data = call("/api/inbox/add", method="POST", body={"node": {"text": "坏链接", "links": [{"url": "javascript:1"}]}})
check_json_error("批次2 收集箱也校验链接 → 400 JSON", status, headers.get("Content-Type", ""), data, 400)

status, headers, data = call("/api/workbench?today=" + TODAY_STR)
board = json.loads(data)
check("批次2 工作台分组齐全",
      status == 200 and set(board["groups"]) == {"overdue", "today", "next7", "reviewToday", "inbox"},
      str(list((board.get("groups") or {}).keys())))
check("批次2 工作台今天包含刚加的任务（dueDate=今天）",
      any(entry["text"] == "工作台测试任务" for entry in board["groups"]["today"]), json.dumps(board["totals"]))
check("批次2 排了日期的收集箱任务不再重复出现在收集箱分组",
      not any(entry["nodeId"] == inbox_node for entry in board["groups"]["inbox"]), str(board["totals"]))
all_ids = [entry["nodeId"] for group in board["groups"].values() for entry in group]
check("批次2 工作台同一条任务不会被两个分组重复统计", len(all_ids) == len(set(all_ids)),
      f"{len(all_ids)} 条 / {len(set(all_ids))} 个唯一 id")
status, headers, data = call("/api/inbox/add", method="POST", body={"node": {"text": "没排期的收集箱任务"}})
loose_inbox_node = json.loads(data)["node"]["id"]
status, headers, data = call("/api/workbench?today=" + TODAY_STR)
board = json.loads(data)
check("批次2 没排期的收集箱任务仍在收集箱分组",
      any(entry["nodeId"] == loose_inbox_node for entry in board["groups"]["inbox"]), str(board["totals"]))
check("批次2 工作台条目带路径与祖先 id",
      all("path" in entry and "ancestorIds" in entry for group in board["groups"].values() for entry in group))

status, headers, data = call("/api/workbench?today=" + urllib.parse.quote("不是日期"))
check("批次2 工作台非法日期回落服务端当天", json.loads(data)["today"] == json.loads(data)["serverToday"], data[:120])

status, headers, data = call("/api/project")
check_json_error("批次2 GET project 缺 id → 400 JSON", status, headers.get("Content-Type", ""), data, 400)

# 归类：先建一个目标项目，再把收集箱任务移进去（此时前面的用例已经清空过项目）
target_project = {
    "id": "b2-target", "name": "归类目标项目", "description": "", "createdAt": TODAY_STR,
    "assessmentEnabled": False, "reviewEnabled": False,
    "tree": [{"id": "b2-w", "type": "week", "text": "第1周", "completed": False, "expanded": False,
              "createdAt": TODAY_STR, "children": [
                  {"id": "b2-d", "type": "day", "text": "单元1", "completed": False, "expanded": False,
                   "createdAt": TODAY_STR, "children": []}]}],
}
status, _, body = call("/api/project", method="POST", body={"project": target_project, "expectedRevision": 0})
check("批次2 建好归类目标项目", status == 200, body[:160])
target_parent = "b2-d"
status, headers, data = call("/api/inbox/move", method="POST",
                             body={"nodeId": inbox_node, "fromProjectId": "inbox",
                                   "toProjectId": "b2-target", "parentId": target_parent})
check("批次2 归类移动 → 200", status == 200 and json.loads(data)["to"] == "b2-target", data[:200])
_, _, body = call("/api/project?id=inbox")
check("批次2 归类后收集箱里没有它了",
      all(str(node.get("id")) != inbox_node for node in json.loads(body)["project"]["tree"]), body[:160])
_, _, body = call("/api/project?id=b2-target")
placed = json.loads(body)["project"]["tree"][0]["children"][0]["children"]
check("批次2 归类后出现在目标的单元下",
      any(str(node.get("id")) == inbox_node for node in placed), json.dumps(placed, ensure_ascii=False)[:200])
check("批次2 归类保留了元数据",
      next(node for node in placed if str(node.get("id")) == inbox_node)["priority"] == "high")

status, headers, data = call("/api/inbox/move", method="POST", body={"nodeId": "不存在", "toProjectId": "b2-target"})
check_json_error("批次2 归类不存在的任务 → 400 JSON", status, headers.get("Content-Type", ""), data, 400)

status, headers, data = call("/api/recent")
recent = json.loads(data)
check("批次2 最近接口三类都有",
      status == 200 and set(recent) >= {"opened", "modified", "completed"}, str(list(recent.keys())))
check("批次2 最近打开记录了刚读过的项目",
      any(entry["id"] in {"b2-target", "inbox"} for entry in recent["opened"]), json.dumps(recent["opened"], ensure_ascii=False)[:160])


# --- 批次 3：批量修改 / 归档（筛选视图已按冗余审计取消）---

# 批量修改：建一个带元数据的项目
batch_project = {
    "id": "b3-target", "name": "批量目标", "description": "", "createdAt": TODAY_STR,
    "assessmentEnabled": False, "reviewEnabled": False,
    "tree": [{"id": "b3-w", "type": "week", "text": "第1周", "completed": False, "expanded": False,
              "createdAt": TODAY_STR, "children": [
                  {"id": "b3-d", "type": "day", "text": "单元1", "completed": False, "expanded": False,
                   "createdAt": TODAY_STR, "children": [
                       {"id": "b3-a", "type": "item", "text": "普通任务A", "completed": False, "completedAt": None,
                        "optional": False, "assessmentRequired": False, "assessmentHistory": 0, "assessment": None,
                        "createdAt": TODAY_STR, "children": []},
                       {"id": "b3-b", "type": "item", "text": "普通任务B", "completed": False, "completedAt": None,
                        "optional": False, "assessmentRequired": False, "assessmentHistory": 0, "assessment": None,
                        "createdAt": TODAY_STR, "children": []},
                       {"id": "b3-c", "type": "item", "text": "需验收任务", "completed": False, "completedAt": None,
                        "optional": False, "assessmentRequired": True, "assessmentHistory": 0, "assessment": None,
                        "createdAt": TODAY_STR, "children": []}]}]}],
}
status, _, body = call("/api/project", method="POST", body={"project": batch_project, "expectedRevision": 0})
check("批次3 建好批量目标项目", status == 200, body[:160])
targets = [{"projectId": "b3-target", "nodeId": "b3-a"}, {"projectId": "b3-target", "nodeId": "b3-b"}]

status, headers, data = call("/api/batch", method="POST", body={"action": "set-priority", "targets": targets, "value": "high"})
check("批次3 批量设优先级", status == 200 and json.loads(data)["changed"] == 2, data[:160])
status, headers, data = call("/api/batch", method="POST", body={"action": "add-tags", "targets": targets, "value": ["Python", "复习"]})
check("批次3 批量加标签", status == 200 and json.loads(data)["changed"] == 2, data[:160])
status, headers, data = call("/api/batch", method="POST", body={"action": "set-due", "targets": [targets[0]], "value": TODAY_STR})
check("批次3 批量设截止", status == 200 and json.loads(data)["changed"] == 1, data[:160])
status, headers, data = call("/api/batch", method="POST", body={"action": "shift-due", "targets": [targets[0]], "value": 2})
check("批次3 批量延期", status == 200 and json.loads(data)["changed"] == 1, data[:160])
_, _, body = call("/api/project?id=b3-target")
batch_items = json.loads(body)["project"]["tree"][0]["children"][0]["children"]
by_id = {node["id"]: node for node in batch_items}
check("批次3 批量结果正确（优先级/标签/截止都写进去了）",
      by_id["b3-a"]["priority"] == "high" and by_id["b3-a"]["tags"] == ["Python", "复习"]
      and by_id["b3-a"]["dueDate"] == (date.fromisoformat(TODAY_STR) + timedelta(days=2)).isoformat(),
      json.dumps(by_id["b3-a"], ensure_ascii=False)[:240])
check("批次3 只改了选中的项", by_id["b3-c"]["priority"] == "" and by_id["b3-c"].get("tags", []) == [])

status, headers, data = call("/api/batch", method="POST",
                             body={"action": "complete", "targets": [{"projectId": "b3-target", "nodeId": "b3-c"},
                                                                     {"projectId": "b3-target", "nodeId": "b3-b"}]})
payload = json.loads(data)
check("批次3 批量完成跳过需验收任务并给出原因",
      status == 200 and payload["changed"] == 1 and len(payload["failed"]) == 1 and "验收" in payload["failed"][0]["error"],
      data[:220])

status, headers, data = call("/api/batch", method="POST", body={"action": "explode", "targets": targets})
check_json_error("批次3 不支持的批量动作 → 400 JSON", status, headers.get("Content-Type", ""), data, 400)
status, headers, data = call("/api/batch", method="POST", body={"action": "set-priority", "targets": []})
check_json_error("批次3 空选择 → 400 JSON", status, headers.get("Content-Type", ""), data, 400)

# 归档
_, _, body = call("/api/project?id=b3-target")
archived_project = json.loads(body)
archived_project["project"]["archived"] = True
status, _, body = call("/api/project", method="POST",
                       body={"project": archived_project["project"], "expectedRevision": archived_project["revision"]})
check("批次3 归档项目", status == 200, body[:160])
_, _, body = call("/api/projects")
archived_summary = next(entry for entry in json.loads(body)["projects"] if entry["id"] == "b3-target")
check("批次3 列表里带 archived 标记", archived_summary["archived"] is True, json.dumps(archived_summary)[:160])
_, _, body = call("/api/workbench?today=" + TODAY_STR)
texts = [entry["text"] for group in json.loads(body)["groups"].values() for entry in group]
check("批次3 归档项目不再出现在工作台", "普通任务A" not in texts, str(texts)[:160])


# --- 批次 4：周期任务（服务端生成 + 校验）与快速添加指定项目 ---
add_project = {
    "id": "b4-target", "name": "周期目标", "description": "", "createdAt": TODAY_STR,
    "assessmentEnabled": False, "reviewEnabled": False,
    "tree": [{"id": "b4-w", "type": "week", "text": "第1周", "completed": False, "expanded": False,
              "createdAt": TODAY_STR, "children": [
                  {"id": "b4-d", "type": "day", "text": "单元1", "completed": False, "expanded": False,
                   "createdAt": TODAY_STR, "children": []}]}],
}
status, _, body = call("/api/project", method="POST", body={"project": add_project, "expectedRevision": 0})
check("批次4 建好周期目标项目", status == 200, body[:160])

status, headers, data = call("/api/inbox/add", method="POST",
                             body={"projectId": "b4-target", "parentId": "b4-d",
                                   "node": {"text": "每天背单词", "dueDate": TODAY_STR, "priority": "mid",
                                            "tags": ["英语"], "repeat": {"freq": "daily"}}})
added = json.loads(data)
check("批次4 快速添加可直接进指定项目", status == 200 and added.get("projectId") == "b4-target", data[:200])
check("批次4 周期规则存下来了", added["node"].get("repeat") == {"freq": "daily", "interval": 1}, json.dumps(added["node"], ensure_ascii=False)[:200])
recurring_id = added["node"]["id"]
_, _, body = call("/api/project?id=b4-target")
check("批次4 任务落在指定的单元下",
      any(str(node.get("id")) == recurring_id for node in json.loads(body)["project"]["tree"][0]["children"][0]["children"]),
      body[:200])

status, headers, data = call("/api/inbox/add", method="POST", body={"node": {"text": "坏周期", "repeat": {"freq": "hourly"}}})
check("批次4 非法周期被丢弃", status == 200 and "repeat" not in json.loads(data)["node"], data[:200])

status, headers, data = call("/api/batch", method="POST",
                             body={"action": "complete", "targets": [{"projectId": "b4-target", "nodeId": recurring_id}]})
payload = json.loads(data)
check("批次4 批量完成周期任务会生成下一次",
      status == 200 and payload["changed"] == 1 and payload["spawned"] == 1, data[:200])
_, _, body = call("/api/project?id=b4-target")
items = json.loads(body)["project"]["tree"][0]["children"][0]["children"]
check("批次4 项目里多出下一次出现", len(items) == 2, json.dumps(items, ensure_ascii=False)[:200])
spawned = next(node for node in items if not node["completed"])
expected_next = (date.fromisoformat(TODAY_STR) + timedelta(days=1)).isoformat()
check("批次4 下一次的日期正确且保留周期与标签",
      spawned["dueDate"] == expected_next and spawned["repeat"] == {"freq": "daily", "interval": 1}
      and spawned["tags"] == ["英语"], json.dumps(spawned, ensure_ascii=False)[:220])
_, _, body = call("/api/workbench?today=" + TODAY_STR)
next7 = json.loads(body)["groups"]["next7"]
check("批次4 下一次出现在工作台的未来 7 天分组", any(entry["nodeId"] == spawned["id"] for entry in next7), str(next7)[:200])

# Q13：单条完成（节点 patch）也由服务端生成下一次，并在响应里回传副本
status, headers, data = call("/api/node/patch", method="POST", body={
    "projectId": "b4-target", "expectedRevision": 3,
    "ops": [{"op": "update", "nodeId": spawned["id"],
             "fields": {"completed": True, "completedAt": TODAY_STR + "T09:00:00"}}]})
patched = json.loads(data)
check("批次4 单条完成（patch）由服务端生成下一次并回传副本",
      status == 200 and len(patched.get("spawned") or []) == 1
      and patched["spawned"][0]["parentId"] == "b4-d", data[:220])
check("批次4 回传的副本字段正确（日期顺延 / 未完成 / 保留周期）",
      patched["spawned"][0]["node"]["dueDate"] == (date.fromisoformat(expected_next) + timedelta(days=1)).isoformat()
      and patched["spawned"][0]["node"]["completed"] is False
      and patched["spawned"][0]["node"]["repeat"] == {"freq": "daily", "interval": 1},
      json.dumps(patched.get("spawned"), ensure_ascii=False)[:220])
_, _, body = call("/api/project?id=b4-target")
check("批次4 patch 后库里真的多出那一条",
      len(json.loads(body)["project"]["tree"][0]["children"][0]["children"]) == 3, body[:160])

# Q13：整树保存路径（非 patch）同样按"完成翻转"生成，且不重复生成
status, headers, data = call("/api/project?id=b4-target")
project_now = json.loads(data)["project"]
project_now["_revision"] = json.loads(data)["revision"]
for item in project_now["tree"][0]["children"][0]["children"]:
    if not item["completed"]:
        item["completed"] = True
        item["completedAt"] = TODAY_STR + "T10:00:00"
        break
status, headers, data = call("/api/project", method="POST", body={
    "project": project_now, "expectedRevision": project_now["_revision"]})
saved = json.loads(data)
check("批次4 整树保存也按完成翻转生成下一次",
      status == 200 and len(saved.get("spawned") or []) == 1, data[:220])

status, headers, data = call("/api/project?id=b4-target")
same = json.loads(data)
status, headers, data = call("/api/project", method="POST", body={
    "project": same["project"], "expectedRevision": same["revision"]})
check("批次4 再存一次（没有新的翻转）不会重复生成",
      status == 200 and (json.loads(data).get("spawned") or []) == [], data[:220])

# --- 第五批：中等难度任务管理（拖拽排序 / 复制 / 删除影响面 / 回收站 / 模板 / 导入 / 导出 / 活动 / 设置）---
_, _, body = call("/api/project", method="POST", body={
    "project": {
        "id": "b5", "name": "批次5项目", "description": "", "createdAt": TODAY_STR,
        "assessmentEnabled": False, "reviewEnabled": False, "archived": False,
        "tree": [{"id": "b5-w1", "type": "week", "text": "第1周", "completed": False, "expanded": False,
                  "createdAt": TODAY_STR, "children": [
                      {"id": "b5-d1", "type": "day", "text": "单元1", "completed": False, "expanded": False,
                       "createdAt": TODAY_STR, "children": [
                           {"id": "b5-i1", "type": "item", "text": "任务1", "completed": False,
                            "completedAt": None, "optional": False, "assessmentRequired": False,
                            "assessmentHistory": 0, "assessment": None, "createdAt": TODAY_STR,
                            "children": [], "priority": "high", "tags": ["批次5"],
                            "note": "备注", "links": [{"label": "文档", "url": "https://example.com"}],
                            "estimateMinutes": 20},
                           {"id": "b5-i2", "type": "item", "text": "任务2", "completed": True,
                            "completedAt": TODAY_STR + "T08:00:00", "optional": False,
                            "assessmentRequired": False, "assessmentHistory": 1,
                            "assessment": {"passed": True, "score": 90}, "createdAt": TODAY_STR,
                            "children": [], "review": {"due": TODAY_STR, "learning": False,
                                                        "log": [{"at": TODAY_STR, "result": "good"}]}},
                       ]},
                      {"id": "b5-d2", "type": "day", "text": "单元2", "completed": False, "expanded": False,
                       "createdAt": TODAY_STR, "children": []}]}],
    }})
check("批次5 建好管理目标项目", status == 200, body[:160])

status, headers, data = call("/api/node/delete-impact?projectId=b5&nodeId=b5-d1")
impact = json.loads(data).get("impact") if status == 200 else {}
check("批次5 删除前能看到受影响的任务数",
      status == 200 and impact.get("itemCount") == 2 and impact.get("completedCount") == 1, data[:200])

status, headers, data = call("/api/node/reorder", method="POST",
                             body={"projectId": "b5", "nodeId": "b5-i1", "parentId": "b5-d2", "position": 0})
moved = json.loads(data).get("move") if status == 200 else {}
check("批次5 拖拽排序：跨单元移动任务",
      status == 200 and moved.get("parentId") == "b5-d2"
      and moved.get("previous") == {"parentId": "b5-d1", "position": 0}, data[:220])
_, _, body = call("/api/project?id=b5")
tree = json.loads(body)["project"]["tree"]
check("批次5 移动后两边的任务列表都对",
      [node["text"] for node in tree[0]["children"][0]["children"]] == ["任务2"]
      and [node["text"] for node in tree[0]["children"][1]["children"]] == ["任务1"], body[:200])

status, headers, data = call("/api/node/reorder", method="POST",
                             body={"projectId": "b5", "nodeId": "b5-w1", "parentId": "b5-d1", "position": 0})
check_json_error("批次5 不允许把父节点拖进自己的子节点 → 400 JSON",
                 status, headers.get("Content-Type", ""), data, 400)

status, headers, data = call("/api/node/duplicate", method="POST",
                             body={"projectId": "b5", "nodeId": "b5-d1", "includeChildren": True,
                                   "keepCompletion": True, "keepAssessment": True, "keepReview": True})
dup = json.loads(data) if status == 200 else {}
check("批次5 复制任务分支（新 ID + 保留状态可选）",
      status == 200 and dup.get("node", {}).get("text") == "单元1（副本）"
      and dup["node"]["id"] != "b5-d1", data[:200])

status, headers, data = call("/api/project/duplicate", method="POST",
                             body={"projectId": "b5", "name": "批次5项目（副本）",
                                   "keepCompletion": False, "keepAssessment": False, "keepReview": False})
clone = json.loads(data).get("project") if status == 200 else {}
check("批次5 复制项目（可清空完成/AI 历史/复习）", status == 200 and clone.get("id") != "b5", data[:200])
_, _, body = call("/api/project?id=" + clone["id"])
clone_item = json.loads(body)["project"]["tree"][0]["children"][0]["children"][0]
check("批次5 副本按要求清空了进度", clone_item["completed"] is False and clone_item.get("assessment") is None
      and "review" not in clone_item, json.dumps(clone_item, ensure_ascii=False)[:200])

status, headers, data = call("/api/templates")
templates = json.loads(data).get("templates") if status == 200 else []
check("批次5 内置项目模板可用", status == 200 and len(templates) >= 2, data[:160])
status, headers, data = call("/api/project/from-template", method="POST",
                             body={"templateId": "builtin-debug-drill", "name": "排错训练"})
check("批次5 用模板创建项目", status == 200 and json.loads(data)["project"]["name"] == "排错训练", data[:160])
# 导出三种格式
status, headers, data = call("/api/export?format=md")
text = data.decode("utf-8") if status == 200 else ""
check("批次5 导出 Markdown", status == 200 and "# 学习计划导出" in text and "- [x]" in text, text[:120])
status, headers, data = call("/api/export?format=csv")
csv_text = data.decode("utf-8") if status == 200 else ""
check("批次5 导出 CSV（带 BOM 与表头）",
      status == 200 and csv_text.startswith("\ufeff") and "项目,周,单元,任务" in csv_text, csv_text[:120])
status, headers, data = call("/api/export?format=json")
check("批次5 JSON 导出仍可用", status == 200 and json.loads(data)["schemaVersion"] == 2, data[:120])
status, headers, data = call("/api/export?format=docx")
check_json_error("批次5 不支持的导出格式 → 400 JSON", status, headers.get("Content-Type", ""), data, 400)

# 导入预览与三种模式
INCOMING = [{
    "id": "b5", "name": "批次5项目（改）", "description": "改过", "createdAt": TODAY_STR,
    "assessmentEnabled": False, "reviewEnabled": False,
    "tree": [{"id": "b5-w1", "type": "week", "text": "第1周（改）", "completed": False, "expanded": False,
              "createdAt": TODAY_STR, "children": [
                  {"id": "b5-d1", "type": "day", "text": "单元1", "completed": False, "expanded": False,
                   "createdAt": TODAY_STR, "children": [
                       {"id": "b5-i1", "type": "item", "text": "任务1（改）", "completed": False,
                        "completedAt": None, "optional": False, "assessmentRequired": False,
                        "assessmentHistory": 0, "assessment": None, "createdAt": TODAY_STR, "children": []},
                       {"id": "b5-i9", "type": "item", "text": "新增任务", "completed": False,
                        "completedAt": None, "optional": False, "assessmentRequired": False,
                        "assessmentHistory": 0, "assessment": None, "createdAt": TODAY_STR, "children": []}]}]}],
}]
status, headers, data = call("/api/import/preview", method="POST",
                             body={"projects": INCOMING, "mode": "merge", "keepAiHistory": False})
preview = json.loads(data).get("preview") if status == 200 else {}
check("批次5 导入预览：新增/更新/重复/AI 历史处理方式",
      status == 200 and preview["totals"]["addedNodes"] == 1 and preview["totals"]["updatedNodes"] >= 3
      and "清空" in preview["aiHistory"]["policy"] and preview["removedProjects"] == []
      and preview["duplicates"] == [],
      json.dumps(preview, ensure_ascii=False)[:260])
status, headers, data = call("/api/import/preview", method="POST",
                             body={"projects": INCOMING + INCOMING, "mode": "merge"})
check("批次5 导入预览报出重复 ID", status == 200 and json.loads(data)["preview"]["duplicates"], data[:200])
status, headers, data = call("/api/import", method="POST",
                             body={"projects": INCOMING + INCOMING, "mode": "merge"})
check_json_error("批次5 有重复 ID 时拒绝导入 → 400 JSON", status, headers.get("Content-Type", ""), data, 400)
status, headers, data = call("/api/import", method="POST",
                             body={"projects": INCOMING, "mode": "merge", "keepAiHistory": False})
check("批次5 合并导入成功", status == 200 and json.loads(data)["mode"] == "merge", data[:160])
_, _, body = call("/api/project?id=b5")
merged_project = json.loads(body)["project"]
merged_texts = set()
def _collect(nodes):
    for node in nodes or []:
        if node["type"] == "item":
            merged_texts.add(node["text"])
        _collect(node.get("children"))
_collect(merged_project["tree"])
check("批次5 合并结果：同 ID 覆盖 + 新任务追加 + 本地独有的保留",
      {"任务1（改）", "新增任务", "任务2"} <= merged_texts,
      json.dumps(sorted(merged_texts), ensure_ascii=False)[:220])
status, headers, data = call("/api/import", method="POST",
                             body={"projects": [INCOMING[0] | {"id": "b5-new"}], "mode": "new"})
check("批次5 导入为新项目（新项目 ID）", status == 200 and json.loads(data)["mode"] == "new", data[:160])

# 回收站：恢复到原位置 / 孤立任务箱
TRASH_NODE = {"id": "b5-i2", "type": "item", "text": "任务2", "completed": True,
              "completedAt": TODAY_STR + "T08:00:00", "optional": False, "assessmentRequired": False,
              "assessmentHistory": 0, "assessment": None, "createdAt": TODAY_STR, "children": []}
# 真实流程：先从项目里删掉这个节点，再把它放进回收站，然后恢复回原位
_, _, body = call("/api/project?id=b5")
project_now = json.loads(body)["project"]
project_now["tree"][0]["children"][0]["children"] = [
    node for node in project_now["tree"][0]["children"][0]["children"] if node["id"] != "b5-i2"]
_, _, body = call("/api/project?id=b5")
call("/api/project", method="POST", body={"project": project_now,
                                          "expectedRevision": json.loads(body)["revision"]})
status, headers, data = call("/api/trash", method="POST", body={
    "action": "store", "item": {"kind": "node", "projectId": "b5", "title": "任务2",
                                "payload": TRASH_NODE, "parentId": "b5-d2", "position": 0}})
trash_id = json.loads(data)["item"]["id"] if status == 200 else ""
check("批次5 删到回收站", status == 200 and trash_id, data[:160])
status, headers, data = call("/api/trash")
items = json.loads(data)["items"] if status == 200 else []
entry = next((item for item in items if item["id"] == trash_id), {})
check("批次5 回收站标记恢复目标（原位置/孤立箱）", entry.get("restoreTarget") == "original", str(entry)[:200])
status, headers, data = call("/api/trash", method="POST", body={"action": "restore", "id": trash_id})
restored = json.loads(data) if status == 200 else {}
_, _, body = call("/api/project?id=b5")
restored_texts = [node["text"] for node in json.loads(body)["project"]["tree"][0]["children"][1]["children"]]
check("批次5 恢复到原位置（回到原来的单元）",
      status == 200 and restored.get("item", {}).get("restoredTo") == "original"
      and "任务2" in restored_texts, data[:200].decode("utf-8", "replace") + str(restored_texts)[:120])

status, headers, data = call("/api/trash", method="POST", body={
    "action": "store", "item": {"kind": "node", "projectId": "b5", "title": "孤儿任务",
                                "payload": TRASH_NODE | {"id": "b5-orphan", "text": "孤儿任务"},
                                "parentId": "不存在的父节点", "position": 0}})
orphan_id = json.loads(data)["item"]["id"] if status == 200 else ""
status, headers, data = call("/api/trash")
entry = next((item for item in json.loads(data)["items"] if item["id"] == orphan_id), {})
check("批次5 父节点不存在时标记为孤立箱恢复", entry.get("restoreTarget") == "orphan", str(entry)[:200])
status, headers, data = call("/api/trash", method="POST", body={"action": "restore", "id": orphan_id})
check("批次5 恢复到孤立任务箱",
      status == 200 and json.loads(data)["item"]["restoredTo"] == "orphan", data[:200])
_, _, body = call("/api/project?id=b5")
box = next((node for node in json.loads(body)["project"]["tree"] if node["text"] == "孤立任务箱"), None)
check("批次5 项目里出现孤立任务箱并放进了任务",
      box is not None and [node["text"] for node in box["children"]] == ["孤儿任务"], str(box)[:200])

# 设置（活动历史面板与自动归档已取消：写入仍在，面板与接口不再提供）
status, headers, data = call("/api/settings")
check("批次5 读取设置（回收站保留天数）",
      status == 200 and json.loads(data)["settings"]["trashRetentionDays"] == 7, data[:160])
status, headers, data = call("/api/settings", method="POST", body={"settings": {"trashRetentionDays": 30}})
check("批次5 修改设置", status == 200 and json.loads(data)["settings"]["trashRetentionDays"] == 30, data[:160])
status, headers, data = call("/api/settings", method="POST", body={"settings": {"trashRetentionDays": 0}})
check_json_error("批次5 非法设置 → 400 JSON", status, headers.get("Content-Type", ""), data, 400)

# --- AI 加练：出题（无答案）→ 批改（判分 + 示范解法）→ 收藏 → 列表 → 删除 ---
import os as _os
import sqlite3 as _sqlite3

def review_table_counts():
    connection = _sqlite3.connect(_os.environ["TODO_SQLITE_FILE"])
    try:
        return (connection.execute("SELECT COUNT(*) FROM review_attempts").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM review_states").fetchone()[0])
    finally:
        connection.close()

target_code = "py.mutability.default-arg"
before_counts = review_table_counts()
status, _, data = call("/api/review/ai-question", method="POST", body={"code": target_code})
question = json.loads(data).get("question") if status == 200 else {}
check("AI 加练 出题 200（mock）", status == 200 and question.get("prompt"), f"status={status} body={data[:160]}")
check("AI 加练 出题不带参考答案", "reference" not in question, str(question)[:160])
check("AI 加练 出题题型合法",
      question.get("questionType") in ("concept", "predict", "debug", "code_task"), str(question)[:160])

status, _, data = call("/api/review/ai-answer", method="POST", body={
    "code": target_code, "questionType": question.get("questionType"),
    "prompt": question.get("prompt"), "questionCode": question.get("code") or "",
    "focus": question.get("focus") or "", "answer": ""})
verdict = json.loads(data).get("verdict") if status == 200 else {}
reference = json.loads(data).get("reference") if status == 200 else {}
check("AI 加练 空作答也能批改（200 + verdict）", status == 200 and verdict, f"status={status} body={data[:200]}")
check("AI 加练 空作答必须给示范解法", bool(reference.get("reference")), str(reference)[:200])
check("AI 加练 空作答判为未通过", verdict.get("correct") is False, str(verdict)[:160])

status, _, data = call("/api/review/ai-collect", method="POST", body={
    "code": target_code, "questionType": question.get("questionType"),
    "prompt": question.get("prompt"), "questionCode": question.get("code") or "",
    "focus": question.get("focus") or "", "reference": reference})
saved_id = (json.loads(data).get("question") or {}).get("id") if status == 200 else ""
check("AI 加练 收藏 200", status == 200 and bool(saved_id), f"status={status} body={data[:200]}")

status, _, data = call("/api/review/ai-questions?code=" + urllib.parse.quote(target_code))
items = json.loads(data).get("items") if status == 200 else []
check("AI 加练 列表含刚收藏的题且不吐参考答案",
      status == 200 and any(item["id"] == saved_id for item in items)
      and all("reference" not in item for item in items), f"status={status} body={data[:200]}")

after_counts = review_table_counts()
check("临时加练零留痕：attempts/states 行数不变", before_counts == after_counts,
      f"{before_counts} -> {after_counts}")

status, _, data = call("/api/review/ai-question?id=" + urllib.parse.quote(saved_id), method="DELETE")
check("AI 加练 删除 200 且返回该点剩余列表",
      status == 200 and json.loads(data)["items"] == [], f"status={status} body={data[:200]}")
status, _, data = call("/api/review/ai-question?id=" + urllib.parse.quote(saved_id), method="DELETE")
check("AI 加练 重复删除 → 404", status == 404, f"status={status}")
status, headers, data = call("/api/review/ai-collect", method="POST", body={
    "code": target_code, "questionType": "essay", "prompt": "x", "reference": {"explain": "y"}})
check_json_error("AI 加练 非法题型 → 400 JSON", status, headers.get("Content-Type", ""), data, 400)

print(f"\n   通过 {len(passed)} 项，失败 {len(failed)} 项")
if failed:
    print("   失败项: " + ", ".join(failed))
    sys.exit(1)
PY

echo "### 4) 服务端日志（应无异常堆栈）"
if grep -q "Traceback" "$WORK/server.log"; then echo "   发现异常（完整日志）:"; cat "$WORK/server.log"; else echo "   无异常 ✔"; fi
echo "### 完成"
