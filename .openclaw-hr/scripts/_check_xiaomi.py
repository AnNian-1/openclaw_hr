from pathlib import Path
import re
t = Path("/home/hr/.openclaw-hr/env.sh").read_text()
m = re.search(r"^export XIAOMI_API_KEY=(.*)$", t, re.M)
if not m:
    print("XIAOMI_API_KEY missing")
else:
    v = m.group(1).strip().strip('"').strip("'")
    print("XIAOMI_API_KEY empty" if not v else "XIAOMI_API_KEY set")
