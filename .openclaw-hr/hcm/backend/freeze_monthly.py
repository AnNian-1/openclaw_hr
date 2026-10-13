#!/usr/bin/env python3
"""HCM 内部冻结 CLI。同一 period 幂等返回既有 run。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import SessionLocal  # noqa: E402
from schema_migrate import migrate_schema  # noqa: E402
from monthly_metrics import freeze_period  # noqa: E402
import models  # noqa: F401,E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="冻结 HCM 月报快照")
    p.add_argument("--period", required=True, help="YYYY-MM")
    args = p.parse_args(argv)
    migrate_schema()
    db = SessionLocal()
    try:
        payload = freeze_period(db, args.period)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    finally:
        db.close()
    print(json.dumps({"report_run_id": payload["report_run_id"], "month": payload["month"], "source": "HCM"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
