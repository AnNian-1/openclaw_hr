---
name: office-to-md
description: Convert PDF/DOC/DOCX/PPTX resumes to Markdown. Use when an incoming resume is an office document and must become Markdown before parsing-resumes. Does not extract structured candidate fields — that is parsing-resumes.
metadata:
  openclaw:
    requires:
      bins: ["node"]
---

# office-to-md

把 PDF / DOC / DOCX / PPTX 转成 Markdown。这是简历处理流水线的格式转换环，不做结构化抽取。

## 何时用

收到的简历是办公文档，需要先变成 Markdown 再交给 `parsing-resumes`。本来就是 `.md` 则跳过。

## 怎么调

```bash
bash scripts/recruitment-run.sh node skills/office-to-md-v2/office-to-md/openclaw-skill.js inbox/<文件>.pdf
```

同目录会写出 `<文件>.md`。转换器在嵌套目录 `office-to-md/`；本文件必须带 YAML frontmatter 且位于 Skill 第一层，否则 `skills list` 扫不到（课程活反例：外层 SKILL.md 缺 frontmatter 等于能力不存在）。

## 边界

- 只做格式转换，不抽取候选人字段、不评分、不收邮件。
- 依赖 `node` 与该目录已安装的 npm 包；不要在 exec 里 `npm install`。
