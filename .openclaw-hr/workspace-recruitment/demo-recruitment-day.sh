#!/bin/bash
# ============================================================
# 招聘子 Agent · HR 一天三场景端到端演示
#   把 Lesson 2-1 §7 端到端实战的三场景命令收成一个可一键运行的脚本。
#   场景一 批量筛简历 + 候选人画像 / 场景二 人才库语义检索 / 场景三 面试纪要
# 用法：
#   bash demo-recruitment-day.sh
# 前置条件：
#   - ~/.openclaw-hr/ 已配好 recruitment 子 Agent（见 §2-§6）
#   - faster-whisper 已装在 ~/.openclaw-hr/venv-asr
#   - ~/.openclaw-hr/env.sh 里有 DEEPSEEK_API_KEY
# ============================================================
set -e
cd ~/.openclaw-hr/workspace-recruitment

# DeepSeek / 通义 都是国内可直连的 API：载入密钥并清掉代理变量，
# 避免请求被本机 HTTP 代理拦截。
source ~/.openclaw-hr/env.sh
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY

echo "===== 场景一 · 批量筛简历 + 候选人画像 ====="
# 复用 C-2 数字回核修正版评分结果，展示 7 名 tech 候选人按 JD 匹配分排序
python3 scoring/show_ranking.py scoring/results/ranking-后端开发.json
# 为「强匹配 / 偏科 / 带硬伤」3 名典型候选人各生成一份 HTML 画像
for N in 员工1; do
  python3 profile/generate_profile.py \
    scoring/results/ranking-后端开发.json "$N" "profile/output/demo-$N.html"
done

echo "===== 场景二 · 人才库语义检索「再来一个像员工1的」====="
python3 talent-pool/search.py --like 员工1 --topn 5
python3 talent-pool/explain.py --search talent-pool/search-员工1.json

echo "===== 场景三 · 面试录音 → 转写说话人分离 → 结构化纪要 ====="
~/.openclaw-hr/venv-asr/bin/python3 interview/scripts/asr-diarize.py \
  interview/interview-yuangong1-tech2.wav interview/transcript-h1.json
python3 interview/scripts/gen-minutes.py \
  interview/transcript-h1.json inbox/resume-tech-01-员工1-后端开发.md \
  interview/minutes-h1.json interview/minutes-h1.md

echo "===== 三场景演示完成 ====="
echo "产出物："
echo "  评分排序  scoring/results/ranking-后端开发.json"
echo "  HTML 画像 profile/output/demo-员工1.html"
echo "  检索结果  talent-pool/search-员工1-explained.json"
echo "  面试纪要  interview/minutes-h1.md"
