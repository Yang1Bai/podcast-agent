"""
音频转文字模块 - 使用 Whisper
"""
import whisper
import os

_model = None

def get_model(size="base"):
    global _model
    if _model is None:
        print(f"⏳ 加载 Whisper {size} 模型...")
        _model = whisper.load_model(size)
        print("✅ Whisper 加载完成")
    return _model

def transcribe(audio_path: str, language: str = None) -> dict:
    """
    转录音频文件
    language: "zh" 中文, "en" 英文, None 自动检测
    返回: {"text": str, "language": str, "segments": list}
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")
    
    model = get_model("base")
    
    kwargs = {}
    if language:
        kwargs["language"] = language
    
    print(f"🎙️ 转录中: {os.path.basename(audio_path)}")
    result = model.transcribe(audio_path, **kwargs)
    
    print(f"✅ 转录完成，语言: {result['language']}, 字数: {len(result['text'])}")
    return {
        "text": result["text"].strip(),
        "language": result["language"],
        "segments": result.get("segments", [])
    }
