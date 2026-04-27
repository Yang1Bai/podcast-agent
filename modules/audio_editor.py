"""
音频剪辑模块 - 专为采访录音设计
功能：降噪、人声增强、去除停顿/结巴、加片头片尾音乐
"""
import os
import json
import subprocess
import tempfile
from pathlib import Path


def concatenate_audio(input_files: list, output_path: str) -> str:
    """拼接多个音频文件"""
    list_file = output_path + ".list.txt"
    with open(list_file, "w") as f:
        for fp in input_files:
            f.write(f"file '{os.path.abspath(fp)}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-i", list_file, "-c", "copy", output_path]
    subprocess.run(cmd, capture_output=True, check=True)
    os.remove(list_file)
    return output_path

ASSETS_DIR = Path(__file__).parent.parent / "assets"


def get_duration(path: str) -> float:
    """获取音频时长（秒）"""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def denoise_and_enhance(input_path: str, output_path: str, strength: str = "medium"):
    """
    降噪 + 人声增强
    strength: light / medium / strong
    """
    # 降噪强度映射
    noise_params = {
        "light":  "afftdn=nf=-25",
        "medium": "afftdn=nf=-20",
        "strong": "afftdn=nf=-15",
    }
    denoise = noise_params.get(strength, noise_params["medium"])

    # 完整滤镜链：
    # 1. 高通滤波去掉 80Hz 以下低频噪音/空调嗡嗡声
    # 2. FFT 降噪
    # 3. 动态压缩（让声音更均匀）
    # 4. 人声频段 EQ 提升（1k-4kHz 清晰度）
    # 5. 响度归一化到 -16 LUFS（播客标准）
    filter_chain = ",".join([
        "highpass=f=80",                                   # 去低频噪音
        denoise,                                           # FFT 降噪
        "compand=attacks=0.02:decays=0.15:points=-80/-80|-45/-15|-27/-9|0/-7|20/-7:soft-knee=6:gain=0:volume=-90:delay=0.15",  # 压缩
        "equalizer=f=3000:width_type=o:width=2:g=3",      # 提升人声清晰度
        "equalizer=f=200:width_type=o:width=1:g=-2",      # 稍微削弱浑浊感
        "loudnorm=I=-16:TP=-1.5:LRA=11",                  # 响度归一化
    ])

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af", filter_chain,
        "-ar", "44100", "-ac", "2",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"降噪失败: {result.stderr[-500:]}")
    return output_path


def remove_silences(input_path: str, output_path: str,
                    min_silence_ms: int = 800,
                    keep_silence_ms: int = 300,
                    threshold_db: float = -35.0):
    """
    去除过长停顿/结巴产生的沉默段
    min_silence_ms: 超过这个时长的静音才会被处理
    keep_silence_ms: 处理后保留多少毫秒的自然停顿
    threshold_db: 静音检测阈值
    """
    # 使用 silenceremove 滤镜
    # 先检测再删除，保留自然的短停顿
    filter_str = (
        f"silenceremove="
        f"stop_periods=-1:"
        f"stop_duration={min_silence_ms/1000}:"
        f"stop_threshold={threshold_db}dB:"
        f"leave_silence={keep_silence_ms/1000}"
    )

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af", filter_str,
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # silenceremove 参数各版本不同，用简化版fallback
        filter_str_simple = (
            f"silenceremove=stop_periods=-1:stop_duration={min_silence_ms/1000}:stop_threshold={threshold_db}dB"
        )
        cmd[5] = filter_str_simple
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # 完全 fallback：直接复制
            print("   ⚠️ 静音检测降级，跳过静音处理")
            import shutil
            shutil.copy(input_path, output_path)
    return output_path


def add_music_bookends(
    main_audio: str,
    output_path: str,
    intro_music: str = None,
    outro_music: str = None,
    intro_sec: float = 8.0,
    outro_sec: float = 8.0,
    music_volume: float = 0.25,   # 片头片尾音乐音量
    fade_sec: float = 2.0,
):
    """
    添加片头片尾音乐
    片头：音乐单独播放 intro_sec 秒后淡出
    片尾：音乐淡入后播放 outro_sec 秒
    """
    tmp_parts = []
    parts = []

    def make_music_clip(music_path, duration, fade_in=False, fade_out=True, vol=music_volume):
        tmp = tempfile.mktemp(suffix=".mp3")
        filters = [f"volume={vol}"]
        if fade_in:
            filters.append(f"afade=t=in:st=0:d={fade_sec}")
        if fade_out:
            fade_start = max(0, duration - fade_sec)
            filters.append(f"afade=t=out:st={fade_start}:d={fade_sec}")
        cmd = [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", music_path,
            "-t", str(duration),
            "-af", ",".join(filters),
            "-ar", "44100", "-ac", "2",
            tmp
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return tmp

    # 片头
    if intro_music and os.path.exists(intro_music):
        clip = make_music_clip(intro_music, intro_sec, fade_in=True, fade_out=True)
        parts.append(clip)
        tmp_parts.append(clip)

    # 主体
    parts.append(main_audio)

    # 片尾
    if outro_music and os.path.exists(outro_music):
        clip = make_music_clip(outro_music, outro_sec, fade_in=True, fade_out=True)
        parts.append(clip)
        tmp_parts.append(clip)

    # 拼接
    list_file = output_path + ".concat.txt"
    with open(list_file, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-codec:a", "libmp3lame", "-qscale:a", "2",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    os.remove(list_file)
    for t in tmp_parts:
        try: os.remove(t)
        except: pass

    if result.returncode != 0:
        raise RuntimeError(f"拼接失败: {result.stderr[-300:]}")
    return output_path


def generate_intro_narration(
    guest_name: str,
    institution: str,
    topic: str,
    intro_text: str,
    output_path: str,
    language: str = "zh",
) -> str:
    """
    用 Claude 生成开场介绍文本（含质量检查），用 F5-TTS 合成杨白的声音
    返回生成的音频路径（失败则返回 None）
    """
    import os
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")

    # Step A: Claude 生成介绍文本
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        if language == "zh":
            prompt = (
                f"你是播客「科研面对面」的主持人。请严格使用以下嘉宾信息写一段中文开场介绍，口语化。\n\n"
                f"嘉宾信息（必须原文使用，绝对不得虚构）：\n"
                f"- 姓名：{guest_name}\n"
                f"- 机构：{institution or '（未提供）'}\n"
                f"- 方向：{topic or '（未提供）'}\n"
                f"- 简介：{intro_text or '（未提供）'}\n\n"
                f"要求：①开头直接说「欢迎来到科研面对面」不要自我介绍 "
                f"②介绍嘉宾姓名、机构、方向，避免重复「研究」二字 "
                f"③结尾用「废话不多说，让我们欢迎{guest_name}」 "
                f"④只输出正文 ⑤严格70字以内"
            )
        else:
            prompt = (
                f"Write a 60-word podcast intro for: {guest_name} from {institution or 'a university'}, "
                f"working on {topic or 'science'}. {intro_text or ''} "
                f"Start with 'Welcome to Science Face-to-Face'. End with 'Please welcome {guest_name}'. Plain text only."
            )

        msg = client.messages.create(
            model="claude-haiku-4-5", max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        intro_script = msg.content[0].text.strip()

        # 质量检查：修正机构名/姓名错误，消除重复词
        check_prompt = (
            f"检查并修正以下播客开场介绍，直接输出修正后正文：\n"
            f"原文：{intro_script}\n\n"
            f"必须核对：①嘉宾姓名是否为「{guest_name}」②机构是否为「{institution}」"
            f"③有无重复词（如同一个词连续出现2次以上）\n"
            f"如有问题直接修正，没问题原文输出。严格70字以内。"
        )
        checked = client.messages.create(
            model="claude-haiku-4-5", max_tokens=150,
            messages=[{"role": "user", "content": check_prompt}]
        )
        intro_script = checked.content[0].text.strip()[:72]
        print(f"   📝 开场介绍: {intro_script}")

    except Exception as e:
        print(f"   ⚠️ Claude 生成介绍失败: {e}，使用默认介绍")
        intro_script = f"欢迎来到科研面对面！今天的嘉宾是{guest_name}。废话不多说，让我们欢迎{guest_name}。"

    # Step B: F5-TTS 合成
    try:
        from modules.local_tts import generate_speech_local, DEFAULT_REF_TEXT
        AGENT_DIR = Path(__file__).parent.parent
        ref_audio = str(AGENT_DIR / "voices" / "yang_bai_ref.mp3")
        if not os.path.exists(ref_audio):
            ref_audio = str(AGENT_DIR / "voices" / "yang_bai_sample.mp3")

        generate_speech_local(
            text=intro_script,
            ref_audio=ref_audio,
            ref_text=DEFAULT_REF_TEXT,
            output_path=output_path,
            language=language,
        )
        return output_path
    except Exception as e:
        print(f"   ⚠️ 语音合成失败: {e}")
        return None


PODCAST_OUTPUT_DIR = Path.home() / "Desktop" / "播客成品"


def edit_interview(
    input_path: str,
    output_path: str = None,
    denoise_strength: str = "medium",   # light / medium / strong
    remove_silence: bool = True,
    min_silence_ms: int = 800,
    keep_silence_ms: int = 300,
    intro_music: str = None,
    outro_music: str = None,
    intro_sec: float = 8.0,
    outro_sec: float = 8.0,
    move_original: bool = True,
    remove_fillers: bool = True,
    generate_notes: bool = True,
    guest_name: str = "",
    guest_institution: str = "",
    guest_topic: str = "",
    guest_intro_text: str = "",
    episode_title: str = "",
) -> str:
    """
    完整采访剪辑流水线：
    降噪 → 去停顿 → 去口头禅（可选）→ 加片头片尾 → 导出成品 → 生成 Show Notes → 原始文件归档
    """
    from datetime import datetime
    import shutil

    date_prefix = datetime.now().strftime("%Y-%m-%d")
    input_stem = Path(input_path).stem
    input_suffix = Path(input_path).suffix

    # 去掉文件名已有的日期前缀（如 2026-04-26_xxx → xxx）
    import re
    clean_stem = re.sub(r'^\d{4}-\d{2}-\d{2}_', '', input_stem)
    clean_stem = re.sub(r'_原始$', '', clean_stem)  # 去掉 _原始 后缀
    clean_stem = clean_stem or input_stem  # fallback

    # 按项目名建子文件夹，文件名加日期前缀
    project_dir = PODCAST_OUTPUT_DIR / clean_stem
    project_dir.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        output_path = str(project_dir / f"{date_prefix}_{clean_stem}.mp3")
    else:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    tmp_dir = tempfile.mkdtemp()

    try:
        current = input_path
        orig_dur = get_duration(input_path)
        print(f"\n🎬 开始剪辑: {os.path.basename(input_path)}")
        print(f"   原始时长: {orig_dur/60:.1f} 分钟")

        # Step 1: 降噪 + 人声增强
        print(f"\n🔇 Step 1/3 降噪 + 人声增强 (强度: {denoise_strength})...")
        denoised = os.path.join(tmp_dir, "denoised.mp3")
        denoise_and_enhance(current, denoised, denoise_strength)
        current = denoised
        print("   ✅ 完成")

        # Step 2: 去除过长停顿
        if remove_silence:
            print(f"\n✂️  Step 2/4 去除过长停顿 (>{min_silence_ms}ms)...")
            cleaned = os.path.join(tmp_dir, "cleaned.mp3")
            remove_silences(current, cleaned, min_silence_ms, keep_silence_ms)
            new_dur = get_duration(cleaned)
            saved = orig_dur - new_dur
            print(f"   ✅ 完成，剪掉了 {saved:.1f} 秒停顿")
            current = cleaned
        else:
            print("\n⏭️  Step 2/4 跳过停顿处理")

        # Step 3: 去除口头禅（可选）
        # 同时缓存 Whisper 转录结果，供 Show Notes 复用
        whisper_result_cache = None
        transcript_text = ""
        if remove_fillers:
            print(f"\n🗣️  Step 3/4 识别并去除口头禅...")
            try:
                from modules.filler_remover import remove_filler_words
            except ImportError:
                from filler_remover import remove_filler_words

            filler_out = os.path.join(tmp_dir, "no_fillers.mp3")
            filler_result = remove_filler_words(
                input_path=current,
                output_path=filler_out,
                language="zh",
                whisper_result=None,
            )
            whisper_result_cache = filler_result.get("whisper_result")
            # 提取转录文本
            if whisper_result_cache:
                transcript_text = whisper_result_cache.get("text", "")

            current = filler_out
            removed_count = filler_result.get("removed_count", 0)
            print(f"   ✅ 完成，共去除 {removed_count} 处口头禅")
        else:
            print("\n⏭️  Step 3/4 跳过口头禅去除")

        # Step 4: 生成中文开场介绍 + 精细混音
        # 结构: [Time Sparks 独奏 5s] → [音乐垃底+杨白介绍] → [音乐渐出] → [采访正文] → [片尾音乐]
        has_music = intro_music and os.path.exists(intro_music)

        if has_music and generate_notes and guest_name:
            print(f"\n🎵 Step 4/4 生成介绍 + 混音...")
            # 4a: 生成介绍语音
            narration_path = os.path.join(tmp_dir, "narration.wav")
            narration = generate_intro_narration(
                guest_name=guest_name,
                institution=guest_institution,
                topic=guest_topic or episode_title,
                intro_text=guest_intro_text,
                output_path=narration_path,
                language="zh",
            )
            if narration and os.path.exists(narration):
                # 4b: 精细混音：独奏→垃底音乐+介绍→渐出→采访
                from modules.intro_mixer import mix_intro
                final_mix = os.path.join(tmp_dir, "final_mix.mp3")
                mix_intro(
                    music_path=intro_music,
                    narration_path=narration,
                    interview_path=current,
                    output_path=final_mix,
                    music_solo_sec=5.0,
                    music_bg_volume=0.12,
                    music_fadeout_sec=3.0,
                    outro_music_path=outro_music if outro_music and os.path.exists(outro_music or "") else None,
                    outro_sec=outro_sec,
                )
                current = final_mix
                print("   ✅ 完成")
            else:
                # 介绍生成失败，改用普通片头片尾
                print("   ⚠️ 介绍生成失败，使用简单片头片尾")
                with_music = os.path.join(tmp_dir, "with_music.mp3")
                add_music_bookends(current, with_music, intro_music=intro_music,
                                   outro_music=outro_music, intro_sec=8.0, outro_sec=outro_sec)
                current = with_music

        elif has_music:
            # 没有嘉宾信息，只加片头片尾音乐
            print(f"\n🎵 Step 4/4 添加片头片尾音乐...")
            with_music = os.path.join(tmp_dir, "with_music.mp3")
            add_music_bookends(current, with_music, intro_music=intro_music,
                               outro_music=outro_music, intro_sec=8.0, outro_sec=outro_sec)
            current = with_music
            print("   ✅ 完成")
        else:
            print("\n⏭️  Step 4/4 未找到音乐文件，跳过")
            print(f"   提示: 把音乐放到 {ASSETS_DIR}/intro.mp3 和 outro.mp3")

        # 最终导出
        cmd = [
            "ffmpeg", "-y", "-i", current,
            "-codec:a", "libmp3lame", "-qscale:a", "2",
            "-id3v2_version", "3",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        final_dur = get_duration(output_path)
        size_mb = os.path.getsize(output_path) / (1024 * 1024)

        # 生成 Show Notes
        if generate_notes:
            print(f"\n📝 生成 Show Notes...")
            try:
                try:
                    from modules.show_notes import generate_show_notes
                except ImportError:
                    from show_notes import generate_show_notes

                # 如果没有转录文本（跳过了口头禅步骤），用 Whisper 快速转录
                if not transcript_text:
                    try:
                        import whisper as _whisper
                        _model = _whisper.load_model("base")
                        _res = _model.transcribe(output_path, language="zh", verbose=False)
                        transcript_text = _res.get("text", "")
                        whisper_result_cache = _res
                    except Exception as _e:
                        print(f"   ⚠️ 转录失败，跳过 Show Notes: {_e}")

                if transcript_text:
                    segments_for_notes = (
                        whisper_result_cache.get("segments", [])
                        if whisper_result_cache else []
                    )
                    notes_result = generate_show_notes(
                        transcript=transcript_text,
                        language="zh",
                        guest_name=guest_name,
                        episode_title=episode_title or input_stem,
                        segments=segments_for_notes,
                    )
                    # 保存 Show Notes
                    notes_filename = f"{date_prefix}_{clean_stem}_show_notes.md"
                    notes_path = project_dir / notes_filename
                    notes_path.write_text(notes_result["show_notes_md"], encoding="utf-8")
                    print(f"   ✅ Show Notes 已保存: {notes_path.name}")
            except Exception as _notes_err:
                print(f"   ⚠️ Show Notes 生成失败: {_notes_err}")
        else:
            print("\n⏭️  跳过 Show Notes 生成")

        # 原始文件移动到播客成品文件夹
        if move_original:
            import shutil
            orig_abs = os.path.abspath(input_path)
            orig_dest = project_dir / f"{date_prefix}_{clean_stem}_原始{input_suffix}"
            if orig_abs != str(orig_dest) and os.path.exists(orig_abs):
                shutil.move(orig_abs, str(orig_dest))
                print(f"   📦 原始文件: {orig_dest.name}")

        print(f"\n🎉 剪辑完成!")
        print(f"   📁 成品: {output_path}")
        print(f"   ⏱️  时长: {final_dur/60:.1f} 分钟 (原始 {orig_dur/60:.1f} 分钟)")
        print(f"   💾 大小: {size_mb:.1f} MB")
        print(f"   📂 全部已存到: {PODCAST_OUTPUT_DIR}")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True) if 'shutil' in dir() else __import__('shutil').rmtree(tmp_dir, ignore_errors=True)

    return output_path
