# 🎙️ 科研面对面 Podcast Agent

自动化播客制作工作流，支持：
- 采访录音降噪、去停顿、去口头禅
- AI 生成中文开场介绍（F5-TTS 本地声音克隆）
- 片头片尾音乐混音（Time Sparks，渐出过渡）
- 自动生成 Show Notes（章节、摘要、金句、社媒文案）
- 收件箱自动监控（放入文件自动处理，Telegram 通知）

## 快速开始

```bash
cd podcast-agent
cp .env.example .env   # 填入 API keys
python3 podcast_agent.py edit 采访录音.m4a --guest "嘉宾名" --institution "机构" --topic "研究方向"
```

## 收件箱工作流

1. 把录音放入 `~/Desktop/播客待处理/`
2. 同名文本文件写嘉宾信息（支持 .txt / .md / .note 等）
3. 30 秒内自动开始处理，完成后 Telegram 通知

## 目录结构

```
podcast-agent/
├── podcast_agent.py       # 主命令行入口
├── inbox_watcher.py       # 收件箱自动监控
├── modules/
│   ├── audio_editor.py    # 剪辑主流程
│   ├── intro_mixer.py     # 片头混音
│   ├── local_tts.py       # F5-TTS 本地语音合成
│   ├── filler_remover.py  # 口头禅去除
│   ├── show_notes.py      # Show Notes 生成
│   ├── transcriber.py     # Whisper 转录
│   └── voice_generator.py # ElevenLabs TTS
├── assets/
│   ├── intro.mp3          # 片头音乐（Time Sparks）
│   └── outro.mp3          # 片尾音乐
└── voices/                # 声音克隆参考音频（本地，不上传）
```

## 依赖

```bash
pip3 install f5-tts openai-whisper anthropic openai elevenlabs pydub python-dotenv watchdog --break-system-packages
brew install ffmpeg
```

## 环境变量

```
ELEVENLABS_API_KEY=...
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
```
