#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transcribe_diarize.py — FunASR + CAM++ 面试录音转写 + 说话人分离

transcribing-interviews Skill 的核心脚本。把一段面试录音转成"按发言人组织
的转写稿"，给下游的 generating-minutes 用。

两步合一次推理跑完:
  1. 转写:    FunASR Paraformer-zh (ModelScope iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch)
              + VAD (iic/speech_fsmn_vad_zh-cn-16k-common-pytorch) 切片
              + PUNC (iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch) 加标点
  2. 说话人分离: CAM++ speaker embedding
              (iic/speech_campplus_sv_zh-cn_16k-common) 算 192 维 embedding,
              凝聚聚类按余弦相似度自动决定"几个人、谁是谁"——不是固定二分.

为什么换 FunASR + CAM++, 不再用 faster-whisper + 基频聚类:
  - HuggingFace 认证墙: pyannote-audio 需 HF token + 接受用户协议, 国内下载
    也受阻; faster-whisper 在中文场景稳定性不如 Paraformer-zh.
  - F0 聚类边界: 只对音高差异明显的两说话人有效, 真实多人/同性别相近音色/口
    音相近场景直接失效——基频聚类写死了二分 (speaker_A / speaker_B), 不
    知道是几个人也不会自适应.
  - FunASR 全部跑在 ModelScope 上 (MIT, 国内直下载, 零 token), CAM++ 是
    speaker embedding 聚类, 自动决定说话人数量, 多人场景直接能用.

CLI:
  python3 transcribe_diarize.py <audio.wav> <out.json> [--device auto|cpu|cuda:0]
                                                          [--cache <models-dir>]
                                                          [--batch-size-s 10]
  audio.wav          面试录音 (16kHz 单声道 WAV 最佳, 其他采样率也能转)
  out.json           转写 + 分离结果输出路径
  --device           auto (默认, torch.cuda.is_available 自动选择)
                     / cpu / cuda:0
  --cache            MODELSCOPE 缓存目录 (默认 ~/.openclaw-hr/workspace-recruitment/models)
                     → 该目录下须有 iic/speech_* 的 4 个模型 (VAD/PUNC/Paraformer-zh/CAM++)
                     → 第一次运行会自动下, 之后命中本地缓存
  --batch-size-s     流式切段时长, 默认 10s (FunASR 内部按此切段送推理)

环境约定:
  - Python 环境: conda activate funasr_me
                 (或自建 venv, 但要 pip install funasr modelscope torch torchaudio
                  + pip install "numpy<2" 防 torch 2.2.2 ABI 报错)
  - 若当前 python 没装 funasr, 用 --venv <path-to-venv/bin/..> 让脚本自动切环境

退出码:
  0 = 转写 + 分离成功
  1 = FunASR 调用失败 (模型加载/generate 失败)
  2 = 用法 / 文件错误
  3 = 依赖不满足且无 --venv (脚本不会自己重跑到别的环境; 必须显式 --venv)
"""
import argparse
import json
import os
import sys
from pathlib import Path


# 模型注册表 — 4 个核心模型来自 ModelScope, 落地后路径形如
#   ~/.openclaw-hr/workspace-recruitment/models/iic--speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch/
MODELS = {
    "asr_paraformer": "iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
    "vad":            "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",  # 注意 -pytorch 后缀 (老 ID 404)
    "punc":           "iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
    "spk_campplus":   "iic/speech_campplus_sv_zh-cn_16k-common",
}


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="FunASR + CAM++ 转写 + 说话人分离 (transcribing-interviews)")
    p.add_argument("audio", type=str, help="输入 WAV 路径")
    p.add_argument("out_json", type=str, help="输出 JSON 路径")
    p.add_argument("--device", default="auto",
                   help="auto (默认, 自动检测 GPU) | cpu | cuda:0")
    p.add_argument("--cache", default=None,
                   help="MODELSCOPE 缓存目录 (默认 ~/.openclaw-hr/workspace-recruitment/models)")
    p.add_argument("--batch-size-s", type=int, default=10,
                   help="流式分段秒数 (default: 10)")
    p.add_argument("--venv", default=None,
                   help="若 funasr 没装在当前 python, 指向 <venv>/bin/python 让脚本重跑")
    return p.parse_args(argv)


def reexec_in_venv(venv, argv):
    """funasr 不在当前 python, 用指定 venv 的 python 重跑自己 (避免无限递归)."""
    if venv.endswith("bin"):
        py = os.path.join(venv, "python3")
    else:
        py = os.path.join(venv, "bin", "python3")
    if not os.path.isfile(py):
        sys.stderr.write(f"[error] --venv 指定的虚拟环境无 python3: {py}\n")
        sys.exit(2)
    # 去掉 --venv 参数避免无限递归
    new_argv = [py, os.path.abspath(__file__)]
    skip = False
    for a in argv[1:]:
        if skip:
            skip = False
            continue
        if a == "--venv":
            skip = True
            continue
        new_argv.append(a)
    os.execv(py, new_argv)


def main():
    args = parse_args(sys.argv[1:])

    audio_path = Path(args.audio).expanduser().resolve()
    if not audio_path.is_file():
        sys.stderr.write(f"[error] 音频文件不存在: {audio_path}\n")
        sys.exit(2)

    # --- 设置 MODELSCOPE_CACHE ---
    cache = args.cache
    if cache is None:
        cache = str(Path.home() / ".openclaw-hr" / "workspace-recruitment" / "models")
    cache_path = Path(cache).expanduser().resolve()
    os.environ["MODELSCOPE_CACHE"] = str(cache_path)
    sys.stderr.write(f"[info] MODELSCOPE_CACHE={cache_path}\n")

    # --- 检查 funasr 依赖 ---
    try:
        from funasr import AutoModel  # noqa: F401
    except ImportError:
        if args.venv:
            sys.stderr.write(f"[info] funasr 未装, 用 --venv 重跑: {args.venv}\n")
            reexec_in_venv(args.venv, sys.argv)
            return  # 重 exec 后不会回这里
        sys.stderr.write("[error] funasr 未装, 见 SKILL.md §环境前置 安装; "
                         "或用 --venv <venv-path> 指定已装的虚拟环境 (conda activate funasr_me 后 <venv-path>=~/.local/miniconda3/envs/funasr_me/)\n")
        sys.exit(3)

    # --- 自动检测 GPU/CPU ---
    if args.device == "auto":
        try:
            import torch
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
    else:
        device = args.device
    sys.stderr.write(f"[info] using device = {device}\n")

    # --- 关键计时: 真正的推理 (不含 Python 启动 / 模型首次下载) ---
    import torch as _torch
    if device.startswith("cuda") and _torch.cuda.is_available():
        _torch.cuda.synchronize()

    print(f"[1/3] 加载 AutoModel (Paraformer-zh + VAD + PUNC + CAM++, device={device})...", flush=True)
    try:
        from funasr import AutoModel
        m = AutoModel(
            model=MODELS["asr_paraformer"],
            vad_model=MODELS["vad"],
            punc_model=MODELS["punc"],
            spk_model=MODELS["spk_campplus"],
            device=device,
        )
    except Exception as e:
        sys.stderr.write(f"[error] AutoModel 构造失败: {e}\n")
        sys.exit(1)

    print(f"[2/3] 转写 + 说话人分离: {audio_path.name}", flush=True)
    try:
        if device.startswith("cuda") and _torch.cuda.is_available():
            _torch.cuda.synchronize()
        import time as _time
        t0 = _time.time()
        r = m.generate(
            input=str(audio_path),
            batch_size_s=args.batch_size_s,
        )
        if device.startswith("cuda") and _torch.cuda.is_available():
            _torch.cuda.synchronize()
        t1 = _time.time()
    except Exception as e:
        sys.stderr.write(f"[error] generate 失败: {e}\n")
        sys.exit(1)

    # --- 解析 sentence_info ---
    if not r or not isinstance(r, list) or "sentence_info" not in r[0]:
        sys.stderr.write("[error] FunASR 返回结构异常, 缺少 sentence_info\n")
        sys.exit(1)

    sent = r[0]["sentence_info"]
    if not sent:
        sys.stderr.write("[error] FunASR 产出空 segments — 音频可能无人声\n")
        sys.exit(1)

    # --- 转换 schema ---
    # FunASR sentence_info: [{start(ms), end(ms), text, spk(int 0/1/2), ...}]
    # 落地 schema: 每段 [{start, end, text, spk_int, speaker}] (spk_int 留底便于溯源)
    segs = []
    for s in sent:
        segs.append({
            "start": round(s["start"] / 1000.0, 2),
            "end":   round(s["end"]   / 1000.0, 2),
            "text":  s.get("text", "").strip(),
            "spk_int": int(s.get("spk", -1)),
            "speaker": f"speaker_{chr(65 + int(s.get('spk', 0)))}",  # 0->A, 1->B, 2->C
        })

    result = {
        "audio": str(audio_path),
        "model": "paraformer",
        "diarization_method": "funasr-cam++",
        "spk_campplus_used": True,
        "device": device,
        "batch_size_s": args.batch_size_s,
        "model_path": str(cache_path),
        "wall_sec": round(t1 - t0, 2),
        "segments": segs,
        "raw_sentence_info_keys": list(sent[0].keys()) if sent else [],
    }

    out_path = Path(args.out_json).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[3/3] 完成: {out_path}", flush=True)
    from collections import Counter
    cnt = Counter(s["speaker"] for s in segs)
    durs = sum(seg["end"] - seg["start"] for seg in segs)
    print(f"  共 {len(segs)} 段, 总时长 {durs:.1f}s, wall={t1-t0:.2f}s")
    for k in sorted(cnt.keys()):
        print(f"  {k}: {cnt[k]} 段")
    sys.exit(0)


if __name__ == "__main__":
    main()
