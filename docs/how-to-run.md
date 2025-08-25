# How to run

## Requirements
- Python 3.11 or 3.12
- Discord bot token in an environment variable named `DISCORD_TOKEN`
- Optional: database connection string if your setup uses one

## Steps
1. Create and activate a virtualenv
2. Install runtime dependencies of the bot
3. Export `DISCORD_TOKEN`
4. Run `python main.py`

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DISCORD_TOKEN=xxx
python main.py
```
