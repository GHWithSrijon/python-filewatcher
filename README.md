# python-filewatcher

Lightweight Python utility to watch filesystem changes and react to them. Useful for automating tasks, live-reloading, syncing, or triggering custom handlers when files are created, modified, or deleted.

## Features

- Watch files or directories (optionally recursive)
- Filter by glob patterns or file extensions
- Debounce rapid events
- Run shell commands or Python callbacks on events
- Small, easily embeddable API and simple CLI

## Installation

Install from PyPI (if published) or locally:

pip install python-filewatcher

Or from a local checkout:

pip install -e .

## Quickstart

CLI example:

```bash
# watch a directory and run a command when a change happens
filewatcher --path ./src --pattern "*.py" --command "pytest -q" --recursive --debounce 500
```

## Configuration options

- paths: list of paths to watch
- patterns: glob patterns (e.g. ["*.py", "*.md"])
- recursive: bool, descend into subdirectories
- debounce_ms: integer, milliseconds to batch rapid events
- command: optional shell command to run on events
- callback: Python callable invoked with event metadata

## Examples
