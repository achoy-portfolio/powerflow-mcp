# Powerflow MCP

An MCP server that wraps [pandapower](https://www.pandapower.org/) for running power flow analysis via AI agents.

## Tools

The MCP server exposes three tools:

- `get_available_networks` — list available test networks (IEEE cases, CIGRE, PEGASE, RTE)
- `run_pf` — run power flow simulation on a selected network
- `analysis_pf_result` — get voltage profile, line loading, and power summary from a solved network

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

Add your API key to `.env`:

```
deepseek_key=your-key-here
```

Run the demo agent:

```bash
python chat.py
```

This connects DeepSeek to the pandapower MCP server and runs a power flow analysis on the IEEE 14-bus network.

### As an MCP server

Configure any MCP client to connect:

```json
{
  "mcpServers": {
    "pandapower": {
      "command": "uv",
      "args": ["run", "powerflow_mcp/pandapower/run_pf.py"]
    }
  }
}
```

## Dependencies

- pandapower
- mcp
- openai
- python-dotenv
