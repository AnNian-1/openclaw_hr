#!/usr/bin/env python3
# 合同：同人覆盖 / 同名异号 / 无电话交 HR / 无意向栏待确认。不调 LLM。
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_resumes as fr  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        inbox = ws / "inbox"
        inbox.mkdir()
        (ws / "parsed").mkdir()
        (ws / "scoring").mkdir()
        text_a = "姓名：张伟\n电话：13812345678\n目标岗位：后端开发\n"
        text_b = "姓名：张伟\n电话：13900001111\n目标岗位：后端开发\n"
        text_upd = "姓名：张伟\n电话：13812345678\n目标岗位：后端开发\n更新了项目经历\n"
        text_no_phone = "姓名：张伟\n目标岗位：后端开发\n"
        text_no_intent = "姓名：陈朝浩\n电话：13700000000\n专业：大数据技术\n自我评价：想做设计\n"

        s, k = fr._land_one_resume(
            data=b"%PDF-fake-a", ext=".pdf", orig_label="a.pdf",
            resume_text_full=text_a, name="张伟", llm_position="后端开发",
            method="test", content_sha="aaa", inbox_dir=inbox,
        )
        assert s and not k, (s, k)
        name1 = s[0].saved_name
        (ws / "parsed" / f"{Path(name1).stem}.json").write_text("{}", encoding="utf-8")
        (ws / "scoring" / f"clean-{Path(name1).stem}.json").write_text("{}", encoding="utf-8")
        (ws / "scoring" / f"score-{Path(name1).stem}.json").write_text("{}", encoding="utf-8")

        s2, k2 = fr._land_one_resume(
            data=b"%PDF-fake-b", ext=".pdf", orig_label="b.pdf",
            resume_text_full=text_b, name="张伟", llm_position="后端开发",
            method="test", content_sha="bbb", inbox_dir=inbox,
        )
        assert s2 and not k2, "同名异号应作为第二人落盘"
        assert s2[0].saved_name != name1

        s3, k3 = fr._land_one_resume(
            data=b"%PDF-fake-upd", ext=".pdf", orig_label="upd.pdf",
            resume_text_full=text_upd, name="张伟", llm_position="后端开发",
            method="test", content_sha="ccc", inbox_dir=inbox,
        )
        assert s3 and "overwrite" in s3[0].reason
        assert not (ws / "parsed" / f"{Path(name1).stem}.json").exists()
        assert not (ws / "scoring" / f"clean-{Path(name1).stem}.json").exists()
        pipe = (inbox / "needs-pipeline.jsonl").read_text(encoding="utf-8")
        assert "reparse-score" in pipe

        s4, k4 = fr._land_one_resume(
            data=b"%PDF-fake-np", ext=".pdf", orig_label="np.pdf",
            resume_text_full=text_no_phone, name="张伟", llm_position="后端开发",
            method="test", content_sha="ddd", inbox_dir=inbox,
        )
        assert s4 and not k4, "不确定身份也应落盘走流程"

        s5, k5 = fr._land_one_resume(
            data=b"%PDF-fake-ch", ext=".pdf", orig_label="ch.pdf",
            resume_text_full=text_no_intent, name="陈朝浩", llm_position="设计师",
            method="test", content_sha="eee", inbox_dir=inbox,
        )
        assert s5 and "待确认" in s5[0].saved_name
        q = (inbox / "needs-hr.jsonl").read_text(encoding="utf-8")
        assert "position-uncertain" in q
        assert "identity-ambiguous" in q

        print("test_hr_contract: ok")
        print("inbox", [p.name for p in inbox.iterdir() if p.suffix == ".pdf"])
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
