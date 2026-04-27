"""
音频制作模块 - 混音、添加音乐、导出成品
"""
import os
import subprocess
from pathlib import Path

ASSETS_DIR = Path(__file__).parent.parent / "assets"

def check_ffmpeg():
    result = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
    return result.returncode == 0

def normalize_audio(input_path: str, output_path: str, target_lufs: float = -16.0):
    """音量归一化到播客标准 (-16 LUFS)"""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
        "-ar", "44100", "-ac", "2",
        output_path
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path

def add_silence(input_path: str, output_path: str, before_ms: int = 0, after_ms: int = 500):
    """在音频前后添加静音"""
    filters = []
    if before_ms > 0:
        filters.append(f"adelay={before_ms}|{before_ms}")
    if after_ms > 0:
        filters.append(f"apad=pad_dur={after_ms/1000}")
    
    if filters:
        cmd = ["ffmpeg", "-y", "-i", input_path,
               "-af", ",".join(filters), output_path]
    else:
        cmd = ["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path]
    
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path

def concatenate_audio(input_files: list, output_path: str):
    """拼接多个音频文件"""
    # 生成 ffmpeg concat 列表
    list_file = output_path + ".list.txt"
    with open(list_file, "w") as f:
        for fp in input_files:
            f.write(f"file '{os.path.abspath(fp)}'\n")
    
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output_path
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    os.remove(list_file)
    return output_path

def mix_with_music(
    voice_path: str,
    music_path: str,
    output_path: str,
    music_volume: float = 0.08,  # 背景音乐音量（0-1）
    fade_in: float = 3.0,        # 音乐淡入秒数
    fade_out: float = 5.0        # 音乐淡出秒数
):
    """将语音与背景音乐混合"""
    # 获取语音时长
    probe_cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", voice_path
    ]
    import json
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    duration = float(json.loads(result.stdout)["format"]["duration"])
    
    fade_out_start = max(0, duration - fade_out)
    
    cmd = [
        "ffmpeg", "-y",
        "-i", voice_path,
        "-stream_loop", "-1", "-i", music_path,
        "-filter_complex",
        f"[1:a]volume={music_volume},afade=t=in:st=0:d={fade_in},afade=t=out:st={fade_out_start}:d={fade_out},atrim=0:{duration}[music];"
        f"[0:a][music]amix=inputs=2:duration=first[out]",
        "-map", "[out]",
        "-t", str(duration),
        "-ar", "44100", "-ac", "2",
        output_path
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path

def add_intro_outro(
    main_audio: str,
    output_path: str,
    intro_music: str = None,
    outro_music: str = None,
    intro_duration: float = 5.0,
    outro_duration: float = 5.0,
):
    """添加片头片尾"""
    parts = []
    tmp_files = []
    
    # 片头
    if intro_music and os.path.exists(intro_music):
        intro_tmp = output_path + "_intro.mp3"
        cmd = [
            "ffmpeg", "-y", "-i", intro_music,
            "-t", str(intro_duration),
            "-af", f"afade=t=out:st={max(0, intro_duration-2)}:d=2",
            intro_tmp
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        parts.append(intro_tmp)
        tmp_files.append(intro_tmp)
    
    # 主音频
    parts.append(main_audio)
    
    # 片尾
    if outro_music and os.path.exists(outro_music):
        outro_tmp = output_path + "_outro.mp3"
        cmd = [
            "ffmpeg", "-y", "-i", outro_music,
            "-t", str(outro_duration),
            "-af", f"afade=t=in:st=0:d=2,afade=t=out:st={max(0, outro_duration-2)}:d=2",
            outro_tmp
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        parts.append(outro_tmp)
        tmp_files.append(outro_tmp)
    
    if len(parts) == 1:
        # 只有主音频，直接复制
        import shutil
        shutil.copy(main_audio, output_path)
    else:
        concatenate_audio(parts, output_path)
    
    # 清理临时文件
    for f in tmp_files:
        try:
            os.remove(f)
        except:
            pass
    
    return output_path

def produce_podcast(
    voice_audio: str,
    output_path: str,
    bg_music: str = None,
    normalize: bool = True,
    add_music: bool = True,
) -> str:
    """
    完整的播客后期制作流水线
    1. 音量归一化
    2. 混入背景音乐（可选）
    3. 导出成品 MP3
    """
    print("🎛️ 开始后期制作...")
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    
    current = voice_audio
    tmp_files = []
    
    # Step 1: 归一化
    if normalize:
        norm_path = voice_audio + "_normalized.mp3"
        print("   📊 音量归一化...")
        normalize_audio(current, norm_path)
        tmp_files.append(norm_path)
        current = norm_path
    
    # Step 2: 混入背景音乐
    if add_music and bg_music and os.path.exists(bg_music):
        mixed_path = voice_audio + "_mixed.mp3"
        print(f"   🎵 混入背景音乐: {os.path.basename(bg_music)}")
        mix_with_music(current, bg_music, mixed_path)
        tmp_files.append(mixed_path)
        current = mixed_path
    
    # Step 3: 最终导出
    cmd = [
        "ffmpeg", "-y", "-i", current,
        "-codec:a", "libmp3lame", "-qscale:a", "2",
        "-id3v2_version", "3",
        output_path
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    
    # 清理临时文件
    for f in tmp_files:
        try:
            os.remove(f)
        except:
            pass
    
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"✅ 成品已生成: {output_path} ({size_mb:.1f} MB)")
    return output_path
