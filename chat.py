import asyncio
import json
import os

from dotenv import load_dotenv
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()


async def main():
    # Connect to the pandapower MCP server
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "powerflow_mcp/pandapower/run_pf.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Discover available tools from the MCP server
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

            # Set up DeepSeek client (OpenAI-compatible API)
            client = OpenAI(
                api_key=os.getenv("deepseek_key"),
                base_url="https://api.deepseek.com",
            )

            prompt = (
                "You are a power systems engineer. "
                "First list the available networks, then run power flow on the case14 "
                "(IEEE 14-bus) network and analyze the results. "
                "Explain what the results mean."
            )

            messages = [{"role": "user", "content": prompt}]
            print(f"User: {prompt}\n")

            total_prompt_tokens = 0
            total_completion_tokens = 0

            # Agentic loop
            while True:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    tools=openai_tools,
                )

                # Track tokens
                if response.usage:
                    total_prompt_tokens += response.usage.prompt_tokens
                    total_completion_tokens += response.usage.completion_tokens
                    print(
                        f"  [tokens] this call: {response.usage.prompt_tokens} in / "
                        f"{response.usage.completion_tokens} out | "
                        f"running total: {total_prompt_tokens} in / "
                        f"{total_completion_tokens} out"
                    )

                choice = response.choices[0]

                # If no tool calls, print final response and exit
                if choice.finish_reason == "stop" or not choice.message.tool_calls:
                    print(f"\nDeepSeek: {choice.message.content}")
                    print(
                        f"\n--- Token Usage ---\n"
                        f"Prompt tokens:     {total_prompt_tokens}\n"
                        f"Completion tokens: {total_completion_tokens}\n"
                        f"Total tokens:      "
                        f"{total_prompt_tokens + total_completion_tokens}"
                    )
                    break

                # Append assistant message with tool calls
                messages.append(choice.message)

                # Execute each tool call against the MCP server
                for tool_call in choice.message.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)
                    print(f"  -> Calling tool: {fn_name}({fn_args})")

                    result = await session.call_tool(fn_name, arguments=fn_args)

                    result_text = "\n".join(
                        c.text for c in result.content if hasattr(c, "text") and c.text
                    )
                    print(f"  <- Result: {result_text[:200]}")

                    # Feed tool result back
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result_text,
                        }
                    )


if __name__ == "__main__":
    asyncio.run(main())
