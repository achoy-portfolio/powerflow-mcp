# chat.py — AI Agent Power Flow Solver

An autonomous agent that connects DeepSeek to the pandapower
MCP server and attempts to solve voltage violations on the
IEEE 30-bus challenge network.

## What it does

- Launches the MCP server (`powerflow_mcp/pandapower/run_pf.py`)
- Connects a DeepSeek LLM via the OpenAI-compatible API
- The agent iteratively runs power flow, checks violations,
  and adjusts generators/shunts/taps to fix voltage issues
- Prints tool calls, results, and token usage in the terminal

## Requirements

- A DeepSeek API key in `.env`:
  ```
  deepseek_key=your-key-here
  ```

## How to run

```bash
source .venv/bin/activate
python chat.py
```

The agent runs autonomously — no user input needed. It will
print its reasoning and actions as it works through the problem.
