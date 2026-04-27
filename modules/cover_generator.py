"""
播客封面生成模块 - gpt-image-2 生成背景 + Pillow 合成文字排版
输出 3000x3000px 高质量封面（Apple Podcasts / Spotify 标准）
"""

import os
import base64
import textwrap
from pathlib import Path
from io import BytesIO
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

try:
    import openai
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    DEPS_OK = True
except ImportError:
    DEPS_OK = False

SIZE = 3000  # 3000x3000px
ASSETS_DIR = Path(__file__).parent.parent / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"


def _get_font(size: int, bold: bool = False):
    """加载字体，找不到用系统默认"""
    # 尝试系统字体路径（macOS）
    candidates = []
    if bold:
        candidates = [
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    else:
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _generate_bg_prompt(guest: str, topic: str, institution: str, language: str = "zh") -> str:
    """封面背景提示词 - 科研面对面风格：卡通可爱+浅色+对话感"""
    topic_hint = topic or "science research"

    # 根据话题选择相关科学道具
    prop_map = [
        ("化学", "a cute cartoon chemistry flask bubbling with colorful liquid, molecular models"),
        ("材料", "cute crystal structures, glowing atomic lattice models"),
        ("AI", "a friendly cartoon robot with antenna, neural network glow effects"),
        ("生物", "cute DNA helix, cartoon microscope"),
        ("物理", "cartoon atom with orbiting electrons, wave patterns"),
        ("能源", "solar panels, glowing energy crystals"),
        ("医学", "cute cartoon microscope, red cross"),
        ("数学", "floating geometric shapes, equation bubbles"),
        ("光", "prism splitting light, photon sparkles"),
    ]
    props = "a cute cartoon robot scientist with a microphone, floating science icons"
    for kw, p in prop_map:
        if kw in topic_hint:
            props = p + ", plus a cute microphone icon"
            break

    prompt = f"""A charming, professional podcast cover art illustration for a Chinese science interview podcast.

Visual style reference: similar to modern Chinese science podcast covers — cute cartoon characters, clean layout, warm pastel tones.

Specific requirements:
- Background: soft warm gradient — pale sky blue (#e8f4f8) to creamy white, OR light warm peach/cream — NOT dark, NOT white pure white
- Main visual: {props}
- Topic context: {topic_hint}
- 2-3 small speech bubble icons (white with dots "...") floating near the character — suggesting conversation/interview
- Small sparkle stars ✦ scattered lightly around
- Flat cartoon illustration style — bold clean outlines, slightly rounded shapes, friendly and approachable
- Color palette: soft blue, warm orange/coral, light yellow accents — cheerful and clean
- NO text, NO letters, NO numbers in the image
- Leave TOP 30% of image mostly clear (light background only) — for guest name text
- Leave BOTTOM 20% clear — for show name text
- Character and props placed in CENTER to lower-center of image
- Square format (1:1), high quality

Overall feel: warm, curious, intellectual but approachable — like a friendly science conversation"""

    return prompt


def generate_cover(
    show_name: str = "科研面对面",
    guest_name: str = "",
    institution: str = "",
    topic: str = "",
    episode_num: str = "",
    language: str = "zh",
    output_path: str = None,
    model: str = "dall-e-3",
) -> str:
    """
    生成播客封面图
    返回输出文件路径（PNG）
    """
    if not DEPS_OK:
        raise ImportError("请安装: pip3 install openai pillow --break-system-packages")

    if output_path is None:
        output_path = str(ASSETS_DIR / "cover_latest.png")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    print(f"🎨 生成封面: {guest_name or show_name}")

    # === Step 1: gpt-image-2 生成背景 ===
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    prompt = _generate_bg_prompt(guest_name, topic, institution, language)

    print("   ⏳ gpt-image-2 生成背景中...")
    # dall-e-3 用 revised_prompt，gpt-image 系列用 output_format
    gen_kwargs = dict(model=model, prompt=prompt, n=1, response_format="b64_json")
    if model == "dall-e-3":
        gen_kwargs.update(size="1024x1024", quality="hd")
    else:
        gen_kwargs.update(size="1024x1024", quality="high", output_format="png")
        del gen_kwargs["response_format"]

    response = client.images.generate(**gen_kwargs)
    img_b64 = response.data[0].b64_json
    bg_img = Image.open(BytesIO(base64.b64decode(img_b64))).convert("RGBA")
    bg_img = bg_img.resize((SIZE, SIZE), Image.LANCZOS)
    print("   ✅ 背景生成完成")

    # === Step 2: Pillow 文字排版叠加（仿参考封面布局）===
    canvas = bg_img.copy()
    draw = ImageDraw.Draw(canvas)

    # 顶部轻微半透白遮罩（让嘉宾名字区域更清晰）
    top_overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    td = ImageDraw.Draw(top_overlay)
    for i in range(500):
        alpha = int(120 * ((500 - i) / 500) ** 2)
        td.rectangle([(0, i), (SIZE, i + 1)], fill=(255, 255, 255, alpha))
    canvas = Image.alpha_composite(canvas, top_overlay)

    # 底部白色渐变（节目名区域）
    bot_overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bot_overlay)
    for i in range(600):
        alpha = int(200 * (i / 600) ** 1.5)
        bd.rectangle([(0, SIZE - 600 + i), (SIZE, SIZE - 600 + i + 1)], fill=(255, 255, 255, alpha))
    canvas = Image.alpha_composite(canvas, bot_overlay)
    draw = ImageDraw.Draw(canvas)

    # 配色
    col_blue   = (30, 60, 140, 255)   # 深蓝 #1e3c8c
    col_orange = (240, 90, 30, 255)   # 橙   #f05a1e
    col_mid    = (60, 90, 160, 220)   # 中蓝

    # === 顶部：嘉宾姓名（大字，仿 Timothy Noël 风格）===
    if guest_name:
        name_font = _get_font(260, bold=True)
        name_lines = textwrap.wrap(guest_name, width=10)
        y = 80
        for line in name_lines[:2]:
            lw = draw.textlength(line, font=name_font) if hasattr(draw, 'textlength') else SIZE//2
            # 白色描边增加可读性
            for dx, dy in [(-4,0),(4,0),(0,-4),(0,4)]:
                draw.text(((SIZE-lw)/2+dx, y+dy), line, font=name_font, fill=(255,255,255,200))
            draw.text(((SIZE-lw)/2, y), line, font=name_font, fill=col_blue)
            y += 290

    # === 机构名（嘉宾名下，橙色）===
    if institution:
        inst_font = _get_font(95, bold=False)
        iw = draw.textlength(institution, font=inst_font) if hasattr(draw, 'textlength') else 400
        y_inst = 80 + 290 * min(len(textwrap.wrap(guest_name, width=10)[:2]), 2) + 10
        draw.text(((SIZE-iw)/2, y_inst), institution, font=inst_font, fill=col_orange)

    # === 底部：节目名（大字居中）===
    show_font = _get_font(160, bold=True)
    sw = draw.textlength(show_name, font=show_font) if hasattr(draw, 'textlength') else 400
    draw.text(((SIZE-sw)/2, SIZE-220), show_name, font=show_font, fill=col_blue)

    # === 集数角标（左下小字）===
    if episode_num:
        ep_font = _get_font(80, bold=False)
        draw.text((120, SIZE-200), f"EP.{episode_num}", font=ep_font, fill=col_mid)

    # === 话题标签（右下小字）===
    if topic:
        t_short = topic if len(topic) <= 16 else topic[:14] + "…"
        t_font = _get_font(75, bold=False)
        tw = draw.textlength(t_short, font=t_font) if hasattr(draw, 'textlength') else 300
        draw.text((SIZE-tw-120, SIZE-200), t_short, font=t_font, fill=col_mid)

    # === Step 3: 保存 ===
    final = canvas.convert("RGB")
    final.save(output_path, "PNG", quality=95, optimize=True)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"   ✅ 封面已保存: {output_path} ({size_mb:.1f} MB)")
    return output_path
