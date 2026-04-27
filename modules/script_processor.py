"""
脚本处理模块 - 用 Claude 把原始内容转成播客脚本
"""
import anthropic
import os

def get_client():
    key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    # 如果没有 Anthropic key，尝试从 OpenClaw 环境获取
    return anthropic.Anthropic(api_key=key) if key else None

def process_script(
    content: str,
    language: str = "zh",
    format: str = "solo",  # "solo" 单人 | "dialogue" 对话
    topic: str = "",
    duration_hint: str = "5-10分钟"
) -> str:
    """
    将原始内容转化为播客脚本
    """
    lang_name = "中文" if language == "zh" else "English"
    
    if format == "solo":
        format_desc = "单人旁白风格，像在和听众亲切聊天" if language == "zh" else "solo narrator style, conversational and engaging"
        structure_desc = """
结构要求：
- 开场白（15秒）：吸引人的钩子/问题
- 主体内容（分2-3个小节）
- 结尾（30秒）：总结 + 行动呼吁
- 在每个自然停顿处加 [PAUSE] 标记
""" if language == "zh" else """
Structure:
- Hook/Opening (15s): engaging question or statement  
- Main content (2-3 sections)
- Outro (30s): summary + call to action
- Add [PAUSE] at natural breaks
"""
    else:
        format_desc = "双人对话风格，HOST 和 GUEST 角色" if language == "zh" else "dialogue format with HOST and GUEST"
        structure_desc = """
结构要求：
- 用 HOST: 和 GUEST: 标记发言人
- 开场互动
- 自然的对话节奏，问答穿插
- 结尾总结
- 在角色切换时加 [PAUSE]
""" if language == "zh" else """
Structure:
- Use HOST: and GUEST: speaker labels
- Natural back-and-forth conversation
- Questions and answers woven in
- Closing remarks
- Add [PAUSE] on speaker changes
"""

    if language == "zh":
        prompt = f"""你是一位专业的播客脚本编辑。

任务：将以下原始内容改编为高质量的播客脚本。

原始内容：
{content}

要求：
- 语言：{lang_name}
- 风格：{format_desc}
- 预计时长：{duration_hint}
- 话题：{topic or "从内容中提取"}
{structure_desc}

注意：
- 口语化表达，避免书面语
- 节奏感强，适合音频收听
- 不要用 markdown 格式，纯文本
- 直接输出脚本内容，不要加任何解释"""
    else:
        prompt = f"""You are a professional podcast script editor.

Task: Transform the following content into a high-quality podcast script.

Source content:
{content}

Requirements:
- Language: {lang_name}
- Style: {format_desc}
- Target duration: {duration_hint}
- Topic: {topic or "extract from content"}
{structure_desc}

Notes:
- Conversational tone, not formal writing
- Good rhythm for audio listening
- Plain text only, no markdown
- Output the script directly, no explanations"""

    client = get_client()
    if client is None:
        # 没有 Claude key，返回简单格式化版本
        print("⚠️ 未找到 Anthropic API Key，跳过 AI 脚本优化，使用原始内容")
        return content
    
    print("✍️ AI 正在生成播客脚本...")
    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    
    script = message.content[0].text.strip()
    print(f"✅ 脚本生成完成，长度: {len(script)} 字")
    return script
