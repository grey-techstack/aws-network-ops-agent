# network_agent.py
# -*- coding: utf-8 -*-
"""
Network assistant for Cisco IOS using Netmiko + LangChain ReAct agent (sanitized version)

Security note:
- No real credentials are embedded. Configure via environment variables or a .env loader.

Runtime deps (install with pip):
    pip install netmiko langchain langchain-openai

Optional (for local .env loading):
    pip install python-dotenv

Environment variables expected:
    DEVICE_USERNAME        # e.g., admtech
    DEVICE_PASSWORD        # device SSH password
    OPENROUTER_API_KEY     # your OpenRouter API key

Usage:
    python network_agent.py
"""

import os
import re
import time
from typing import Tuple

try:
    from netmiko import ConnectHandler
except Exception as e:  # pragma: no cover
    raise RuntimeError("Netmiko is required. Install via 'pip install netmiko'.") from e

try:
    from langchain_openai import ChatOpenAI
    from langchain.tools import tool
    from langchain.agents import AgentExecutor, create_react_agent
    from langchain.prompts import PromptTemplate
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "LangChain and langchain-openai are required. Install via 'pip install langchain langchain-openai'."
    ) from e

# --- Load secrets from environment (sanitized: no hard-coded secrets) ---
USERNAME = os.getenv("DEVICE_USERNAME")
PASSWORD = os.getenv("DEVICE_PASSWORD")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not USERNAME or not PASSWORD:
    raise EnvironmentError(
        "DEVICE_USERNAME and DEVICE_PASSWORD must be set in environment variables."
    )

if not OPENROUTER_API_KEY:
    raise EnvironmentError(
        "OPENROUTER_API_KEY must be set in environment variables (do not hard-code secrets)."
    )

# --- Configure LLM via OpenRouter + LangChain ---
# Model naming on OpenRouter usually follows the provider/model format, e.g., "openai/gpt-4o-mini".
# Adjust to any compatible chat model available to your account.
llm = ChatOpenAI(
    model="openai/gpt-4o-mini",
    openai_api_key=OPENROUTER_API_KEY,
    openai_api_base="https://openrouter.ai/api/v1",
    temperature=0.2,
)


def get_device_connection(ip: str) -> dict:
    return {
        "device_type": "cisco_ios",
        "ip": ip,
        "username": USERNAME,
        "password": PASSWORD,
        # Optional: tweak for speed/stability
        # "fast_cli": True,
        # "global_delay_factor": 1,
    }


# ----------------------------
# Tools (LangChain @tool)
# ----------------------------

@tool
def check_cpu_status(ip_address: str) -> str:
    """检查目标设备的 CPU 使用情况。参数：设备 IP 地址。"""
    device_params = get_device_connection(ip_address)
    for attempt in range(3):
        try:
            time.sleep(1)
            with ConnectHandler(**device_params) as connection:
                output = connection.send_command("show process cpu history")
                return f"CPU status for device {ip_address}:\n{output}"
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue
            return f"Error connecting to {ip_address}: {str(e)}"


def _parse_ip_and_interface(ip_and_interface: str) -> Tuple[str, str]:
    """Parse 'IP Interface' from user text like '172.16.1.1 gi1/0/1'. Strip comments (#...)."""
    # remove inline comments and trim
    cleaned = ip_and_interface.split('#')[0].strip()
    parts = cleaned.split(maxsplit=1)
    if len(parts) < 2:
        raise ValueError("需要同时提供 IP 地址和接口名称，以空格分隔。例如: '172.16.1.1 gi1/0/1'")
    ip = parts[0].strip("'\" ")
    iface = parts[1].strip("'\" ").replace(" ", "")
    return ip, iface


@tool
def check_link_utilization(ip_and_interface: str) -> str:
    """检查目标设备指定接口的带宽使用情况。参数格式: 'IP地址 接口名称', 例如: '172.16.1.1 gi1/0/1'"""
    try:
        ip_address, interface = _parse_ip_and_interface(ip_and_interface)
    except Exception as e:
        return f"错误: {str(e)}"

    device_params = get_device_connection(ip_address)
    try:
        with ConnectHandler(**device_params) as connection:
            output = connection.send_command(f"show interface {interface}")

            # Common patterns seen on IOS: 'txload 1/255, rxload 1/255' or 'TX load 1/255, RX load 1/255'
            tx_patterns = [r"txload (\d+)/(\d+)", r"TX load (\d+)/(\d+)"]
            rx_patterns = [r"rxload (\d+)/(\d+)", r"RX load (\d+)/(\d+)"]

            txload_match = None
            rxload_match = None
            for p in tx_patterns:
                txload_match = re.search(p, output, flags=re.IGNORECASE)
                if txload_match:
                    break
            for p in rx_patterns:
                rxload_match = re.search(p, output, flags=re.IGNORECASE)
                if rxload_match:
                    break

            if txload_match and rxload_match:
                tx_value = int(txload_match.group(1))
                tx_max = int(txload_match.group(2))
                rx_value = int(rxload_match.group(1))
                rx_max = int(rxload_match.group(2))

                # Convert Cisco load (x/255) to percentage
                tx_percentage = (tx_value / tx_max) * 100 if tx_max else 0.0
                rx_percentage = (rx_value / rx_max) * 100 if rx_max else 0.0

                tx_result = f"{tx_percentage:.1f}%" if tx_percentage >= 1 else "小于 1%"
                rx_result = f"{rx_percentage:.1f}%" if rx_percentage >= 1 else "小于 1%"

                return (
                    f"设备 {ip_address} 的端口 {interface} 带宽使用情况：\n"
                    f"上行带宽为 {tx_result}\n"
                    f"下行带宽为 {rx_result}\n\n"
                    f"原始输出:\n{output}"
                )
            else:
                return f"无法从输出中提取带宽信息\n\n原始输出:\n{output}"
    except Exception as e:
        return f"Error connecting to {ip_address} or checking interface {interface}: {str(e)}"


@tool
def analysis_syslog(ip_address: str) -> str:
    """分析目标设备的日志（show log），并用 LLM 生成摘要。参数：设备 IP 地址。"""
    device_params = get_device_connection(ip_address)
    for attempt in range(3):
        try:
            time.sleep(1)
            with ConnectHandler(**device_params) as connection:
                log_output = connection.send_command("show log")

            analysis_prompt = (
                "Please analyze the following network device logs and provide a concise summary "
                "of notable events, errors, warnings, or potential issues. Focus on actionable information.\n\n"
                f"Logs:\n{log_output[:12000]}"  # avoid over-long prompts
            )
            analysis = llm.invoke(analysis_prompt)
            analysis_text = getattr(analysis, "content", str(analysis))
            return f"设备 {ip_address} 的日志分析结果：\n{analysis_text}"
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue
            return f"Error connecting to {ip_address}: {str(e)}"


# ----------------------------
# Prompt & Agent setup
# ----------------------------

prompt_template = """
You are a network assistant specializing in Cisco device monitoring and troubleshooting.
Analyze user requests and use the appropriate tools to gather information from network devices.

When helping users, remember:
1. For CPU utilization queries, use the check_cpu_status tool
2. For link utilization queries, use the check_link_utilization tool with BOTH the IP address AND interface name
3. For log analysis requests, use the analysis_syslog tool
4. For general network performance issues (e.g., "why is the network slow?"), use all three tools and analyze the results

IMPORTANT:
- When users ask about link utilization, they will specify both an IP address and an interface. Extract BOTH and use them with the tool.

DEFAULT SETTINGS:
- If user asks a general question about network slowness (like "why is the network slow?") without specifying devices:
  - Use IP address 10.0.0.10 as the default device
  - Use interface GigabitEthernet0/16 as the default interface
  - Check CPU, link utilization, and logs on this default device

Available tools:
{tools}

Use the following format:
User question: The input question you must answer
Thought: Consider what tools would help answer this question and extract any IP addresses and interfaces
Action: The action to take, should be one of [{tool_names}]
Action Input: The parameters to pass to the tool (make sure to include BOTH IP and interface for check_link_utilization)
Observation: The result of the action
Thought: I now have enough information to answer the user's question
... (this Thought/Action/Action Input/Observation can repeat multiple times)
Thought: I have collected all necessary data from the tools
Analysis: Analyze the tool outputs to determine possible reasons for the user's question (e.g., network slowness)
Final Answer: The final answer to the user's question, summarizing the tool output in a concise way

**IMPORTANT**:
- For general performance questions like "why is the network slow?", after collecting data from all three tools (CPU, link utilization, logs), analyze the outputs to identify potential causes of slowness (e.g., high CPU usage, link congestion, errors in logs).
- Once you have enough data to answer the question, provide the Analysis and Final Answer, then STOP. Do not repeat tool calls unnecessarily.

User question: {input}
{agent_scratchpad}
"""

prompt = PromptTemplate.from_template(prompt_template)

tools = [check_cpu_status, check_link_utilization, analysis_syslog]
agent = create_react_agent(llm, tools, prompt)

# Create an executor for the agent
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    max_iterations=3,
    verbose=True,
    handle_parsing_errors=True,
)


def process_input(user_input: str) -> str:
    """处理用户输入，通过 agent_executor 调用 agent 来决定使用哪些工具。"""
    try:
        result = agent_executor.invoke({"input": user_input})
        if isinstance(result, dict) and "output" in result:
            return result["output"]
        return str(result)
    except Exception as e:  # pragma: no cover
        return (
            f"无法处理请求: {str(e)}\n"
            "请尝试明确指定您想查询的内容（例如 CPU 使用率、链路利用率或日志分析），"
            "并确保包含必要的 IP 地址和接口信息（如果适用）。"
        )


if __name__ == "__main__":
    print("Cisco Network Assistant (ReAct Agent) — type 'exit' or 'quit' to leave.")
    while True:
        try:
            user_input = input("\nEnter your question: ").strip()
            if user_input.lower() in ["exit", "quit"]:
                print("\nBye!")
                break
            if not user_input:
                print("Please enter a valid prompt!")
                continue
            result = process_input(user_input)
            print("\n" + str(result))
        except KeyboardInterrupt:
            print("\n程序被用户中断")
            break
        except Exception as e:  # pragma: no cover
            print(f"\n发生错误: {str(e)}")
