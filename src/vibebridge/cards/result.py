"""Task result card."""

from .base import card_base, markdown_element


def render_result_card(
    task_id: str, provider: str, result_text: str, files: list[str]
) -> dict:
    file_section = ""
    if files:
        file_section = "\n**生成文件:**\n" + "\n".join(f"- `{f}`" for f in files)

    content = f"**Task ID:** `{task_id}`\n**结果:**\n```\n{result_text[:2000]}\n```{file_section}"

    return card_base(
        header_title=f"✅ 任务完成 ({provider})",
        template="green",
        elements=[
            markdown_element(content),
        ],
    )
