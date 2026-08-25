#!/usr/bin/env python3
# 读取 openclaw config get agents 的 JSON，打印每个子 Agent 的隔离情况
import sys, json
d = json.load(sys.stdin)
print("子 Agent       workspace                    agentDir")
print("-" * 70)
for a in d["list"]:
    aid = a["id"]
    ws = a.get("workspace", "(default)")
    ad = a.get("agentDir", "(default)")
    ws_short = ws.split("/")[-1] if ws != "(default)" else ws
    ad_short = ad.split("/")[-1] if ad != "(default)" else ad
    print("{:14} {:28} {}".format(aid, ws_short, ad_short))
