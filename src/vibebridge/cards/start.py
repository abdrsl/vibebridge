"""Task start card."""

from .base import card_base, markdown_element


def render_start_card(task_id: str, provider: str, prompt_preview: str) -> dict:
    return card_base(
        header_title=f"🚀 任务已创建 ({provider})",
        template="blue",
        elements=[
            markdown_element(
                f"**Task ID:** `{task_id}`\n"
                f"**Provider:** {provider}\n"
                f"**Prompt:** {prompt_preview[:300]}"
            ),
        ],
    )
