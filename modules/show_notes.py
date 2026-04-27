"""
Show Notes 生成模块
功能：根据播客转录文本，用 Claude API 生成完整配套内容
包含：标题建议、摘要、章节、关键洞察、金句、社交文案
"""
import os
import json
from datetime import datetime


def _format_time(seconds: float) -> str:
    """秒数转 MM:SS 或 HH:MM:SS"""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _estimate_chapters_from_segments(segments: list, max_chapters: int = 8) -> list:
    """
    从 Whisper segments 推算章节时间戳
    按时长等分，每段约 5-8 分钟一个章节
    """
    if not segments:
        return []

    total_dur = segments[-1].get("end", 0) if segments else 0
    if total_dur <= 0:
        return []

    # 每个章节约 5 分钟
    chapter_dur = 300.0
    chapters = []
    current_time = 0.0
    chapter_idx = 0

    while current_time < total_dur and chapter_idx < max_chapters:
        chapters.append({
            "time": _format_time(current_time),
            "time_sec": current_time,
            "title": f"第{chapter_idx + 1}部分",  # 占位，由 AI 填充
        })
        current_time += chapter_dur
        chapter_idx += 1

    return chapters


def _simple_template(
    transcript: str,
    language: str,
    guest_name: str,
    episode_title: str,
    chapters_hint: list,
) -> dict:
    """
    无 API Key 时的简单模板生成
    """
    date_str = datetime.now().strftime("%Y年%m月%d日")
    title = episode_title or "本期播客"
    guest = f"嘉宾：{guest_name}" if guest_name else ""

    # 截取摘要（前 150 字）
    summary_raw = transcript.replace("\n", " ").strip()
    summary = summary_raw[:150] + ("…" if len(summary_raw) > 150 else "")

    chapters = chapters_hint if chapters_hint else [{"time": "00:00", "title": "节目开始"}]

    chapters_md = "\n".join(
        f"- `{c['time']}` {c.get('title', '章节')}" for c in chapters
    )

    show_notes_md = f"""# {title}

> 播出日期：{date_str}  
> {guest}

## 📋 节目摘要

{summary}

## 📍 章节时间轴

{chapters_md}

## 📝 完整文字稿摘录

{transcript[:500]}{'...' if len(transcript) > 500 else ''}

---
*本 Show Notes 由 Podcast Agent 自动生成*
"""

    social_zh = f"""🎙️ 新一期播客上线！

{title}

{summary}

#播客 #PodcastLife"""

    social_en = f"""🎙️ New episode out now!

{title}

{summary}

#Podcast #NewEpisode"""

    return {
        "title_suggestions": [title, f"{title}（精华版）", f"对话{guest_name or '嘉宾'}：{title}"],
        "summary": summary,
        "chapters": chapters,
        "key_takeaways": ["（需 Claude API Key 生成详细内容）"],
        "key_quotes": ["（需 Claude API Key 生成详细内容）"],
        "show_notes_md": show_notes_md,
        "social_zh": social_zh,
        "social_en": social_en,
    }


def _call_claude(api_key: str, prompt: str, system: str = "") -> str:
    """调用 Claude API"""
    try:
        import anthropic
    except ImportError:
        raise ImportError("请安装 anthropic: pip3 install anthropic --break-system-packages")

    client = anthropic.Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": prompt}]

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=4096,
        system=system or "你是一位专业的播客制作人和内容编辑，擅长制作高质量的播客配套内容。",
        messages=messages,
    )
    return response.content[0].text


def _generate_with_claude(
    api_key: str,
    transcript: str,
    language: str,
    guest_name: str,
    episode_title: str,
    chapters_hint: list,
) -> dict:
    """使用 Claude API 生成完整 Show Notes"""

    lang_desc = "中文" if language == "zh" else "English"
    guest_info = f"嘉宾：{guest_name}" if guest_name else "（无特定嘉宾）"
    title_info = f"节目标题：{episode_title}" if episode_title else "（无特定标题）"

    # 构建 chapters 提示
    if chapters_hint:
        chapters_str = json.dumps(chapters_hint, ensure_ascii=False, indent=2)
        chapters_prompt = f"\n参考时间轴（请为每个章节补充合适的标题）：\n{chapters_str}"
    else:
        chapters_prompt = "\n请根据内容推断合理的章节划分（3-8个章节），时间戳用 MM:SS 格式。"

    # 截取转录（避免超出 token 限制）
    transcript_excerpt = transcript[:6000] + ("...[截断]" if len(transcript) > 6000 else "")

    prompt = f"""请为以下播客节目生成完整的 Show Notes 配套内容。

语言：{lang_desc}
{title_info}
{guest_info}
{chapters_prompt}

转录文字稿：
---
{transcript_excerpt}
---

请用 JSON 格式返回以下内容（确保是合法 JSON，不要有多余的文字）：
{{
  "title_suggestions": ["标题1", "标题2", "标题3"],
  "summary": "150字以内的摘要",
  "chapters": [{{"time": "00:00", "title": "章节标题"}}],
  "key_takeaways": ["要点1", "要点2", "要点3", "要点4", "要点5"],
  "key_quotes": ["金句1", "金句2", "金句3"],
  "social_zh": "小红书/微信朋友圈文案（含emoji，200字以内）",
  "social_en": "Twitter/LinkedIn post (under 280 characters)"
}}

注意：
- title_suggestions 正好 3 个，吸引眼球，适合平台发布
- summary 控制在 150 字以内
- key_takeaways 正好 5 条
- key_quotes 正好 3 条，来自转录原文
- social_zh 适合小红书/微信，有 emoji，活泼
- social_en 适合 Twitter，简洁有力
- 所有内容使用{lang_desc}"""

    raw = _call_claude(api_key, prompt)

    # 解析 JSON
    try:
        # 找到 JSON 块
        json_start = raw.find("{")
        json_end = raw.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            data = json.loads(raw[json_start:json_end])
        else:
            raise ValueError("未找到 JSON")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"   ⚠️ Claude 返回解析失败: {e}，使用模板回退")
        return None

    # 确保字段完整
    chapters = data.get("chapters", chapters_hint or [{"time": "00:00", "title": "节目开始"}])
    title_suggestions = data.get("title_suggestions", [episode_title or "本期播客"])
    summary = data.get("summary", "")
    key_takeaways = data.get("key_takeaways", [])
    key_quotes = data.get("key_quotes", [])
    social_zh = data.get("social_zh", "")
    social_en = data.get("social_en", "")

    # 生成完整 Markdown
    date_str = datetime.now().strftime("%Y年%m月%d日")
    main_title = title_suggestions[0] if title_suggestions else (episode_title or "本期播客")
    guest_line = f"> 嘉宾：{guest_name}  \n" if guest_name else ""

    chapters_md = "\n".join(
        f"- `{c.get('time', '00:00')}` {c.get('title', '')}" for c in chapters
    )
    takeaways_md = "\n".join(f"{i+1}. {t}" for i, t in enumerate(key_takeaways))
    quotes_md = "\n\n".join(f"> {q}" for q in key_quotes)

    show_notes_md = f"""# {main_title}

> 播出日期：{date_str}  
{guest_line}
## 📋 节目摘要

{summary}

## 📍 章节时间轴

{chapters_md}

## 💡 核心洞察

{takeaways_md}

## 💬 精彩金句

{quotes_md}

---

## 📱 社交媒体文案

### 🇨🇳 小红书 / 微信

{social_zh}

### 🌍 Twitter / LinkedIn

{social_en}

---
*本 Show Notes 由 Podcast Agent × Claude 自动生成*
"""

    return {
        "title_suggestions": title_suggestions,
        "summary": summary,
        "chapters": chapters,
        "key_takeaways": key_takeaways,
        "key_quotes": key_quotes,
        "show_notes_md": show_notes_md,
        "social_zh": social_zh,
        "social_en": social_en,
    }


def generate_show_notes(
    transcript: str,
    language: str = "zh",
    guest_name: str = "",
    episode_title: str = "",
    segments: list = None,
) -> dict:
    """
    生成播客 Show Notes 配套内容

    参数：
        transcript:     播客完整文字稿
        language:       语言 "zh" | "en"
        guest_name:     嘉宾姓名（可选）
        episode_title:  节目标题（可选）
        segments:       Whisper segments 列表（用于推算章节时间戳）

    返回：
        {
            "title_suggestions": [str x3],
            "summary": str,
            "chapters": [{"time": "MM:SS", "title": str}],
            "key_takeaways": [str x5],
            "key_quotes": [str x3],
            "show_notes_md": str,
            "social_zh": str,
            "social_en": str,
        }
    """
    print(f"   📄 生成 Show Notes...")

    # 推算章节时间戳
    chapters_hint = _estimate_chapters_from_segments(segments or [])

    # 尝试使用 Claude API
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        # 尝试从 .env 加载
        try:
            from dotenv import load_dotenv
            env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
            load_dotenv(env_path)
            api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        except Exception:
            pass

    if api_key:
        print(f"   🤖 使用 Claude API 生成...")
        try:
            result = _generate_with_claude(
                api_key=api_key,
                transcript=transcript,
                language=language,
                guest_name=guest_name,
                episode_title=episode_title,
                chapters_hint=chapters_hint,
            )
            if result:
                print(f"   ✅ Claude 生成完成")
                return result
        except Exception as e:
            print(f"   ⚠️ Claude API 调用失败: {e}，回退到简单模板")
    else:
        print(f"   ⚠️ 未找到 ANTHROPIC_API_KEY，使用简单模板生成")

    # 回退：简单模板
    result = _simple_template(
        transcript=transcript,
        language=language,
        guest_name=guest_name,
        episode_title=episode_title,
        chapters_hint=chapters_hint,
    )
    print(f"   ✅ Show Notes 模板生成完成")
    return result
