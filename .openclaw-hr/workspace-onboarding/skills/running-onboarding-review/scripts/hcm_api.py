#!/usr/bin/env python3
"""
hcm_api.py — HCM 系统 API 客户端（只读 + 节点更新）

所有入职脚本通过此模块调用 HCM API，不再直接读写本地 JSON 文件。
数据真相来源是 HCM 系统（SQLite），不是本地 stub-state/。

环境变量（二者等价，先读 URL）：
  HCM_API_URL / HCM_API_BASE — API 地址，默认 http://localhost:8000

原则：
  · GET 读取候选人数据（小慧只读）
  · 不调 POST / PUT / DELETE —— 部门节点由各部门在 HCM 维护
"""
import json
import os
import sys
import urllib.request
import urllib.error

def hcm_base():
    return (
        os.environ.get("HCM_API_URL")
        or os.environ.get("HCM_API_BASE")
        or "http://localhost:8000"
    ).rstrip("/")


HCM_API_BASE = hcm_base()


def _request(method, path, body=None):
    """发起 HTTP 请求，返回 (status_code, parsed_json)。"""
    url = f"{hcm_base()}{path}"
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        return e.code, {"error": body_text}
    except urllib.error.URLError as e:
        sys.stderr.write(f"[hcm_api] 连接失败: {url} — {e.reason}\n")
        return 0, {"error": str(e.reason)}


def fetch_candidates():
    """GET /api/candidates。成功返回 (True, list)；连不上或非 200 返回 (False, detail)。

    空花名册是 (True, [])，与「HCM 不可用」分开，避免把故障当成没人。
    """
    code, data = _request("GET", "/api/candidates")
    if code == 200 and isinstance(data, list):
        return True, data
    return False, {"http_status": code, "body": data}


def list_candidates():
    """GET /api/candidates → 候选人列表（含 prep nodes）。失败时返回 []。"""
    ok, data = fetch_candidates()
    if ok:
        return data
    sys.stderr.write(f"[hcm_api] list_candidates 失败: {data}\n")
    return []


def find_candidates(*, name=None, pinyin=None):
    """按姓名和/或拼音过滤花名册。返回 (hcm_ok, matches, error_detail)。"""
    ok, data = fetch_candidates()
    if not ok:
        return False, [], data
    matches = list(data)
    if pinyin:
        matches = [c for c in matches if c.get("pinyin") == pinyin]
    if name:
        matches = [c for c in matches if c.get("name") == name]
    return True, matches, None


def get_candidate_by_pinyin(pinyin):
    """按拼音查找候选人，返回 candidate dict 或 None。"""
    for c in list_candidates():
        if c.get("pinyin") == pinyin:
            return c
    return None


def get_candidate_by_id(candidate_id):
    """GET /api/candidates/{id} → candidate dict 或 None。"""
    code, data = _request("GET", f"/api/candidates/{candidate_id}")
    if code == 200:
        return data
    return None


def get_prep_node(pinyin, node_type):
    """获取指定候选人的某个 prep node，返回 node dict 或 None。"""
    candidate = get_candidate_by_pinyin(pinyin)
    if not candidate:
        return None
    for node in candidate.get("nodes", []):
        if node.get("node_type") == node_type:
            return node
    return None


def get_prep_node_data(pinyin, node_type):
    """获取指定候选人的某个 prep node 的 data 字段，返回 dict 或空 dict。"""
    node = get_prep_node(pinyin, node_type)
    if node:
        return node.get("data", {})
    return {}


def get_candidate_info(pinyin):
    """获取候选人基本信息（姓名、岗位、薪资），返回 dict。

    优先从 HCM API 读取；若 API 不可用，回退到 workflow.json。
    """
    candidate = get_candidate_by_pinyin(pinyin)
    if candidate:
        return {
            "name": candidate.get("name", pinyin),
            "pinyin": candidate.get("pinyin", pinyin),
            "role": candidate.get("role", ""),
            "salary": candidate.get("salary", ""),
            "status": candidate.get("status", ""),
        }
    return None


if __name__ == "__main__":
    # 简易测试：列出所有候选人
    candidates = list_candidates()
    for c in candidates:
        nodes_summary = ", ".join(
            f"{n['node_type']}={n['status']}" for n in c.get("nodes", [])
        )
        print(f"{c['name']} ({c['pinyin']}) — {c['status']} | {nodes_summary}")
