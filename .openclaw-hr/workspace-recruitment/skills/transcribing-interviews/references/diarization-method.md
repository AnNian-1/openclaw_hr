# 面试转写与说话人分离方法（FunASR + CAM++）

> transcribing-interviews Skill 的转写与分离逻辑细则。SKILL.md 在需要时引用本文件。

## 目录

- 1. 两段任务一次跑完：FunASR Paraformer-zh + CAM++
- 2. 为什么转写用 FunASR Paraformer-zh，不用 faster-whisper / Whisper
- 3. 为什么说话人分离用 CAM++，不用 pyannote / 基频聚类
- 4. CAM++ 怎么"自动决定"说话人数量
- 5. 转写的真实误差 + 改进路径
- 6. 环境前置 + 已知坑

## 1. 两段任务一次跑完

面试纪要要"按发言人组织"，所以转写录音要同时回答两个问题：

- **说了什么** —— ASR（自动语音识别）。
- **谁说的** —— 说话人分离（diarization），给每段打说话人标签。

`transcribe_diarize.py` 一次推理同输出：

```
面试录音 → FunASR AutoModel (VAD → ASR → PUNC → CAM++ speaker embedding → 聚类)
         → 一份 JSON:
           segments: [
             {start, end, text, spk_int, speaker}
           ]
```

ASR 用 **Paraformer-zh**（ModelScope `iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch`，~953 MB），说话人分离用 **CAM++**（`iic/speech_campplus_sv_zh-cn_16k-common`，~28 MB）。中间夹 **VAD**（`speech_fsmn_vad_zh-cn-16k-common-pytorch`，3.9 MB）切长录音 + **PUNC**（`punc_ct-transformer_zh-cn-common-vocab272727-pytorch`，283 MB）加标点。

## 2. 为什么转写用 FunASR Paraformer-zh，不用 faster-whisper

**funasr / Paraformer-zh 的优势**：

- **中文首选**：在 ModelScope 中文公开榜单上的 CER（字错率）显著好于 Whisper / faster-whisper。Whisper 是英文/多语种派生模型，对中文数字量级（"80 万行" / "12.8 万 TPS"）、专业术语（"扣减" / "履约"）、中文姓名（"员工1"）的鲁棒性差一截。
- **免认证**：模型从 ModelScope 国内直下载，零 token，零用户协议——比 HuggingFace 系模型（whisper / pyannote）省一道认证墙。
- **本地运行**：转写全程在本机，面试录音不出本地——招聘场景的硬要求（候选人是隐私数据源）。
- **MIT 协议**：可以商用、可以改、可以嵌入本 Skill 分发，没有 CC-BY-4.0 gated terms 那道坎。

**faster-whisper 的真实痛点**：

- `small` 模型在中文场景把"员工1"听成"张蕾"、"80 万行"听成"80 万型"、"扣减"听成"扣检"是结构性问题——这不致命（下游 LLM 能从上下文纠），但每一处都要花一次纠错的 token 开销。
- `medium` / `large-v3` 中文好一点，但前者在 CPU 上慢 ~3 倍，后者在国内下载不稳定、显存吃紧。
- 即使换 `large-v3`，仍需面对说话人分离这道独立的难关（见 §3）。

**实测对比**（同一条 wav `interview-yuangong1-tech2.wav`，282.84 s）：FunASR + Paraformer-zh 在 CPU 上 RTF = 0.131（7.6× 实时），GPU (V100S) RTF = 0.031（32.6× 实时），三跑 v1/v2/v3 输出严格确定（105 段、说话人 A=31 / B=74、文本逐字 0 字符差）。详见 `playground/1.step_6_arc/reports/cpu-vs-gpu.md`。

## 3. 为什么说话人分离用 CAM++，不用 pyannote-audio / 基频聚类

**CAM++ 的关键能力**：speaker embedding + 凝聚聚类自动决定"几个人、谁是谁"——不是预设分几类。

### pyannote-audio 为什么不行

pyannote-audio 3.x 是业界标准方案，但它在国内环境有三道坎：

1. **HuggingFace token**：模型页面上有 gated terms，必须用 HF 账号登录 + 手动点"Accept"接受协议。
2. **国内下载受阻**：HuggingFace 国内 CDN 不稳定，模型动辄几百 MB、断点续传经常挂。
3. **CC-BY-4.0 协议**：商用需要看仔细，对二开分发不友好。

本 Skill 选 FunASR + CAM++ 就是绕开这三道坎——ModelScope 国内直连、零 token、MIT 协议。

### 基频（F0）聚类为什么不行

旧版（v1 实现）用 F0 中位数把转写片段二分成 `speaker_A` / `speaker_B`。它只能对付**两人音高差异明显**的合成录音——比如本课自己用 TTS 造的 demo（女面试官 220-246 Hz vs 男候选人 110-122 Hz）。

**真实面试基本不用**：

- **同性别相近音色**的面试官和候选人，F0 都在同一区间，中位数阈值切不开——validate 会因"单一说话人占比 > 92%"拒收；
- **三人及以上的群面**，F0 写死了二分，分不出第三个人；
- **同一个人音高波动大**（激动时拉高、平静时压低），可能被错切到两类里。

### CAM++ 的对照表（pyannote vs FunASR + CAM++）

| 维度            | pyannote-audio 3.x        | **FunASR 1.3.14 + CAM++**               |
| ------------- | ------------------------- | -------------------------------------- |
| 协议            | CC-BY-4.0（需接受 gated terms） | **MIT（ModelScope）**                       |
| 模型下载          | HuggingFace（国内受限）          | **ModelScope（国内直连）**                       |
| 部署 token      | 必须 HF token + 同意用户协议    | **无需任何 token**                              |
| ASR + 说话人分离 | 两条 pipeline 串接           | **一次推理联合输出字幕 + speaker 标签**                     |
| 中文支持          | whisper 派生 + pyannote 通用  | **Paraformer-zh + CAM++ 都针对中文优化**              |
| 多说话人          | 支持但需手动调 num_speakers   | **CAM++ 自动决定，无需预设**                           |
| 模型体积          | 数 GB                    | **Paraformer-zh 953 MB + CAM++ 28 MB**     |

## 4. CAM++ 怎么"自动决定"说话人数量

CAM++ (`speech_campplus_sv_zh-cn_16k-common`) 工作流：

1. **算 192 维 speaker embedding**：对每个 VAD 切出的语音片段，用 CAM++ 模型算一个 192 维向量（speaker fingerprint）。
2. **计算余弦相似度**：两两算余弦相似度，组成相似度矩阵。
3. **凝聚聚类**：从每个片段各成一类开始，按相似度由低到高逐级合并——超过余弦阈值就合并到同一说话人。**聚类自己决定合并几次**——2 说话人就分 2 类、3 说话人就分 3 类、不需要预设。
4. **重新标号**：给每个聚类一个 `spk` 整数（0 / 1 / 2 ...），最后输出时按 `chr(65 + spk)` 映射到 `speaker_A / speaker_B / speaker_C`，下游不需要知道 spk 整数语义。

这套机制换到录音长度 / 说话人数量 / 音高差异都不会失效——只要每人的声纹 embedding 在相似度空间里能分开，CAM++ 就能聚开。

**边界**：非常相近的同性别两人（如双胞胎面试官），embedding 距离可能落在阈值附近，导致某些片段被错分。在 `validate_transcript.js` 的健康度检查里会被拦下（"单一说话人占比 > 92%" 或 "说话人分离只分出 1 类"），不会偷偷放过。

## 5. 转写的真实误差 + 改进路径

FunASR Paraformer-zh 在中文场景比 Whisper 稳，但不是 100% 准确。已知误差形态：

- **数字量级**："80 万行"偶尔听成"80 万航"——下游 `generating-minutes` 的 LLM 会从上下文纠回（"行" vs "航" 在"代码行数"语境里能区分）。
- **专业术语**：低频术语（如"履约"、"扣减" vs "扣检"）在 fast-talk 段可能有 1-2 字错。
- **中文姓名**：训练数据覆盖度高的名字稳，生僻名偶尔错。

**改进路径**：

- **换更大的 Paraformer**：`speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch` 已经是 large 等级；想更高精度可跑 SenseVoiceSmall（多语种），但牺牲中文领域知识。
- **加术语校正词表**：生产环境可在转写后加一个 postprocessing，常见术语和人名用词表强匹配修正。
- **数字回核兜底**：下游 `generating-minutes` 已经对候选人口述数字做了回核（候选人说 "12.8 万 TPS" → 对照原简历找 → 找不到标"需人工核实"）——纪要里数字错一对照样会被卡。

## 6. 环境前置 + 已知坑

### 6.1 安装 (一次)

```bash
# 1. conda 环境
conda create -n funasr_me python=3.10 -y
conda activate funasr_me

# 2. PyTorch (自动检测 GPU/CPU; 有 NVIDIA 卡走 cu121, 否则 cpu)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

# 3. NumPy 锁版本 (torch 2.2.2 是 NumPy 1.x ABI 编译)
pip install "numpy<2"

# 4. FunASR + ModelScope
pip install funasr modelscope
```

### 6.2 模型本地缓存

模型首次运行会自动从 ModelScope 下到 `MODELSCOPE_CACHE`。本 Skill 默认走：

```
~/.openclaw-hr/workspace-recruitment/models/
├── iic--punc_ct-transformer_zh-cn-common-vocab272727-pytorch/        283 MB
├── iic--speech_campplus_sv_zh-cn_16k-common/                          28 MB
├── iic--speech_fsmn_vad_zh-cn-16k-common-pytorch/                    3.9 MB
└── iic--speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch/  953 MB
```

要切到其他缓存目录用 `--cache <dir>`。

### 6.3 已知坑

| 现象                                              | 原因                                            | 修正                                                |
| ----------------------------------------------- | --------------------------------------------- | ------------------------------------------------- |
| `[transformers] Disabling PyTorch because PyTorch >= 2.4 is required but found 2.2.2+cu121` | transformers 检测到 torch < 2.4，不让加载 transformers | **无害**——FunASR 不需要 transformers，本警告可忽略                |
| `[error] Numpy is not available`                | torch 2.2.2 是 NumPy 1.x ABI 编译、env 装的是 2.x | `pip install "numpy<2"`                            |
| `[error] CUDA available: False 但机器有卡`            | torch 是 CPU 版 (常见于先装 CPU 又装 CUDA 混装)      | `pip uninstall -y torch torchaudio && pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121` |
| `RuntimeWarning: divide by zero / overflow ...` | FunASR 处理静音帧的无害告警                            | **忽略**                                            |
| `[error] auto model record not found` (404)    | VAD 模型 ID 写错（老 ID `speech_fsmn_vad_zh-cn-16k-common` 已改名） | 改 `MODELS["vad"]` 为 `iic/speech_fsmn_vad_zh-cn-16k-common-pytorch` |
| FunASR `import` 时 `[transformers] PyTorch was not found` | 同 1 — transformers 嫌弃 torch 版本           | **无害**                                            |
| `RuntimeError: CUDA out of memory`             | 模型 + 中间激活塞不下显存                              | 临时切 CPU: `--device cpu`；或调小 `batch_size_s`           |
| `ffmpeg is not installed` warning              | FunASR 优先用 ffmpeg 读音频，没装就退到 torchaudio     | **无害**——16 kHz WAV torchaudio 直接读                     |
| `--venv` 重递归                                  | `--venv` 参数没被剥                                | 已在 `reexec_in_venv` 里 `--venv <value>` 这两 token 一并剥掉        |

环境装好后的 smoke test 详见 `playground/1.step_6_arc/README-funasr-setup.md`。
