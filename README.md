# GigaJoyce Docs Setup

This repository contains a documentation skeleton for the GigaJoyce Discord bot.
You can move these files to your project root or keep them in a `docs/` subfolder.

## Quick start
1. Create a Python virtual environment.
2. Install doc requirements: `pip install -r requirements-docs.txt`
3. Build and serve: `mkdocs serve`
4. Open http://127.0.0.1:8000 to view the docs.

## Structure
- `mkdocs.yml` config file for the site
- `docs/` Markdown sources
- `docs/api/` is auto-populated by mkdocstrings at build time
