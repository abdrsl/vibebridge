"""Progress card creation."""

from __future__ import annotations


def create_progress_card(
    agent_name: str,
    task_name: str,
    percent: int,
    status: str,
    current_step: str,
    total_steps: int,
    elapsed_seconds: float,
    latest_output: str,
    bot_name: str,
) -> dict:
    template = "wathet" if percent < 100 else "green"
    elements = []
    if status:
        elements.append(
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**状态:** {status}"}}
        )
    if current_step:
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**当前步骤:** {current_step} / {total_steps}",
                },
            }
        )
    if elapsed_seconds:
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**已用时:** {elapsed_seconds:.1f}s",
                },
            }
        )
    if latest_output:
        elements.append(
            {"tag": "div", "text": {"tag": "lark_md", "content": latest_output}}
        )

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"⏳ {agent_name} {percent}% {task_name}",
            },
            "template": template,
        },
        "elements": elements,
    }
