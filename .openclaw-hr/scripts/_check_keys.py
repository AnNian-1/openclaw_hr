from pathlib import Path
import re

keys = [
    "DEEPSEEK_API_KEY",
    "XIAOMI_API_KEY",
    "SILICONFLOW_API_KEY",
    "DASHSCOPE_API_KEY",
    "OPENCLAW_GATEWAY_TOKEN",
    "FEISHU_APP_SECRET",
    "VOLCANO_ENGINE_API_KEY",
    "VOLCANO_DEEPSEEK_API_KEY",
]
files = [
    Path("/home/hr/.openclaw-hr/env.sh"),
    Path("/root/hr_claw_hub/openclaw-hr/env.sh"),
    Path("/root/hr_claw_hub/playground/0.step_deployer_hr_system/configs/env.sh"),
    Path("/home/annian/hr_claw_hub/playground/1.step_A_pre_env_test/openclaw-hr_20260711_backup/env.sh"),
    Path("/root/hr_claw_hub/playground/1.step_A_pre_env_test/openclaw-hr_20260711_backup/env.sh"),
]
print("=== files exist ===")
for p in files:
    print(f"{p} exists={p.exists()} size={p.stat().st_size if p.exists() else 0}")

print("=== keys in /home/hr/.openclaw-hr/env.sh ===")
text = Path("/home/hr/.openclaw-hr/env.sh").read_text()
for k in keys:
    ms = list(re.finditer(rf"^export {k}=(.*)$", text, re.M))
    if not ms:
        print(f"{k}: missing")
        continue
    v = ms[-1].group(1).strip().strip('"').strip("'")
    placeholder = v in {"", "sk-...", "replace-with-random-token", "...", "tp-..."}
    print(f"{k}: {'placeholder-or-empty' if placeholder else 'set'} len={len(v)}")
