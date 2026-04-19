"""VibeBridge CLI."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from .config import Config, FeishuConfig, get_config
from .providers import build_providers

app = typer.Typer(help="VibeBridge - IM Gateway for AI Coding Agents")
console = Console()


@app.command()
def init(
    non_interactive: bool = typer.Option(False, "--non-interactive", "-n", help="Use environment variables without prompts"),
):
    """Interactive setup for VibeBridge."""
    console.print(Panel.fit("🔧 VibeBridge 初始化", style="bold blue"))

    cfg = Config()
    cfg.ensure_dirs()

    # Scan local providers
    console.print("\n[bold]🔍 扫描本地 AI 工具...[/bold]")
    scans = {
        "opencode": _has_binary("opencode") or _exists(Path.home() / ".nvm/versions/node/v24.14.0/bin/opencode"),
        "kimi": _check_kimi(),
        "claude": _has_binary("claude"),
        "openclaw": _check_openclaw(),
        "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
    }

    for name, ok in scans.items():
        icon = "✅" if ok else "❌"
        console.print(f"   {icon} {name:<10} {'检测到' if ok else '未检测到'}")

    # Feishu config
    console.print("\n[bold]✏️ 飞书配置[/bold]")
    if non_interactive:
        cfg.feishu.app_id = os.getenv("FEISHU_APP_ID", cfg.feishu.app_id)
        cfg.feishu.app_secret = os.getenv("FEISHU_APP_SECRET", cfg.feishu.app_secret)
        cfg.feishu.encrypt_key = os.getenv("FEISHU_ENCRYPT_KEY", cfg.feishu.encrypt_key)
        cfg.feishu.verification_token = os.getenv("FEISHU_VERIFICATION_TOKEN", cfg.feishu.verification_token)
        cfg.feishu.mode = os.getenv("FEISHU_MODE", cfg.feishu.mode)
        console.print("   已使用环境变量配置 (non-interactive mode)")
    else:
        cfg.feishu.app_id = Prompt.ask("App ID", default=cfg.feishu.app_id or os.getenv("FEISHU_APP_ID", ""))
        cfg.feishu.app_secret = Prompt.ask("App Secret", password=True, default=cfg.feishu.app_secret or os.getenv("FEISHU_APP_SECRET", ""))
        cfg.feishu.encrypt_key = Prompt.ask("Encrypt Key", password=True, default=cfg.feishu.encrypt_key or os.getenv("FEISHU_ENCRYPT_KEY", ""))
        cfg.feishu.verification_token = Prompt.ask("Verification Token", password=True, default=cfg.feishu.verification_token or os.getenv("FEISHU_VERIFICATION_TOKEN", ""))
        mode = Prompt.ask("连接模式", choices=["websocket", "webhook"], default=cfg.feishu.mode)
        cfg.feishu.mode = mode

    # Provider defaults
    enabled_providers = [k for k, v in scans.items() if v]
    if not enabled_providers:
        enabled_providers = ["opencode"]

    if non_interactive:
        default_provider = os.getenv("VB_DEFAULT_PROVIDER", enabled_providers[0])
        cfg.agents.default_provider = default_provider
    else:
        default_provider = Prompt.ask(
            "默认 Provider",
            choices=enabled_providers,
            default=enabled_providers[0],
        )
        cfg.agents.default_provider = default_provider

    cfg.agents.opencode.enabled = scans["opencode"]
    cfg.agents.kimi.enabled = scans["kimi"]
    cfg.agents.claude.enabled = scans["claude"]
    cfg.agents.openclaw.enabled = scans["openclaw"]
    cfg.agents.openrouter.enabled = scans["openrouter"]

    # Write config (convert Paths to strings for safe YAML)
    config_dict = cfg.model_dump()
    _convert_paths_to_strings(config_dict)
    with cfg.config_file.open("w", encoding="utf-8") as f:
        yaml.dump(config_dict, f, allow_unicode=True, sort_keys=False)


    mode = cfg.feishu.mode
    console.print(f"\n✅ 配置已保存到 [cyan]{cfg.config_file}[/cyan]")
    console.print("\n📋 下一步:")
    console.print("   1. 在飞书开发者后台配置事件订阅: https://open.feishu.cn/app")
    console.print("   2. 订阅事件: im.message.receive_v1")
    if mode == "webhook":
        console.print("   3. 请求 URL: http://your-machine-ip:8000/im/feishu/webhook")
    else:
        console.print("   3. WebSocket 模式无需配置公网 URL")
    console.print("\n🚀 运行 [bold]vibebridge start[/bold] 启动服务")


def _convert_paths_to_strings(obj):
    """Recursively convert Path objects to strings in a dict/list."""
    from pathlib import Path
    if isinstance(obj, dict):
        for key, value in list(obj.items()):
            if isinstance(value, Path):
                obj[key] = str(value)
            elif isinstance(value, (dict, list)):
                _convert_paths_to_strings(value)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, Path):
                obj[i] = str(item)
            elif isinstance(item, (dict, list)):
                _convert_paths_to_strings(item)


@app.command()
def start(
    host: str = "0.0.0.0",
    port: int = 8000,
    install: bool = typer.Option(False, help="Register as systemd user service"),
):
    """Start the VibeBridge server."""
    if install:
        _install_systemd_service(port)
        return

    console.print(f"🚀 Starting VibeBridge on {host}:{port}")
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "vibebridge.server:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    os.environ["PYTHONPATH"] = str(Path(__file__).parent.parent) + os.pathsep + os.environ.get("PYTHONPATH", "")
    subprocess.run(cmd, cwd=str(Path(__file__).parent.parent.parent))


@app.command()
def stop():
    """Stop the systemd user service."""
    subprocess.run(["systemctl", "--user", "stop", "vibebridge.service"], check=False)
    console.print("⏹️  vibebridge.service stopped")


@app.command()
def status():
    """Show service and provider health status."""
    # Service status
    result = subprocess.run(
        ["systemctl", "--user", "is-active", "vibebridge.service"],
        capture_output=True,
        text=True,
    )
    service_active = result.stdout.strip() == "active"
    console.print(f"{'🟢' if service_active else '🔴'} systemd service: {result.stdout.strip() or 'inactive'}")

    # Provider health
    cfg = get_config()
    providers = build_providers(cfg.agents)
    table = Table(title="Provider Health")
    table.add_column("Provider", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Message")

    import asyncio

    async def _check():
        for name, p in providers.items():
            ok, msg = await p.health_check()
            table.add_row(p.display_name, "✅ Healthy" if ok else "❌ Unhealthy", msg)

    asyncio.run(_check())
    console.print(table)


@app.command()
def logs(follow: bool = typer.Option(False, "-f", "--follow")):
    """View logs."""
    log_dir = Path.home() / ".local" / "share" / "vibebridge" / "logs"
    log_file = log_dir / "vibebridge.log"
    if not log_file.exists():
        console.print("No log file found.")
        raise typer.Exit(1)
    cmd = ["tail", "-n", "50"]
    if follow:
        cmd.append("-f")
    cmd.append(str(log_file))
    subprocess.run(cmd)


@app.command()
def test_openrouter():
    """Test all available OpenRouter models."""
    from .providers.openrouter import OpenRouterProvider
    
    console.print(Panel.fit("🧪 Testing OpenRouter Models", style="bold blue"))
    
    # Check API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        console.print("[red]❌ OPENROUTER_API_KEY environment variable not set[/red]")
        console.print("\n请设置环境变量:")
        console.print("  export OPENROUTER_API_KEY=your_api_key_here")
        console.print("\n或添加到 .env 文件:")
        console.print("  OPENROUTER_API_KEY=your_api_key_here")
        raise typer.Exit(1)
    
    # Create provider
    provider = OpenRouterProvider(api_key=api_key)
    
    # Test connection
    console.print("\n[bold]🔗 Testing OpenRouter connection...[/bold]")
    import asyncio
    
    async def run_tests():
        # Health check
        healthy, msg = await provider.health_check()
        if not healthy:
            console.print(f"[red]❌ Connection failed: {msg}[/red]")
            return
        
        console.print(f"[green]✅ Connection successful: {msg}[/green]")
        
        # Test all models
        console.print("\n[bold]🧪 Testing available models...[/bold]")
        console.print("This may take a minute...")
        
        results = await provider.test_all_models()
        
        if "error" in results:
            console.print(f"[red]❌ Error: {results['error']}[/red]")
            return
        
        # Display results
        console.print(f"\n[bold]📊 Results: {results['total_models']} total models available[/bold]")
        console.print(f"[bold]✅ {len(results['available_models'])} popular models tested[/bold]")
        
        # Create table
        table = Table(title="Model Test Results")
        table.add_column("Model", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Response", style="green")
        table.add_column("Tokens", style="yellow")
        
        for model, test_result in results["test_results"].items():
            if test_result.get("available"):
                status = "✅ Available"
                response = test_result.get("response", "N/A")[:30]
                tokens = str(test_result.get("tokens", 0))
            else:
                status = "❌ Unavailable"
                response = test_result.get("error", "Unknown error")[:30]
                tokens = "N/A"
            
            table.add_row(model, status, response, tokens)
        
        console.print(table)
        
        # Summary
        available_count = sum(1 for r in results["test_results"].values() if r.get("available"))
        total_tested = len(results["test_results"])
        
        console.print(f"\n[bold]📈 Summary:[/bold]")
        console.print(f"  Available: {available_count}/{total_tested} models")
        console.print(f"  Success rate: {(available_count/total_tested)*100:.1f}%")
        
        # Save results to file
        results_file = Path.home() / ".config" / "vibebridge" / "openrouter_test_results.json"
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        import json
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        console.print(f"\n[green]✅ Results saved to: {results_file}[/green]")
        
        # Clean up
        await provider.close()
    
    asyncio.run(run_tests())


@app.command()
def doctor():
    """Run diagnostic checks."""
    table = Table(title="VibeBridge Doctor")
    table.add_column("Check", style="cyan")
    table.add_column("Result", style="bold")

    cfg = get_config()
    table.add_row("Config file", "✅ Exists" if cfg.config_file.exists() else "❌ Missing")
    table.add_row("Python", f"✅ {sys.version.split()[0]}")
    table.add_row("Node", _node_version() or "❌ Not found")
    table.add_row("OpenCode", "✅ Found" if _has_binary("opencode") else "❌ Not found")
    table.add_row("Kimi", "✅ Found" if _check_kimi() else "❌ Not found")
    table.add_row("Claude", "✅ Found" if _has_binary("claude") else "❌ Not found")
    table.add_row("OpenClaw Gateway", "✅ Running" if _check_openclaw() else "❌ Not reachable")
    table.add_row("OpenRouter API Key", "✅ Configured" if os.getenv("OPENROUTER_API_KEY") else "❌ Not configured")

    console.print(table)


# Helpers

def _has_binary(name: str) -> bool:
    return shutil.which(name) is not None


def _exists(path: Path) -> bool:
    return path.exists()


def _check_kimi() -> bool:
    return _has_binary("kimi")


def _check_openclaw() -> bool:
    import httpx

    try:
        resp = httpx.get("http://127.0.0.1:18789/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


def _node_version() -> str | None:
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _install_systemd_service(port: int):
    service_dir = Path.home() / ".config" / "systemd" / "user"
    service_dir.mkdir(parents=True, exist_ok=True)
    service_file = service_dir / "vibebridge.service"

    python_path = Path(sys.executable).parent / "python"
    script_dir = Path(__file__).parent.parent.resolve()

    content = f"""[Unit]
Description=VibeBridge - IM Gateway for AI Coding Agents
After=network-online.target

[Service]
Type=simple
ExecStart={python_path} -m uvicorn vibebridge.server:app --host 0.0.0.0 --port {port}
WorkingDirectory={script_dir}
Restart=always
RestartSec=5
Environment=PATH={os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin')}
Environment=PYTHONPATH={script_dir}

[Install]
WantedBy=default.target
"""
    service_file.write_text(content, encoding="utf-8")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "--user", "enable", "--now", "vibebridge.service"], check=False)
    console.print(f"✅ Installed and started {service_file}")


def main():
    app()


if __name__ == "__main__":
    main()
