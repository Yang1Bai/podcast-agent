"""
口头禅去除模块
功能：用 Whisper 逐词转录，识别并精确剪掉口头禅/结巴
支持中英文口头禅检测
"""
import os
import json
import subprocess
import tempfile
from pathlib import Path

# ---- 口头禅词库 ----
FILLER_WORDS_EN = {
    "um", "uh", "hmm", "hm", "like", "you know", "you know what",
    "i mean", "basically", "literally", "actually", "right", "okay so",
    "so yeah", "kind of", "sort of",
}

FILLER_WORDS_ZH = {
    "那个", "就是说", "就是", "然后然后", "对对对", "嗯嗯", "啊啊",
    "那个那个", "这个这个", "就那个", "对吧对吧", "嗯那个",
    "然后就是", "就是那个", "就那", "这个", "然后啊",
}

# 过渡保留时间（秒），避免剪辑太突兀
FADE_MARGIN_SEC = 0.05  # 50ms


def _get_filler_set(language: str) -> set:
    """根据语言返回口头禅集合"""
    if language == "en":
        return FILLER_WORDS_EN
    elif language == "zh":
        return FILLER_WORDS_ZH | FILLER_WORDS_EN  # 中文录音也可能混入英文口头禅
    else:
        return FILLER_WORDS_ZH | FILLER_WORDS_EN


def _transcribe_with_words(input_path: str, language: str) -> dict:
    """
    调用 Whisper 进行逐词转录
    返回 whisper 结果字典（含 segments 和 words）
    """
    try:
        import whisper
    except ImportError:
        raise ImportError("请安装 openai-whisper: pip3 install openai-whisper --break-system-packages")

    model = whisper.load_model("base")
    result = model.transcribe(
        input_path,
        language=language if language != "auto" else None,
        word_timestamps=True,
        verbose=False,
    )
    return result


def _find_filler_segments(result: dict, filler_set: set) -> list:
    """
    从 Whisper 逐词结果中找出口头禅片段
    返回列表：[{"start": float, "end": float, "word": str}, ...]
    """
    filler_segments = []
    filler_lower = {w.lower().strip() for w in filler_set}

    for segment in result.get("segments", []):
        words = segment.get("words", [])
        i = 0
        while i < len(words):
            word_info = words[i]
            word_text = word_info.get("word", "").strip().lower()
            # 去除标点
            word_clean = "".join(c for c in word_text if c.isalnum() or '\u4e00' <= c <= '\u9fff')

            # 尝试匹配多词口头禅（最多 3 个词组合）
            matched = False
            for n in range(3, 0, -1):
                if i + n > len(words):
                    continue
                phrase_words = words[i:i+n]
                phrase = "".join(
                    w.get("word", "").strip().lower() for w in phrase_words
                )
                phrase_clean = "".join(
                    c for c in phrase if c.isalnum() or '\u4e00' <= c <= '\u9fff'
                )
                # 中文：去空格比较；英文：带空格比较
                phrase_with_space = " ".join(
                    w.get("word", "").strip().lower() for w in phrase_words
                ).strip()

                if phrase_clean in filler_lower or phrase_with_space in filler_lower:
                    start = phrase_words[0].get("start", 0)
                    end = phrase_words[-1].get("end", 0)
                    if end > start:
                        filler_segments.append({
                            "start": start,
                            "end": end,
                            "word": phrase_with_space or phrase_clean,
                        })
                    i += n
                    matched = True
                    break

            if not matched:
                # 单词匹配
                if word_clean in filler_lower:
                    start = word_info.get("start", 0)
                    end = word_info.get("end", 0)
                    if end > start:
                        filler_segments.append({
                            "start": start,
                            "end": end,
                            "word": word_clean,
                        })
                i += 1

    # 合并相邻（间隔 < 100ms）的口头禅片段，避免过碎剪辑
    if not filler_segments:
        return []

    merged = [filler_segments[0].copy()]
    for seg in filler_segments[1:]:
        if seg["start"] - merged[-1]["end"] < 0.1:
            merged[-1]["end"] = seg["end"]
            merged[-1]["word"] += " + " + seg["word"]
        else:
            merged.append(seg.copy())

    return merged


def _build_keep_segments(total_duration: float, filler_segs: list) -> list:
    """
    根据口头禅列表，计算保留的时间段（取反）
    每个口头禅片段向内缩进 FADE_MARGIN_SEC，保留自然过渡
    返回 [(start, end), ...]
    """
    keep = []
    cursor = 0.0

    for fs in filler_segs:
        # 保留 50ms fade margin
        cut_start = max(cursor, fs["start"] + FADE_MARGIN_SEC)
        cut_end = max(cut_start, fs["end"] - FADE_MARGIN_SEC)

        if cursor < cut_start:
            keep.append((cursor, cut_start))
        cursor = cut_end

    if cursor < total_duration:
        keep.append((cursor, total_duration))

    return keep


def _get_duration(path: str) -> float:
    """获取音频时长"""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def _cut_and_concat(input_path: str, keep_segments: list, output_path: str):
    """
    用 ffmpeg 精确剪切并拼接保留片段
    """
    if not keep_segments:
        import shutil
        shutil.copy(input_path, output_path)
        return

    tmp_dir = tempfile.mkdtemp()
    segment_files = []

    try:
        for i, (start, end) in enumerate(keep_segments):
            duration = end - start
            if duration < 0.01:
                continue
            seg_path = os.path.join(tmp_dir, f"seg_{i:04d}.mp3")
            cmd = [
                "ffmpeg", "-y",
                "-ss", f"{start:.4f}",
                "-i", input_path,
                "-t", f"{duration:.4f}",
                "-c:a", "libmp3lame", "-qscale:a", "2",
                seg_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and os.path.exists(seg_path):
                segment_files.append(seg_path)

        if not segment_files:
            import shutil
            shutil.copy(input_path, output_path)
            return

        # 写 concat 列表
        list_file = os.path.join(tmp_dir, "concat.txt")
        with open(list_file, "w") as f:
            for sf in segment_files:
                f.write(f"file '{sf}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c:a", "libmp3lame", "-qscale:a", "2",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg concat 失败: {result.stderr[-400:]}")

    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def remove_filler_words(
    input_path: str,
    output_path: str,
    language: str = "zh",
    whisper_result: dict = None,
) -> dict:
    """
    去除音频中的口头禅/结巴

    参数：
        input_path:     输入音频文件路径
        output_path:    输出音频文件路径
        language:       语言 "zh" | "en" | "auto"
        whisper_result: 已有的 Whisper 转录结果（可复用，避免重复转录）

    返回：
        {
            "output": str,            # 输出文件路径
            "removed_count": int,     # 去除的口头禅数量
            "removed_words": list,    # 去除的词列表
            "whisper_result": dict,   # Whisper 转录结果（供复用）
        }
    """
    print(f"   🔍 分析口头禅...")

    # Step 1: 转录（或复用）
    if whisper_result is None:
        print(f"   📝 Whisper 逐词转录中（language={language}）...")
        whisper_result = _transcribe_with_words(input_path, language)
    else:
        print(f"   ♻️  复用已有转录结果")

    # Step 2: 找出口头禅
    filler_set = _get_filler_set(language)
    filler_segs = _find_filler_segments(whisper_result, filler_set)

    if not filler_segs:
        print(f"   ✅ 未发现口头禅，跳过剪辑")
        import shutil
        shutil.copy(input_path, output_path)
        return {
            "output": output_path,
            "removed_count": 0,
            "removed_words": [],
            "whisper_result": whisper_result,
        }

    removed_words = [seg["word"] for seg in filler_segs]
    print(f"   ✂️  发现 {len(filler_segs)} 处口头禅: {removed_words[:10]}{'...' if len(removed_words)>10 else ''}")

    # Step 3: 计算保留段
    total_dur = _get_duration(input_path)
    keep_segs = _build_keep_segments(total_dur, filler_segs)

    # Step 4: 剪切拼接
    _cut_and_concat(input_path, keep_segs, output_path)

    print(f"   ✅ 口头禅去除完成，共去掉 {len(filler_segs)} 处")

    return {
        "output": output_path,
        "removed_count": len(filler_segs),
        "removed_words": removed_words,
        "whisper_result": whisper_result,
    }
