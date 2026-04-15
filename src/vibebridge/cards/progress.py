"""Task progress card."""

from .base import card_base, markdown_element


def render_progress_card(task_id: str, provider: str, progress_text: str) -> dict:
    return card_base(
        header_title=f"⏳ 任务执行中 ({provider})",
        template="wathet",
        elements=[
            markdown_element(
                f"**Task ID:** `{task_id}`\n"
                f"```\n{progress_text[-800:]}\n```"
            ),
        ],
    )
