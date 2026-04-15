"""Error card."""

from .base import card_base, markdown_element


def render_error_card(task_id: str | None, error_text: str) -> dict:
    tid = f"`{task_id}`" if task_id else "N/A"
    return card_base(
        header_title="❌ 任务失败",
        template="red",
        elements=[
            markdown_element(f"**Task ID:** {tid}\n**错误:** {error_text[:800]}"),
        ],
    )
