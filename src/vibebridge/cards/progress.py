"""Task progress card."""

from .base import card_base, markdown_element


def render_progress_card(task_id: str, provider: str, progress_text: str) -> dict:
    # Show last 3000 chars so markdown/code blocks aren't truncated mid-way
    shown = progress_text[-3000:] if len(progress_text) > 3000 else progress_text
    return card_base(
        header_title=f"⏳ 任务执行中 ({provider})",
        template="wathet",
        elements=[
            markdown_element(
                f"**Task ID:** `{task_id}`\n\n{shown}"
            ),
        ],
    )
