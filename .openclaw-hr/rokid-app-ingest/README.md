# 乐奇眼镜上传服务

独立进程，默认 listen `0.0.0.0:18791`。眼镜 Bearer 用 `ROKID_APP_INGEST_SECRET`，**不是** Gateway token。不要把龙虾配对码（`ROKID_LINK_*`）写进 yaml 或本服务。

- `GET /rokid-app/v1/health` 必须带 `Authorization: Bearer …`
- `POST /rokid-app/v1/inbound`：`multipart/form-data`（`device_id`、`type`、可选 `text` / `file` / `client_msg_id`）
- 契约以 `server.py` 与 `test_server.py` 为准

落盘后通知 Gateway：

```bash
openclaw agent --agent router --session-id rokid-app-<device_id> --json --timeout 180 -m "..."
```

会话键 `agent:router:explicit:rokid-app-<device_id>`，与龙虾桥通道分开。媒体在 `workspace-router/media/rokid-app/`（gitignore）。Gateway 未起时文件仍会留下，回复「已存、Agent 未达」。

```bash
source "$PROFILE/env.sh"
bash "$PROFILE/scripts/rokid-app-ingest.sh" start   # 或 run（前台）
curl -sS -H "Authorization: Bearer $ROKID_APP_INGEST_SECRET" \
  http://127.0.0.1:18791/rokid-app/v1/health
python3 "$PROFILE/rokid-app-ingest/test_server.py"
```

不要用本目录去启动 Gateway / HCM / Canvas。
