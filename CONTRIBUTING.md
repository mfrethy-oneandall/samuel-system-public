# Contributing

Thanks for your interest in Samuel! This repo hosts a small Python MCP server plus helper scripts. Contributions that improve reliability, docs, or developer ergonomics are welcome.

## How to Contribute

### Reporting Issues

1. Open an [issue](../../issues) with a clear description of the problem.
2. Include reproduction steps (commands you ran, inputs provided).
3. Share environment details: OS, Python version, and Home Assistant version if relevant.

### Suggesting Improvements

1. Open an [issue](../../issues) describing the current behavior and what you want to improve.
2. Explain why the change is useful (developer experience, stability, clarity).
3. If possible, include a code or config snippet to illustrate the idea.

### Pull Requests

PRs are welcome for:

- Bug fixes in the MCP server or diagnostics tools
- Documentation improvements
- Small developer-experience tweaks

Before submitting a PR:

1. Install deps: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
2. Run basic checks: `python -m compileall samuel` (ensures syntax) and `python -m samuel --help` (should start without errors)
3. Keep changes focused — one concern per PR
4. Update docs if behavior or setup changes

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold it.
