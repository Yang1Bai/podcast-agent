#!/usr/bin/env python3
"""
🎙️ Podcast Agent - 自动播客生成工作流
用法：python3 podcast_agent.py [选项]
"""

import os
import sys
import argparse
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# 添加 modules 路径
sys.path.insert(0, str(Path(__file__).parent))
from modules.transcriber import transcribe
from modules.script_processor import process_script
from modules.voice_generator import (
    clone_voice, get_voice_id, list_my_voices,
    generate_speech, generate_dialogue, get_client as el_client
)
from modules.audio_producer import produce_podcast, concatenate_audio
from modules.audio_editor import edit_interview, ASSETS_DIR as EDIT_ASSETS_DIR

OUTPUT_DIR = Path(__file__).parent / "output"
VOICES_DIR = Path(__file__).parent / "voices"
ASSETS_DIR = Path(__file__).parent / "assets"


def ensure_dirs():
    OUTPUT_DIR.mkdir(exist_ok=True)
    VOICES_DIR.mkdir(exist_ok=True)
    ASSETS_DIR.mkdir(exist_ok=True)


def cmd_clone(args):
    """克隆声音"""
    if not args.files:
        print("❌ 请提供音频文件路径")
        print("   例如: python3 podcast_agent.py clone --name '我的声音' --files voice1.mp3 voice2.mp3")
        return
    
    voice_id = clone_voice(
        name=args.name,
        audio_files=args.files,
        description=args.description or ""
    )
    print(f"\n🎉 声音克隆成功!")
    print(f"   名称: {args.name}")
    print(f"   ID: {voice_id}")
    print(f"\n现在可以用 --voice '{args.name}' 来生成播客了")


def cmd_voices(args):
    """列出已克隆的声音"""
    voices = list_my_voices()
    if not voices:
        print("📭 还没有克隆任何声音")
        print("   用 clone 命令克隆你的声音: python3 podcast_agent.py clone --name '我的声音' --files sample.mp3")
        return
    
    print("🎙️ 已克隆的声音:")
    for name, info in voices.items():
        print(f"  • {name} — {info['voice_id'][:12]}...")
        if info.get('description'):
            print(f"    {info['description']}")


def cmd_make(args):
    """主命令：生成播客"""
    ensure_dirs()
    
    # 确定输出文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    episode_name = args.title.replace(" ", "_") if args.title else f"episode_{timestamp}"
    output_path = OUTPUT_DIR / f"{episode_name}.mp3"
    
    print(f"\n🎙️ 播客生成开始")
    print(f"   语言: {'中文' if args.language == 'zh' else 'English'}")
    print(f"   格式: {'单人旁白' if args.format == 'solo' else '双人对话'}")
    print(f"   输出: {output_path}\n")
    
    # === Step 1: 获取内容 ===
    raw_content = ""
    
    if args.audio:
        # 音频输入 → 转录
        print("📥 输入类型: 音频文件")
        result = transcribe(args.audio, language=args.language if args.language != "auto" else None)
        raw_content = result["text"]
        if not args.language or args.language == "auto":
            args.language = result["language"]
    elif args.text:
        # 文本文件
        print("📥 输入类型: 文本文件")
        raw_content = Path(args.text).read_text(encoding="utf-8")
    elif args.content:
        # 直接内容
        print("📥 输入类型: 直接内容")
        raw_content = args.content
    else:
        print("❌ 请提供内容：--audio 音频文件 | --text 文本文件 | --content '内容'")
        return
    
    print(f"   原始内容长度: {len(raw_content)} 字\n")
    
    # === Step 2: 生成播客脚本 ===
    if args.no_ai:
        script = raw_content
        print("⏭️ 跳过 AI 脚本优化")
    else:
        script = process_script(
            content=raw_content,
            language=args.language,
            format=args.format,
            topic=args.title or "",
            duration_hint=args.duration or "5-10分钟"
        )
    
    # 保存脚本
    script_path = OUTPUT_DIR / f"{episode_name}_script.txt"
    script_path.write_text(script, encoding="utf-8")
    print(f"📝 脚本已保存: {script_path}\n")
    
    # === Step 3: 获取声音 ===
    voices = list_my_voices()
    
    if args.format == "solo":
        # 单人模式
        if args.voice:
            if args.voice in voices:
                voice_id = voices[args.voice]["voice_id"]
            else:
                # 当作 voice_id 直接用
                voice_id = args.voice
        elif voices:
            # 使用第一个克隆声音
            voice_name = list(voices.keys())[0]
            voice_id = voices[voice_name]["voice_id"]
            print(f"🔊 使用克隆声音: {voice_name}")
        else:
            # 使用 ElevenLabs 默认声音
            voice_id = "EXAVITQu4vr4xnSDxMaL"  # Sarah - 适合播客
            print("⚠️ 未找到克隆声音，使用 ElevenLabs 默认声音 (Sarah)")
            print("   提示: 先用 clone 命令克隆你的声音")
        
        # 生成语音
        raw_voice = str(OUTPUT_DIR / f"{episode_name}_voice_raw.mp3")
        
        # 处理 [PAUSE] 标记，分段生成后拼接
        segments = [s.strip() for s in script.replace("[PAUSE]", "|||").split("|||") if s.strip()]
        
        if len(segments) > 1:
            print(f"   分 {len(segments)} 段生成语音...")
            segment_files = []
            tmp_dir = tempfile.mkdtemp()
            
            for i, seg in enumerate(segments):
                if not seg:
                    continue
                seg_path = os.path.join(tmp_dir, f"seg_{i:03d}.mp3")
                generate_speech(seg, voice_id, seg_path, args.language)
                segment_files.append(seg_path)
            
            # 拼接所有段落
            concatenate_audio(segment_files, raw_voice)
            shutil.rmtree(tmp_dir)
        else:
            generate_speech(script, voice_id, raw_voice, args.language)
    
    else:
        # 对话模式
        host_voice_id = voice_id if args.voice else (
            list(voices.values())[0]["voice_id"] if voices else "EXAVITQu4vr4xnSDxMaL"
        )
        guest_voice_id = args.guest_voice or "JBFqnCBsd6RMkjVDRZzb"  # George
        
        print(f"🎙️ HOST 声音: {args.voice or '你的克隆声音'}")
        print(f"🎙️ GUEST 声音: {args.guest_voice or 'George (默认)'}")
        
        tmp_dir = tempfile.mkdtemp()
        segments = generate_dialogue(
            script, host_voice_id, guest_voice_id, tmp_dir, args.language
        )
        
        raw_voice = str(OUTPUT_DIR / f"{episode_name}_voice_raw.mp3")
        concatenate_audio([p for _, p in segments], raw_voice)
        shutil.rmtree(tmp_dir)
    
    # === Step 4: 后期制作 ===
    bg_music = None
    if args.music and os.path.exists(args.music):
        bg_music = args.music
    elif (ASSETS_DIR / "background.mp3").exists():
        bg_music = str(ASSETS_DIR / "background.mp3")
    
    produce_podcast(
        voice_audio=raw_voice,
        output_path=str(output_path),
        bg_music=bg_music,
        normalize=True,
        add_music=bg_music is not None,
    )
    
    # 清理临时语音文件
    try:
        os.remove(raw_voice)
    except:
        pass
    
    print(f"\n🎉 播客制作完成!")
    print(f"   📁 成品文件: {output_path}")
    print(f"   📝 脚本文件: {script_path}")
    duration_est = os.path.getsize(output_path) / (128 * 1024 / 8) / 60
    print(f"   ⏱️  预计时长: ~{duration_est:.1f} 分钟")


def cmd_edit(args):
    """剪辑采访录音"""
    ensure_dirs()
    if not os.path.exists(args.input):
        print(f"❌ 文件不存在: {args.input}")
        return

    # 输出路径由 audio_editor 自动确定（桌面/播客成品/项目名/）

    # 自动查找音乐文件
    intro_music = args.intro or str(ASSETS_DIR / "intro.mp3")
    outro_music = args.outro or str(ASSETS_DIR / "outro.mp3")

    edit_interview(
        input_path=args.input,
        output_path=None,  # 自动归档到 ~/Desktop/播客成品/项目名/
        denoise_strength=args.denoise,
        remove_silence=not args.keep_silence,
        min_silence_ms=args.min_silence,
        keep_silence_ms=args.keep_silence_ms,
        intro_music=intro_music if os.path.exists(intro_music) else None,
        outro_music=outro_music if os.path.exists(outro_music) else None,
        intro_sec=args.intro_sec,
        outro_sec=args.outro_sec,
        remove_fillers=not args.no_fillers,
        generate_notes=not args.no_show_notes,
        guest_name=args.guest or "",
        guest_institution=getattr(args, 'institution', '') or "",
        guest_topic=getattr(args, 'topic', '') or "",
        guest_intro_text=getattr(args, 'intro_text', '') or "",
        episode_title=args.title or "",
    )


def main():
    parser = argparse.ArgumentParser(
        description="🎙️ Podcast Agent - 自动播客生成工作流",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 克隆你的声音
  python3 podcast_agent.py clone --name '杨白' --files my_voice.mp3

  # 用文本生成中文单人播客
  python3 podcast_agent.py make --content '今天我们聊聊AI的未来...' --language zh --title '我的第一期播客'

  # 用音频文件生成播客
  python3 podcast_agent.py make --audio recording.m4a --language zh --format solo

  # 生成英文对话播客
  python3 podcast_agent.py make --text script.txt --language en --format dialogue --title 'My Podcast'

  # 列出已克隆的声音
  python3 podcast_agent.py voices
"""
    )
    
    subparsers = parser.add_subparsers(dest="command")

    # edit 命令
    edit_parser = subparsers.add_parser("edit", help="剪辑采访录音（降噪/去停顿/加音乐）")
    edit_parser.add_argument("input", help="输入音频文件路径")
    edit_parser.add_argument("--denoise", default="medium", choices=["light", "medium", "strong"], help="降噪强度 (默认: medium)")
    edit_parser.add_argument("--keep-silence", action="store_true", help="保留停顿，不自动剪辑")
    edit_parser.add_argument("--min-silence", type=int, default=800, help="超过多少 ms 的静音才处理 (默认: 800)")
    edit_parser.add_argument("--keep-silence-ms", type=int, default=300, help="静音处理后保留多少 ms 自然停顿 (默认: 300)")
    edit_parser.add_argument("--intro", help="片头音乐文件路径")
    edit_parser.add_argument("--outro", help="片尾音乐文件路径")
    edit_parser.add_argument("--intro-sec", type=float, default=8.0, help="片头时长秒数 (默认: 8)")
    edit_parser.add_argument("--outro-sec", type=float, default=8.0, help="片尾时长秒数 (默认: 8)")
    edit_parser.add_argument("--no-fillers", action="store_true", help="关闭口头禅去除（默认开启）")
    edit_parser.add_argument("--no-show-notes", action="store_true", dest="no_show_notes", help="关闭 Show Notes 生成（默认开启）")
    edit_parser.add_argument("--guest", help="嘉宾姓名")
    edit_parser.add_argument("--institution", help="嘉宾机构")
    edit_parser.add_argument("--topic", help="研究方向/话题")
    edit_parser.add_argument("--intro-text", help="一句话介绍")
    edit_parser.add_argument("--title", help="节目标题")
    
    # clone 命令
    clone_parser = subparsers.add_parser("clone", help="克隆声音")
    clone_parser.add_argument("--name", required=True, help="声音名称")
    clone_parser.add_argument("--files", nargs="+", required=True, help="音频文件路径（1-5个）")
    clone_parser.add_argument("--description", help="声音描述")
    
    # voices 命令
    subparsers.add_parser("voices", help="列出已克隆的声音")
    
    # make 命令
    make_parser = subparsers.add_parser("make", help="生成播客")
    
    # 内容输入（三选一）
    input_group = make_parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--audio", help="音频文件路径（自动转录）")
    input_group.add_argument("--text", help="文本文件路径")
    input_group.add_argument("--content", help="直接输入文字内容")
    
    # 播客设置
    make_parser.add_argument("--language", default="zh", choices=["zh", "en", "auto"], help="语言 (默认: zh)")
    make_parser.add_argument("--format", default="solo", choices=["solo", "dialogue"], help="格式: solo单人 | dialogue对话 (默认: solo)")
    make_parser.add_argument("--title", help="播客标题/集名")
    make_parser.add_argument("--duration", help="目标时长提示，如 '10分钟'")
    make_parser.add_argument("--voice", help="HOST 声音名称或 voice_id")
    make_parser.add_argument("--guest-voice", help="GUEST 声音 voice_id（对话模式）")
    make_parser.add_argument("--music", help="背景音乐文件路径")
    make_parser.add_argument("--no-ai", action="store_true", help="跳过 AI 脚本优化，直接使用原始内容")
    
    args = parser.parse_args()
    
    if args.command == "edit":
        cmd_edit(args)
    elif args.command == "clone":
        cmd_clone(args)
    elif args.command == "voices":
        cmd_voices(args)
    elif args.command == "make":
        cmd_make(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
