"""
片头混音模块
结构：
  [音乐独奏 5s] → [音乐低音量垫底 + 主持人介绍] → [音乐渐出 3s] → [采访正文] → [片尾音乐 8s]
"""
import os
import json
import subprocess
import tempfile
from pathlib import Path


def get_duration(path: str) -> float:
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return float(json.loads(r.stdout)["format"]["duration"])


def mix_intro(
    music_path: str,
    narration_path: str,
    interview_path: str,
    output_path: str,
    music_solo_sec: float = 4.0,      # 片头音乐纯独奏时长
    music_bg_volume: float = 0.07,    # 介绍时背景音乐音量（更低，人声更清晰）
    music_fadeout_sec: float = 4.0,   # 音乐渐出时长（更长更自然）
    outro_music_path: str = None,
    outro_sec: float = 8.0,
) -> str:
    """
    完整片头混音：
    1. 音乐独奏 solo_sec 秒（淡入）
    2. 音乐低音量 + 主持人介绍（narration）同时播放
    3. 音乐在介绍结束后渐出 fadeout_sec 秒
    4. 接采访正文
    5. 结尾加片尾音乐（可选）
    """
    narration_dur = get_duration(narration_path)
    interview_dur = get_duration(interview_path)

    tmp = tempfile.mkdtemp()

    # === Step 1: 音乐独奏片头（淡入）===
    solo_path = os.path.join(tmp, "solo.mp3")
    subprocess.run([
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", music_path,
        "-t", str(music_solo_sec),
        "-af", f"afade=t=in:st=0:d=2,afade=t=out:st={music_solo_sec-1.5}:d=1.5,volume=0.85",
        "-ar", "44100", "-ac", "2",
        solo_path
    ], capture_output=True, check=True)

    # === Step 2: 介绍段 = 背景音乐（低音量）+ 人声 ===
    # 音乐淡出：在介绍结束前 fadeout_sec 开始渐出
    fadeout_start = max(0, narration_dur - music_fadeout_sec)
    bg_path = os.path.join(tmp, "bg.mp3")
    subprocess.run([
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", music_path,
        "-t", str(narration_dur + 0.5),
        "-af", (
            f"volume={music_bg_volume},"
            f"afade=t=out:st={fadeout_start}:d={music_fadeout_sec}"
        ),
        "-ar", "44100", "-ac", "2",
        bg_path
    ], capture_output=True, check=True)

    # 人声归一化
    narration_norm = os.path.join(tmp, "narration_norm.mp3")
    subprocess.run([
        "ffmpeg", "-y", "-i", narration_path,
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-ar", "44100", "-ac", "2",
        narration_norm
    ], capture_output=True, check=True)

    # 混合：背景音乐 + 人声
    intro_mixed = os.path.join(tmp, "intro_mixed.mp3")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", narration_norm,
        "-i", bg_path,
        "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first[out]",
        "-map", "[out]",
        "-t", str(narration_dur + 0.3),
        "-ar", "44100", "-ac", "2",
        intro_mixed
    ], capture_output=True, check=True)

    # === Step 3: 拼接 solo + intro_mixed + interview ===
    parts = [solo_path, intro_mixed, interview_path]

    # 片尾音乐
    if outro_music_path and os.path.exists(outro_music_path):
        outro_path = os.path.join(tmp, "outro.mp3")
        subprocess.run([
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", outro_music_path,
            "-t", str(outro_sec),
            "-af", f"afade=t=in:st=0:d=2,afade=t=out:st={max(0,outro_sec-3)}:d=3,volume=0.85",
            "-ar", "44100", "-ac", "2",
            outro_path
        ], capture_output=True, check=True)
        parts.append(outro_path)

    # 生成 concat 列表
    list_file = os.path.join(tmp, "concat.txt")
    with open(list_file, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-codec:a", "libmp3lame", "-qscale:a", "2",
        output_path
    ], capture_output=True, check=True)

    # 清理
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    dur = get_duration(output_path)
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"   ✅ 混音完成: {dur/60:.1f}分钟 / {size_mb:.1f}MB")
    return output_path
