# 🎙️ Podcast Agent | 科研面对面

> **[English](#english) | [中文](#中文)**

---

<a name="english"></a>
## 🇬🇧 English

An end-to-end automated podcast production workflow for academic interviews. Drop in a raw recording → get a broadcast-ready episode with intro, outro, show notes, and social copy — fully automated.

### ✨ Features

| Step | What happens |
|------|-------------|
| 🎤 **Ingest** | Audio dropped into inbox folder triggers the pipeline |
| 🗣️ **Transcribe** | OpenAI Whisper transcribes speech to text |
| ✍️ **Edit** | Claude cleans filler words, structures segments |
| 🔊 **Voice Clone** | F5-TTS regenerates host voice for seamless edits |
| 📝 **Show Notes** | Claude generates episode summary + timestamps |
| 📱 **Social Copy** | Auto-generates Twitter/WeChat/LinkedIn posts |

### 🛠️ Tech Stack

- **Transcription**: OpenAI Whisper (local)
- **AI Editing**: Anthropic Claude
- **Voice Synthesis**: F5-TTS (local voice cloning)
- **Automation**: Python pipeline

### 🚀 Quick Start

```bash
git clone https://github.com/Yang1Bai/podcast-agent.git
cd podcast-agent
pip install -r requirements.txt
# Drop audio file into inbox/ and run:
python pipeline.py
```

### 📝 License

MIT License

---

<a name="中文"></a>
## 🇨🇳 中文

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white" />
  <img alt="Whisper" src="https://img.shields.io/badge/OpenAI%20Whisper-412991?logo=openai&logoColor=white" />
  <img alt="F5-TTS" src="https://img.shields.io/badge/F5--TTS-Local%20Voice%20Clone-00bcd4?style=flat" />
  <img alt="Claude" src="https://img.shields.io/badge/Anthropic%20Claude-D97757?logo=anthropic&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green?style=flat" />
</p>

> **面向学术访谈的端到端自动化播客制作工作流。**
> 投入原始录音 → 全自动生成可发布节目（含片头、片尾、节目介绍和社交文案）。

---

### ✨ 功能模块

| 步骤 | 发生了什么 |
|---|---|
| 🎤 **录音接入** | 音频投入收件箱文件夹，自动触发流水线 |
| 🔇 **音频清理** | 降噪、去除静音、去除填充词（嗯、啊、那个…） |
| 🗣️ **AI 片头** | 生成个性化中文片头，通过本地 F5-TTS 语音克隆合成 |
| 🎵 **混音** | 将片头旁白与《时光闪烁》主题音乐混合，含淡入淡出 |
| 📝 **节目介绍** | Claude 生成结构化中文节目介绍：章节、摘要、金句、社交文案 |
| 📲 **通知** | 完成后发送 Telegram 通知，附最终输出路径 |

---

### 🚀 快速开始

```bash
git clone https://github.com/Yang1Bai/podcast-agent
cd podcast-agent
cp .env.example .env        # 填写你的 API keys
pip3 install -r requirements.txt
brew install ffmpeg

# 处理单集节目
python3 podcast_agent.py edit 采访录音.m4a --guest "张教授" --institution "北京大学" --topic "钙钛矿太阳能电池"
```

---

### 📥 收件箱工作流（全自动）

1. 将录音投入 `~/Desktop/播客待处理/`
2. 在同目录放一个同名 `.txt` / `.md` 文件，包含嘉宾信息
3. 监听程序在 30 秒内自动拾取——无需任何命令
4. 节目就绪后收到 Telegram 通知

```bash
# 启动收件箱监听
python3 inbox_watcher.py
```

---

### 🗂 项目结构

```
podcast-agent/
├── podcast_agent.py       # CLI 入口
├── inbox_watcher.py       # 文件触发器（watchdog）
├── modules/
│   ├── audio_editor.py    # 主编辑流水线
│   ├── intro_mixer.py     # 片头 + 主题音乐混合
│   ├── local_tts.py       # F5-TTS 本地语音合成
│   ├── filler_remover.py  # 中文填充词去除
│   ├── show_notes.py      # LLM 节目介绍生成
│   ├── transcriber.py     # Whisper 转录
│   └── voice_generator.py # ElevenLabs TTS（云端备用）
├── assets/
│   ├── intro.mp3          # 主题音乐（时光闪烁）
│   └── outro.mp3
└── voices/                # 本地语音参考音频（gitignore）
```

---

### ⚙️ 环境变量

```bash
ELEVENLABS_API_KEY=...    # ElevenLabs TTS（云端备用）
ANTHROPIC_API_KEY=...     # Claude 生成节目介绍
OPENAI_API_KEY=...        # Whisper 转录
TELEGRAM_BOT_TOKEN=...    # 完成通知
TELEGRAM_CHAT_ID=...
```

---

### 📦 依赖

```bash
pip3 install f5-tts openai-whisper anthropic openai elevenlabs pydub python-dotenv watchdog
brew install ffmpeg
```

---

### 🌐 项目背景

**科研面对面** 是一档学术访谈播客节目。本工具旨在消除手动后期制作瓶颈——从原始现场录音到可发布节目，只需数分钟而非数小时。

---

*Built with Python · Whisper · F5-TTS · Claude · ffmpeg*
