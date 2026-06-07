"""Task result card."""

from .base import card_base, markdown_element


def render_result_card(
    task_id: str, provider: str, result_text: str, files: list[str]
) -> dict:
    file_section = ""
    if files:
        file_section = "\n\n**生成文件:**\n" + "\n".join(f"- `{f}`" for f in files)

    # Render as raw markdown so code blocks, headers, lists etc. are properly formatted.
    # Cap at 8000 chars to stay within Feishu card limits (~30KB total).
    shown = result_text[:8000] if len(result_text) > 8000 else result_text

    content = f"**Task ID:** `{task_id}`\n\n{shown}{file_section}"

    return card_base(
        header_title=f"✅ 任务完成 ({provider})",
        template="green",
        elements=[
            markdown_element(content),
        ],
    )
