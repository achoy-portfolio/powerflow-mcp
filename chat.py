import asyncio
import json
import os

from dotenv import load_dotenv
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_header(text):
    width = 60
    print(f"\n{BLUE}{'═' * width}")
    print(f"  {text}")
    print(f"{'═' * width}{RESET}\n")


def print_tool_call(name, args):
    print(f"  {YELLOW}▶ {name}{RESET}")
    if args:
        for k, v in args.items():
            print(f"    {DIM}{k}: {v}{RESET}")


def print_tool_result(text, max_lines=15):
    lines = text.strip().split("\n")
    for line in lines[:max_lines]:
        print(f"    {GREEN}{line}{RESET}")
    if len(lines) > max_lines:
        print(f"    {DIM}... ({len(lines) - max_lines} more lines){RESET}")


def print_tokens(usage, total_in, total_out):
    print(
        f"  {DIM}[tokens] "
        f"{usage.prompt_tokens} in / {usage.completion_tokens} out  "
        f"(total: {total_in} in / {total_out} out){RESET}"
    )


async def main():
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "powerflow_mcp/pandapower/run_pf.py"],
        env={
            **os.environ,
            "PYTHONWARNINGS": "ignore",
            "MCP_LOG_LEVEL": "ERROR",
        },
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema
                        or {"type": "object", "properties": {}},
                    },
                }
                for tool in tools_result.tools
            ]

            client = OpenAI(
                api_key=os.getenv("deepseek_key"),
                base_url="https://api.deepseek.com",
            )

            prompt = (
                "You are a power systems engineer solving voltage"
                " violations on the ieee30_challenge network.\n\n"
                "This is a modified IEEE 30-bus system with heavy"
                " loads causing BOTH overvoltage and undervoltage"
                " problems. Simply lowering generators won't work"
                " — you'll need a mix of strategies.\n\n"
                "RULES:\n"
                "- Voltage limits: 0.97 - 1.03 p.u. (tight band)\n"
                "- 3 tools: set_gen_voltage, add_shunt (negative"
                " q_mvar = capacitor to raise voltage), adjust_trafo_tap\n"
                "- Each action has a cost — minimize total cost\n"
                "- You can reset_network to start over\n\n"
                "STEPS:\n"
                "1. read_solution_log for past attempts\n"
                "2. run_pf on ieee30_challenge\n"
                "3. check_violations (v_min=0.97, v_max=1.03)\n"
                "4. Inspect generators, transformers, shunts\n"
                "5. Plan: which buses need voltage raised vs"
                " lowered? What's the cheapest fix for each?\n"
                "6. Execute changes one at a time with rerun_pf,"
                " check_violations, and log_action after each\n"
                "7. If stuck, reset_network and try differently\n"
                "8. Summarize approach and final cost\n\n"
                "Think carefully. Explain your reasoning at each"
                " step."
            )

            messages = [{"role": "user", "content": prompt}]

            print_header("Power Flow Voltage Correction Agent")
            print(f"{DIM}Prompt:{RESET} {prompt}\n")

            total_in = 0
            total_out = 0
            step_num = 0

            while True:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    tools=openai_tools,
                )

                if response.usage:
                    total_in += response.usage.prompt_tokens
                    total_out += response.usage.completion_tokens
                    print_tokens(response.usage, total_in, total_out)

                choice = response.choices[0]

                if choice.finish_reason == "stop" or not choice.message.tool_calls:
                    print_header("Agent Summary")
                    print(f"{choice.message.content}\n")
                    print(f"{DIM}{'─' * 60}")
                    print(f"  Total tokens: {total_in} in / {total_out} out")
                    print(f"  Total: {total_in + total_out}{RESET}")
                    break

                messages.append(choice.message)

                for tool_call in choice.message.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)

                    # Print step separator for key actions
                    if fn_name in ("rerun_pf", "run_pf"):
                        step_num += 1
                        print(f"\n{BOLD}── Step {step_num} {'─' * 45}{RESET}")

                    print_tool_call(fn_name, fn_args)

                    result = await session.call_tool(fn_name, arguments=fn_args)
                    result_text = "\n".join(
                        c.text for c in result.content if hasattr(c, "text") and c.text
                    )

                    print_tool_result(result_text)

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result_text,
                        }
                    )


if __name__ == "__main__":
    asyncio.run(main())
