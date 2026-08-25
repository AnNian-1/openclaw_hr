# transcribing-interviews 评测场景

> 评测驱动开发（方法基线 §五）：先建评测场景，测"没有 Skill 时的基线表现"，再写最小 SKILL.md，按观察迭代。
> 评测对象：把一段面试录音转成"按发言人标注的转写稿"——每段都标 speaker_A / speaker_B (或更多说话人)。

## 评测场景

### 场景 1 · 标准面试录音（一男一女，音高差异明显）

- 输入：`interview/interview-zhanglei-tech2.wav`（282.8s / 16kHz 单声道，面试官女声 + 候选人低音调，TTS 造的模拟二面录音）
- query：把这段面试录音转成按发言人组织的转写稿
- expected_behavior：
  - FunASR + Paraformer-zh 转写成功，产出 ~105 个片段
  - 说话人分离把片段分成 speaker_A / speaker_B 两类，且两类都有相当数量片段（不是一方占绝对多数）
  - 产物 JSON 顶层含 `audio / model / diarization_method / spk_campplus_used / device / batch_size_s / wall_sec / segments`
  - `diarization_method == "funasr-cam++"`
  - 每段含 `start / end / text / spk_int / speaker`
  - `validate_transcript.js` 校验退出码 0

### 场景 2 · 多人面试录音（3 人及以上）

- 输入：3 人及以上的群面录音
- query：把这段面试录音转成按发言人组织的转写稿
- expected_behavior：
  - CAM++ 自动聚类，输出 **3 个或更多说话人**（speaker_A / speaker_B / speaker_C 等）
  - 不需要预设 `--num-speakers`，脚本自动决定
  - `validate_transcript.js` 校验退出码 0

### 场景 3（边界）· 说话人分离失败——所有片段归一类

- 输入：一份 `speaker` 字段被全部改成同一值的转写 JSON（模拟 CAM++ 对"完全同音色双胞胎"失灵）
- query：校验这份转写产物是否合格
- expected_behavior：
  - `validate_transcript.js` 报"说话人分离只分出 1 类"或"单一说话人占比过高"
  - 退出码 1，不放行
  - 这是本 Skill 的真实边界——CAM++ 聚类也只在 speaker embedding 距离可分时有效

### 场景 4（边界）· 旧版产物混进新版校验器

- 输入：一份 `diarization_method: "f0-clustering"` 的旧版转写 JSON（faster-whisper + F0 时代的产物）
- query：用新版 `validate_transcript.js` 校验
- expected_behavior：
  - 校验器识别旧版 schema，主动报错 `diarization_method=f0-clustering 是旧版 (faster-whisper + F0) 输出, 请改用新版 FunASR + CAM++ 重新跑 transcribe_diarize.py`
  - 退出码 1，避免把废弃产物继续往 `generating-minutes` 推

### 场景 5（边界）· 空转写——录音无人声

- 输入：一份 `segments` 为空数组的转写 JSON（模拟空录音 / 纯静音音频）
- query：校验这份转写产物是否合格
- expected_behavior：
  - `validate_transcript.js` 报 "segments 为空"，退出码 1
  - 转写脚本本身遇到无片段会直接退出码 1，不产出空产物

### 场景 6（边界）· 输入音频文件不存在

- 输入：一个不存在的音频路径
- query：转写这段录音
- expected_behavior：
  - `transcribe_diarize.py` 报"音频文件不存在"，退出码 2
  - 不产出垃圾产物

### 场景 7（边界）· funasr 未装且没给 --venv

- 输入：默认 python（无 funasr 的 system python） + 没传 --venv
- query：转写一段录音
- expected_behavior：
  - `transcribe_diarize.py` 报 `[error] funasr 未装, 见 SKILL.md §环境前置 安装; 或用 --venv <venv-path> 指定已装的虚拟环境`
  - 退出码 3（EX_NOINPUT）
  - 引导用户 conda activate funasr_me 或用 --venv 路径切换环境

### 场景 8（边界）· NumPy ABI 不兼容

- 输入：funasr_me 环境装了 numpy 2.x + torch 2.2.2
- query：跑转写
- expected_behavior：
  - FunASR AutoModel 加载时/推理时报 `RuntimeError: Numpy is not available`
  - 修复：`pip install "numpy<2"`（torch 2.2.2 是 NumPy 1.x ABI 编译）
  - 这条边界写在 `references/diarization-method.md §6.3` 的"已知坑"表里

### 场景 9（一致性）· CPU/GPU 三跑一致

- 输入：同一条 wav，连续跑 3 次，每次换 CPU / GPU 切换
- query：跑转写
- expected_behavior：
  - 三次产物 `segments.length` 完全一致（如 105 段）
  - 每段 `text` 逐字符 0 差
  - 说话人 A/B 段数比例一致（如 31/74）
  - 差异仅在 `device` 字段（cpu vs cuda:0）和 `wall_sec`（CPU 37s / GPU 8.7s）
  - 报告见 `playground/1.step_6_arc/reports/cpu-vs-gpu.md`

## 基线测试（没有 Skill 时）

见实验记录 `exp-stage-c4-skillified.md` CP1 · 步骤 2。

基线痛点（v1 时代）：没有这个 Skill，转写就退化成"人在消息里硬写一长串命令"——指定 faster-whisper、指定模型、指定 venv、再讲清楚怎么做基频聚类分离、产物结构应该长什么样。这一整套上下文每次都要重抄，而且没有任何校验闸——产出一份说话人全归一类的废转写稿，靠人事后才发现。

v2 升级带来的评测增强：

- **自动说话人人数**：v1 写死二分，v2 让 CAM++ 自己聚类，评测场景 2 直接验证"3 人也能跑"——v1 时代这个场景根本写不出来，因为 F0 聚类不可能分 3 类。
- **跨设备一致性**：v1 全 CPU 路径，没有"同一条 wav 三跑一致"的硬性指标。v2 的评测场景 9 强制要求三跑输出严格一致——FunASR 的 `batch_size_s` 是唯一有非确定性的地方，但凝聚聚类稳定，三跑一致是 FunASR 的真实表现。