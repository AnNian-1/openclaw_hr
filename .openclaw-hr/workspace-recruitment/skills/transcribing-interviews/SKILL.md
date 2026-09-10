---
name: transcribing-interviews
description: Transcribe an interview audio recording into a speaker-separated transcript. Use this skill whenever an interview recording (a WAV/audio file) needs to become a text transcript where every segment is labelled with who spoke it, so a structured interview minutes can be generated downstream. Runs FunASR Paraformer-zh for speech-to-text and CAM++ speaker-embedding clustering for speaker diarization, all in one inference — auth-free (ModelScope, no HuggingFace token), MIT-licensed, and works for 2+ speakers without configuration. It only transcribes and separates speakers — it does not summarize the interview or score the candidate.
metadata:
  openclaw:
    requires:
      bins: ["python3", "node"]
---

# transcribing-interviews

把一段面试录音转成"按发言人标注的转写稿"——每个片段都标了"是谁说的"。这是面试纪要链路的第一段，下游 `generating-minutes` 拿这份转写稿整理成结构化纪要。

## 何时用这个 Skill

收到一段面试录音（WAV 等音频文件），需要把它变成文字、并且分清每句话是谁说的时用。

它和纪要链路里另一个 Skill 边界清楚：本 Skill 只做"录音 → 按发言人组织的转写稿"，**不做纪要整理、不做评分**——把转写稿整理成关键问答 / 优劣势 / 评分建议是 `generating-minutes` 的事。

## 这个 Skill 一次跑完两件事

FunASR 的 `AutoModel` 一次推理同输出两件事，无需串接：

- **说了什么** —— ASR 转写。用 FunASR Paraformer-zh（ModelScope `iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch`，953 MB）。VAD 切片（`speech_fsmn_vad_zh-cn-16k-common-pytorch`）切长录音，PUNC 加标点（`punc_ct-transformer_zh-cn-common-vocab272727-pytorch`）。
- **谁说的** —— 说话人分离。用 CAM++ speaker embedding（`speech_campplus_sv_zh-cn_16k-common`，28 MB）算 192 维向量，余弦凝聚聚类自动决定"几个人、谁是谁"——`speaker_A` / `speaker_B` / `speaker_C` 视场景定。

"按发言人组织"是面试纪要的硬要求，所以必须 ASR + 分离一起做完。FunASR 把两步并成一次推理，比 faster-whisper + pyannote / faster-whisper + F0 这类"两条 pipeline 串接"省一半延迟和一半显存。

> **为什么不复用旧版 (faster-whisper + F0)**：旧版写死了 F0 二分，只能对一男一女双峰分得开的合成录音有效；真实面试多说话人 / 同性别相近音色直接失效。详见 §迁移历史 与 `references/diarization-method.md`。

## 工作流程

面试转写分两步，按顺序做：

### 第 1 步 · 转写 + 分离

```bash
bash scripts/recruitment-run.sh python3 skills/transcribing-interviews/scripts/transcribe_diarize.py \
  <音频文件> interview/<转写名>.json

# 强制走 CPU（如 GPU 出错时降级）
bash scripts/recruitment-run.sh python3 skills/transcribing-interviews/scripts/transcribe_diarize.py \
  <音频文件> interview/<转写名>.json --device cpu
```

模型缓存在本 workspace `models/`（`MODELSCOPE_CACHE`，约 1.3GB）。不要指向 `~/.openclaw-hr/...`（与本 profile 不是同一目录）。

- 第一个参数是面试录音，16 kHz 单声道 WAV 最佳；其它采样率也能转。
- 产物是转写 JSON，存到 `interview/` 下。Schema：`{audio, model, diarization_method, spk_campplus_used, device, batch_size_s, model_path, wall_sec, segments: [{start, end, text, spk_int, speaker}]}`。
- `--device auto` 默认行为：有 NVIDIA 卡用 `cuda:0`，否则 `cpu`。**不强制改代码**。
- `--cache` 指 MODELSCOPE 缓存；默认本 workspace `models/`。第一次会下载约 1.3GB，之后命中本地。

跑脚本需要 `exec` 工具（`group:runtime` 权限组）。

### 第 2 步 · 校验

转写产物必须用校验脚本过一遍，跑通才算转写合格：

```bash
bash scripts/recruitment-run.sh node skills/transcribing-interviews/scripts/validate_transcript.js interview/<转写名>.json
```

脚本校验：JSON 可解析、顶层字段齐全（`diarization_method` 必须是 `funasr-cam++`）、每段含 start / end / text / speaker、时间戳自洽、空文本片段占比正常、**说话人分离健康度**（至少分出 2 类 + 没有一方占比畸高 > 92%）。退出码 0 = 通过，1 = 不通过（列出全部问题），2 = 用法错误。

校验不通过就按报出的问题处理——通常是音频本身的问题（空录音、单说话人），换音频或重跑。

## 关键规则

- **说话人分离走 CAM++ speaker embedding 聚类，不用 pyannote / 基频**。pyannote 有 HuggingFace 认证墙（HF token + 接受 gated terms + 国内下载受阻），基频聚类只能二分开音高差异大的两人——两个都不适合生产面试。FunASR + CAM++ 一次推理、自动决定说话人数、零 token、MIT 协议，三难全避开。
- **CAM++ 不是固定二分**：聚类自己决定是 2 类、3 类还是 5 类。本 Skill 输出的是 `speaker_A / speaker_B / speaker_C …`，candidate 间不需要预设。多人群面 / 同性别相近音色场景不需要改任何参数。
- **ASR 中文转写有真实误差**。Paraformer-zh 在中文场景比 Whisper 稳不少，但专业术语、低频人名仍有错（实测"扣减"→"扣检"等）。下游 `generating-minutes` 的 LLM 能从上下文纠正大部分；要更高精度可在转写后加术语校正词表。
- **环境前置别忘了**：FunASR 需要单独的 conda 环境 `funasr_me`（与 `openclaw-hr` 的 numpy 2.x 不能混装）。脚本若在当前 python 找不到 funasr，会自动切到 `~/miniconda3/envs/funasr_me`（或 `FUNASR_VENV` / `--venv`）；环境不存在则退出码 3。
- **NumPy 版本锁**< 2：torch 2.2.2 是 NumPy 1.x ABI 编译的，环境装 numpy 2.x 会导致 `RuntimeError: Numpy is not available`。装环境时 `pip install "numpy<2"`。
- 转写产物是面试纪要链路的地基，校验不通过的转写稿不算转写完成，不要直接交给 `generating-minutes`。

## 本机状态（必须诚实）

conda `funasr_me` 与本 workspace `models/` **环境存在，换机后尚未补测通过**。禁止把下面课程 playground / 他机数字说成本机已验收，禁止假装转写已通过。未补测时如实告知，不要编转写稿，也不要为交差跑长音频。

## 课程 playground 记录（不是本机验收）

课程同一条 wav `interview-yuangong1-tech2.wav`（282.84 s）在教学环境曾测过：CPU 约 105 段 / RTF 0.131；GPU V100S 约 8.68s / RTF 0.031；三跑段数与文本一致。报告路径属于课程 playground，本 workspace 没有把该结果复测为现行真源。

## 迁移历史

| 版 | ASR | 说话人分离 | 退出条件 |
|---|---|---|---|
| v1（旧，已废弃）| faster-whisper small | F0 中位数二分 | TTS 双峰勉强能跑，真实面试多人/同性别/口音相近场景直接失效 |
| **v2（当前）** | **FunASR Paraformer-zh** | **CAM++ speaker embedding 凝聚聚类** | 自动决定说话人数，2 / 3 / 5 人都能用 |

v1 的 `interview/scripts/asr-diarize.py`（旧版 asr-diarize）保留作为"演示专用降级方案"，生产面试请用本 Skill 的 `transcribe_diarize.py`。

环境配置、模型下载、故障排查表、FunASR vs pyannote 详细对比见 → `references/diarization-method.md`。
