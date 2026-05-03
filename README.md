# 🎙️ 科研面对面 Podcast Agent

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white" />
  <img alt="Whisper" src="https://img.shields.io/badge/OpenAI%20Whisper-412991?logo=openai&logoColor=white" />
  <img alt="F5-TTS" src="https://img.shields.io/badge/F5--TTS-Local%20Voice%20Clone-00bcd4?style=flat" />
  <img alt="Claude" src="https://img.shields.io/badge/Anthropic%20Claude-D97757?logo=anthropic&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green?style=flat" />
</p>

> **An end-to-end automated podcast production workflow for academic interviews.**  
> Drop in a raw recording → get a broadcast-ready episode with intro, outro, show notes, and social copy — fully automated.

---

## ✨ What it does

| Step | What happens |
|---|---|
| 🎤 **Ingest** | Audio dropped into inbox folder triggers the pipeline automatically |
| 🔇 **Clean audio** | Noise reduction, silence trimming, filler-word removal (嗯、啊、那个…) |
| 🗣️ **AI Intro** | Generates a personalized Chinese-language intro, synthesized via local F5-TTS voice clone |
| 🎵 **Mix** | Blends intro narration with *Time Sparks* theme music, fade-in/out |
| 📝 **Show Notes** | Claude generates structured Chinese show notes: chapters, summary, quotes, social copy |
| 📲 **Notify** | Sends Telegram notification with final output path when done |

---

## 🚀 Quick Start

```bash
git clone https://github.com/Yang1Bai/podcast-agent
cd podcast-agent
cp .env.example .env        # fill in your API keys
pip3 install -r requirements.txt
brew install ffmpeg

# Process a single episode
python3 podcast_agent.py edit 采访录音.m4a --guest "张教授" --institution "北京大学" --topic "钙钛矿太阳能电池"
```

---

## 📥 Inbox Workflow (Fully Automatic)

1. Drop your recording into `~/Desktop/播客待处理/`
2. Place a `.txt` / `.md` file with the same filename containing guest info
3. The watcher picks it up within 30 seconds — no commands needed
4. Telegram notification arrives when the episode is ready

```bash
# Start the inbox watcher
python3 inbox_watcher.py
```

---

## 🗂 Project Structure

```
podcast-agent/
├── podcast_agent.py       # CLI entry point
├── inbox_watcher.py       # File-based trigger (watchdog)
├── modules/
│   ├── audio_editor.py    # Main editing pipeline
│   ├── intro_mixer.py     # Intro + theme music blend
│   ├── local_tts.py       # F5-TTS local voice synthesis
│   ├── filler_remover.py  # Chinese filler-word removal
│   ├── show_notes.py      # LLM show notes generation
│   ├── transcriber.py     # Whisper transcription
│   └── voice_generator.py # ElevenLabs TTS (cloud fallback)
├── assets/
│   ├── intro.mp3          # Theme music (Time Sparks)
│   └── outro.mp3
└── voices/                # Local voice reference audio (gitignored)
```

---

## ⚙️ Environment Variables

```bash
ELEVENLABS_API_KEY=...    # ElevenLabs TTS (cloud fallback)
ANTHROPIC_API_KEY=...     # Claude for show notes generation
OPENAI_API_KEY=...        # Whisper transcription
TELEGRAM_BOT_TOKEN=...    # Completion notifications
TELEGRAM_CHAT_ID=...
```

---

## 📦 Dependencies

```bash
pip3 install f5-tts openai-whisper anthropic openai elevenlabs pydub python-dotenv watchdog
brew install ffmpeg
```

---

## 🌐 Background

**科研面对面** (Science Face-to-Face) is an academic interview podcast series. This agent was built to eliminate the manual post-production bottleneck — from raw field recording to publishable episode in minutes, not hours.

---

*Built with Python · Whisper · F5-TTS · Claude · ffmpeg*
