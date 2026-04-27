#!/usr/bin/env python3
"""
播客收件箱自动监控
检测到 音频 + 同名.txt 就自动处理，完成后发 Telegram 通知
"""

import os
import sys
import json
import time
import logging
import requests
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

INBOX_DIR = Path.home() / "Desktop" / "播客待处理"
OUTPUT_DIR = Path.home() / "Desktop" / "播客成品"
AGENT_DIR = Path(__file__).parent
STATE_FILE = AGENT_DIR / ".inbox_state.json"

BOT_TOKEN = "8518954174:AAHIWuxR4DDTtqxqjFzeUi33WxFUtnLyQQc"
CHAT_ID = "8727904480"

AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".ogg", ".opus", ".aac", ".flac"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [watcher] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(AGENT_DIR / "inbox_watcher.log"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)


def send_telegram(text: str):
    """发 Telegram 消息"""
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        log.warning(f"Telegram 通知失败: {e}")


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"processed": []}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def parse_description(txt_path: Path) -> dict:
    """解析描述文件，返回嘉宾信息 dict"""
    info = {
        "guest": "",
        "institution": "",
        "topic": "",
        "intro": "",
        "title": "",
        "language": "zh",
    }
    try:
        text = txt_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("嘉宾姓名：") or line.startswith("嘉宾姓名:"):
                info["guest"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            elif line.startswith("所在机构：") or line.startswith("所在机构:"):
                info["institution"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            elif line.startswith("研究方向：") or line.startswith("研究方向:"):
                info["topic"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            elif line.startswith("一句话介绍：") or line.startswith("一句话介绍:"):
                info["intro"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            elif line.startswith("节目标题：") or line.startswith("节目标题:"):
                info["title"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            elif line.startswith("语言：") or line.startswith("语言:"):
                info["language"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
    except Exception as e:
        log.warning(f"解析描述文件失败: {e}")
    return info


def process_file(audio_path: Path, txt_path: Path):
    """处理单个音频文件"""
    stem = audio_path.stem
    info = parse_description(txt_path)
    lang = info.get("language", "zh")
    guest = info.get("guest", "")
    title = info.get("title", "") or stem

    log.info(f"▶️  开始处理: {audio_path.name}")
    log.info(f"   嘉宾: {guest or '未填写'} | 语言: {lang}")

    # 通知开始
    send_telegram(
        f"🎙️ <b>开始处理播客</b>\n"
        f"📂 {audio_path.name}\n"
        f"👤 嘉宾：{guest or '未填写'}\n"
        f"⏳ 处理中，请稍等..."
    )

    start_time = time.time()

    # 构建 podcast_agent.py edit 命令
    cmd = [
        "python3", str(AGENT_DIR / "podcast_agent.py"), "edit",
        str(audio_path),
        "--denoise", "medium",
    ]
    if guest:
        cmd += ["--guest", guest]
    if info.get("institution"):
        cmd += ["--institution", info["institution"]]
    if info.get("topic"):
        cmd += ["--topic", info["topic"]]
    if info.get("intro"):
        cmd += ["--intro-text", info["intro"]]
    if title:
        cmd += ["--title", title]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(AGENT_DIR)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(AGENT_DIR),
        env=env,
    )

    elapsed = time.time() - start_time
    elapsed_min = elapsed / 60

    if result.returncode == 0:
        # 找到生成的成品文件
        project_dir = OUTPUT_DIR / stem
        output_files = list(project_dir.glob("*.mp3")) if project_dir.exists() else []
        notes_files = list(project_dir.glob("*show_notes.md")) if project_dir.exists() else []

        latest_mp3 = max(output_files, key=lambda f: f.stat().st_mtime) if output_files else None
        has_notes = bool(notes_files)

        log.info(f"✅ 处理完成: {stem} ({elapsed_min:.1f}分钟)")

        send_telegram(
            f"✅ <b>播客处理完成！</b>\n"
            f"📻 {title or stem}\n"
            f"⏱️ 耗时：{elapsed_min:.1f} 分钟\n"
            f"📁 成品：~/Desktop/播客成品/{stem}/\n"
            f"{'📄 Show Notes 已生成' if has_notes else ''}"
        )

        # 把 txt 也移到成品文件夹
        if project_dir.exists():
            dest = project_dir / txt_path.name
            if not dest.exists():
                txt_path.rename(dest)
    else:
        log.error(f"❌ 处理失败: {stem}")
        log.error(result.stderr[-500:])
        send_telegram(
            f"❌ <b>播客处理失败</b>\n"
            f"📂 {audio_path.name}\n"
            f"错误：{result.stderr[-200:]}"
        )


def scan_inbox(state: dict) -> list:
    """扫描收件箱，找出待处理的音频+描述对"""
    pending = []
    if not INBOX_DIR.exists():
        return pending

    for f in sorted(INBOX_DIR.iterdir()):
        if f.suffix.lower() not in AUDIO_EXTS:
            continue
        if f.name == "说明.txt":
            continue

        # 跳过已处理
        if str(f) in state["processed"]:
            continue

        # 找同名描述文件（任意非音频文本文件均可）
        txt = next(
            (p for p in INBOX_DIR.iterdir()
             if p.stem == f.stem and p != f and p.suffix.lower() not in AUDIO_EXTS),
            None
        )
        if txt is None:
            continue  # 还没有描述文件，等待

        pending.append((f, txt))

    return pending


def main():
    log.info("🚀 播客收件箱监控启动")
    log.info(f"   监控目录: {INBOX_DIR}")
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    state = load_state()

    while True:
        try:
            pending = scan_inbox(state)
            for audio_path, txt_path in pending:
                process_file(audio_path, txt_path)
                state["processed"].append(str(audio_path))
                save_state(state)

        except Exception as e:
            log.error(f"扫描出错: {e}")

        time.sleep(30)  # 每30秒扫一次


if __name__ == "__main__":
    main()
