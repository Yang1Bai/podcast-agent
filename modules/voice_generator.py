"""
语音生成模块 - ElevenLabs TTS + 声音克隆
"""
import os
import json
from pathlib import Path
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

VOICES_DIR = Path(__file__).parent.parent / "voices"
VOICES_CONFIG = VOICES_DIR / "my_voices.json"

def get_client():
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        raise ValueError("未设置 ELEVENLABS_API_KEY")
    return ElevenLabs(api_key=key)

def load_voices_config() -> dict:
    if VOICES_CONFIG.exists():
        return json.loads(VOICES_CONFIG.read_text())
    return {}

def save_voices_config(config: dict):
    VOICES_DIR.mkdir(exist_ok=True)
    VOICES_CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2))

def clone_voice(name: str, audio_files: list, description: str = "") -> str:
    """
    克隆声音，返回 voice_id
    audio_files: 音频文件路径列表（建议 1-5 分钟清晰录音）
    """
    client = get_client()
    
    print(f"🔊 克隆声音: {name}")
    print(f"   音频文件: {[os.path.basename(f) for f in audio_files]}")
    
    file_handles = [open(f, "rb") for f in audio_files]
    try:
        voice = client.clone(
            name=name,
            description=description or f"Yang Bai's cloned voice - {name}",
            files=file_handles,
        )
    finally:
        for f in file_handles:
            f.close()
    
    voice_id = voice.voice_id
    print(f"✅ 声音克隆成功! voice_id: {voice_id}")
    
    # 保存配置
    config = load_voices_config()
    config[name] = {
        "voice_id": voice_id,
        "description": description,
        "files": [str(f) for f in audio_files]
    }
    save_voices_config(config)
    
    return voice_id

def list_my_voices() -> dict:
    """列出已克隆的声音"""
    return load_voices_config()

def get_voice_id(voice_name: str) -> str:
    """根据名字获取 voice_id"""
    config = load_voices_config()
    if voice_name not in config:
        raise ValueError(f"未找到声音 '{voice_name}'，请先克隆。已有: {list(config.keys())}")
    return config[voice_name]["voice_id"]

def generate_speech(
    text: str,
    voice_id: str,
    output_path: str,
    language: str = "zh",
    stability: float = 0.5,
    similarity_boost: float = 0.8,
    style: float = 0.3,
    ref_audio: str = None,
) -> str:
    """
    生成语音文件
    voice_id == "local" 时使用本地 F5-TTS 零样本克隆（离线，免费）
    其他 voice_id 使用 ElevenLabs API
    返回输出文件路径
    """
    # ── 本地 F5-TTS 路径 ──────────────────────────────────────────
    if voice_id == "local":
        from modules.local_tts import generate_speech_local, DEFAULT_REF_AUDIO
        _ref = ref_audio or DEFAULT_REF_AUDIO
        return generate_speech_local(
            text=text,
            ref_audio=_ref,
            output_path=output_path,
            language=language,
        )

    # ── ElevenLabs API 路径 ───────────────────────────────────────
    client = get_client()
    
    # 根据语言选择模型
    model_id = "eleven_flash_v2_5" if language == "zh" else "eleven_flash_v2_5"
    # 中英文都用 flash_v2_5，它支持多语言
    
    print(f"🗣️ 生成语音 ({language.upper()})，文字长度: {len(text)}")
    
    audio = client.generate(
        text=text,
        voice=voice_id,
        model=model_id,
        voice_settings=VoiceSettings(
            stability=stability,
            similarity_boost=similarity_boost,
            style=style,
            use_speaker_boost=True,
        )
    )
    
    # 写入文件
    output_path = str(output_path)
    with open(output_path, "wb") as f:
        for chunk in audio:
            f.write(chunk)
    
    size_kb = os.path.getsize(output_path) / 1024
    print(f"✅ 语音生成完成: {output_path} ({size_kb:.1f} KB)")
    return output_path

def generate_dialogue(
    script: str,
    host_voice_id: str,
    guest_voice_id: str,
    output_dir: str,
    language: str = "zh"
) -> list:
    """
    生成对话音频（多段）
    script 格式：HOST: ... \nGUEST: ...
    返回音频文件路径列表 [(speaker, path), ...]
    """
    lines = []
    current_speaker = None
    current_text = []
    
    for line in script.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith("HOST:"):
            if current_speaker and current_text:
                lines.append((current_speaker, ' '.join(current_text)))
            current_speaker = "HOST"
            current_text = [line[5:].strip()]
        elif line.startswith("GUEST:"):
            if current_speaker and current_text:
                lines.append((current_speaker, ' '.join(current_text)))
            current_speaker = "GUEST"
            current_text = [line[6:].strip()]
        else:
            if current_speaker:
                current_text.append(line)
    
    if current_speaker and current_text:
        lines.append((current_speaker, ' '.join(current_text)))
    
    results = []
    os.makedirs(output_dir, exist_ok=True)
    
    for i, (speaker, text) in enumerate(lines):
        if not text.strip():
            continue
        voice_id = host_voice_id if speaker == "HOST" else guest_voice_id
        output_path = os.path.join(output_dir, f"segment_{i:03d}_{speaker}.mp3")
        generate_speech(text, voice_id, output_path, language)
        results.append((speaker, output_path))
    
    return results
