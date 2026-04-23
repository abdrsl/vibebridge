# Contributing to VibeBridge

Thank you for your interest in contributing!

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/akliedrak/vibebridge.git`
3. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -e ".[dev]"
   ```

## Development Workflow

1. Create a branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Run tests: `pytest tests/ -v`
4. Run linting: `ruff check src/ tests/`
5. Commit and push
6. Open a Pull Request

## Code Style

- Follow PEP 8
- Use `ruff` for formatting and linting
- Add tests for new features
- Update documentation as needed

## Reporting Issues

Please use GitHub Issues with a clear description and steps to reproduce.
