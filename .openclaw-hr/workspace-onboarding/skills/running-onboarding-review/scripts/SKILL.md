---
name: running-onboarding-review
description: Scripts companion. Canonical instructions are in the parent SKILL.md.
---

# running-onboarding-review / scripts

本目录脚本实现父级 `../SKILL.md`。要点：

- 五部门节点：HCM GET，只读。
- 跟进表：`review-state/reviews.json`。
- **开通跟进**：`sync-reviews-if-ready.sh <姓名> <pinyin>`（五节点全绿才 ensure + 挂 Cron）。
- **查询**：`onboarding-review.sh` 不 ensure；未开通时 `action=not_armed`。
- **确认**：`review-store.sh mark-done`。不要直接调用 `schedule-onboarding-reviews.sh` 除非已经确认五节点 completed。
