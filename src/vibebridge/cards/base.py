"""Base card rendering utilities."""

from __future__ import annotations


def card_base(header_title: str, template: str, elements: list[dict]) -> dict:
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": header_title},
            "template": template,
        },
        "elements": elements,
    }


def markdown_element(text: str) -> dict:
    return {"tag": "div", "text": {"tag": "lark_md", "content": text}}
