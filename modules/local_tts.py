"""
本地语音克隆模块 - 基于 F5-TTS 零样本语音克隆
支持中文和英文，使用 Apple Silicon MPS 加速

安装: pip3 install f5-tts --break-system-packages
模型: F5TTS_v1_Base (自动下载到 ~/.cache/huggingface/hub/)
"""

import os
import time
import tempfile
import subprocess
from pathlib import Path

# 默认配置
DEFAULT_MODEL = "F5TTS_v1_Base"
DEFAULT_DEVICE = "mps"  # Apple Silicon GPU；CPU 用 "cpu"
DEFAULT_REF_AUDIO = str(
    Path(__file__).parent.parent / "voices" / "yang_bai_ref.mp3"
)
DEFAULT_REF_TEXT = "大家好，很高兴今天我们邀请来了这位科学家，他的名字是好好好，所以说今天我们要和他探讨的内容是AI相关的材料研究"


def generate_speech_local(
    text: str,
    ref_audio: str = DEFAULT_REF_AUDIO,
    output_path: str = None,
    language: str = "zh",
    model: str = DEFAULT_MODEL,
    device: str = DEFAULT_DEVICE,
    ref_text: str = DEFAULT_REF_TEXT,
    remove_silence: bool = False,
    speed: float = 1.0,
) -> str:
    """
    用本地 F5-TTS 模型克隆声音生成语音，返回输出路径。

    Args:
        text:           要合成的文本（中文或英文）
        ref_audio:      参考音频路径（3-15秒清晰录音为佳）
        output_path:    输出 WAV 文件路径；None 则自动生成临时路径
        language:       语言代码（"zh" 或 "en"，仅用于日志；F5-TTS 自动检测）
        model:          F5-TTS 模型名称，默认 F5TTS_v1_Base
        device:         推理设备，"mps"（Apple Silicon）或 "cpu"
        ref_text:       参考音频对应的文字；空字符串时 F5-TTS 自动转录
        remove_silence: 是否去除生成音频中的静音段
        speed:          语速倍率（默认 1.0）

    Returns:
        生成的 WAV 文件的绝对路径
    """
    if not text or not text.strip():
        raise ValueError("text 不能为空")

    ref_audio = str(ref_audio)
    if not os.path.exists(ref_audio):
        raise FileNotFoundError(f"参考音频不存在: {ref_audio}")

    # 确定输出路径
    if output_path is None:
        tmpdir = tempfile.mkdtemp(prefix="f5tts_")
        output_path = os.path.join(tmpdir, "output.wav")

    output_path = str(output_path)
    output_dir = os.path.dirname(os.path.abspath(output_path))
    output_file = os.path.basename(output_path)
    os.makedirs(output_dir, exist_ok=True)

    # 构建 CLI 命令
    cmd = [
        "f5-tts_infer-cli",
        "-m", model,
        "-r", ref_audio,
        "-t", text,
        "-o", output_dir,
        "-w", output_file,
        "--device", device,
        "--speed", str(speed),
    ]

    if ref_text:
        cmd += ["-s", ref_text]

    if remove_silence:
        cmd.append("--remove_silence")

    print(f"🗣️ [F5-TTS] 生成语音 lang={language} chars={len(text)}")
    print(f"   ref_audio: {os.path.basename(ref_audio)}")
    print(f"   output:    {output_path}")
    print(f"   cmd:       {' '.join(cmd[:6])} ...")

    t0 = time.time()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    elapsed = time.time() - t0

    if result.returncode != 0:
        raise RuntimeError(
            f"F5-TTS 推理失败 (exit {result.returncode}):\n"
            f"stdout: {result.stdout[-500:]}\n"
            f"stderr: {result.stderr[-500:]}"
        )

    if not os.path.exists(output_path):
        raise FileNotFoundError(
            f"F5-TTS 未生成输出文件: {output_path}\n"
            f"stdout: {result.stdout[-500:]}"
        )

    size_kb = os.path.getsize(output_path) / 1024
    print(f"✅ 语音生成完成: {output_path} ({size_kb:.1f} KB, {elapsed:.1f}s)")
    return output_path


def benchmark(
    text: str = "欢迎来到本期节目，今天我们将探讨一个非常有趣的话题。",
    ref_audio: str = DEFAULT_REF_AUDIO,
    device: str = DEFAULT_DEVICE,
) -> dict:
    """
    简单基准测试，返回生成耗时和文件大小。

    Returns:
        {"output_path": str, "elapsed_s": float, "size_kb": float, "chars_per_sec": float}
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, "bench.wav")
        t0 = time.time()
        generate_speech_local(text, ref_audio=ref_audio, output_path=out, device=device)
        elapsed = time.time() - t0
        size_kb = os.path.getsize(out) / 1024

    return {
        "elapsed_s": round(elapsed, 1),
        "size_kb": round(size_kb, 1),
        "chars": len(text),
        "chars_per_sec": round(len(text) / elapsed, 2),
    }


if __name__ == "__main__":
    # 快速自测
    out = generate_speech_local(
        text="欢迎来到本期节目，今天我们将探讨一个非常有趣的话题。",
        output_path="/Users/gj/.openclaw/workspace/podcast-agent/output/voice_test_local.wav",
    )
    print(f"输出文件: {out}")
