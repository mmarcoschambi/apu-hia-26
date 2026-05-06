from __future__ import annotations

import json
import html
import os
from typing import Iterable, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()


def escape_html(text: str) -> str:
    return html.escape(text, quote=False)


def chunk_text(text: str, limit: int = 4000) -> list[str]:
    return [text[i : i + limit] for i in range(0, len(text), limit)] or [""]


def telegram_send(
    text: str,
    parse_mode: str = "HTML",
    disable_preview: bool = True,
    chat_id: Optional[str] = None,
) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    success = True
    for chunk in chunk_text(text):
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": chunk,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": disable_preview,
                    },
                )
                if r.status_code != 200:
                    success = False
        except Exception:
            success = False
    return success


def telegram_send_html(text: str, chat_id: Optional[str] = None) -> bool:
    return telegram_send(escape_html(text), parse_mode="HTML", chat_id=chat_id)


def send_message_with_buttons(
    text: str,
    buttons: list[list[dict[str, str]]],
    chat_id: Optional[str] = None,
    parse_mode: str = "HTML",
) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    markup = {"inline_keyboard": buttons}
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "reply_markup": markup,
                    "disable_web_page_preview": True,
                },
            )
            return r.status_code == 200
    except Exception:
        return False


def edit_message(
    chat_id: str,
    message_id: int,
    text: str,
    parse_mode: str = "HTML",
) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return False
    url = f"https://api.telegram.org/bot{token}/editMessageText"
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": text,
                    "parse_mode": parse_mode,
                },
            )
            return r.status_code == 200
    except Exception:
        return False


def answer_callback(callback_query_id: str, text: str = "") -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return False
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                url, json={"callback_query_id": callback_query_id, "text": text}
            )
            return r.status_code == 200
    except Exception:
        return False


def get_updates(offset: Optional[int] = None, timeout: int = 20) -> list[dict]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return []
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    try:
        with httpx.Client(timeout=timeout + 5) as client:
            r = client.get(url, params=params)
            data = r.json()
            return data.get("result", []) if data.get("ok") else []
    except Exception:
        return []


def dump_json(path, payload) -> None:
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, default=str))
