import json
from typing import Annotated
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict
from tools import lookup_customer, get_order_details, check_refund_policy, process_refund, get_policy_summary

# tool definitions (@tool wrappers)

@tool
def tool_lookup_customer(identifier: str) -> str:
    """Look up a customer by their email address, customer ID (e.g. C001), or order ID (e.g. ORD-1001)."""
    result = lookup_customer(identifier)
    return json.dumps(result)

@tool
def tool_get_order_details(order_id: str, customer_id: str) -> str:
    """Get the full details of a specific order for a customer."""
    result = get_order_details(order_id, customer_id)
    return json.dumps(result)

@tool
def tool_check_refund_policy(customer_id: str, order_id: str) -> str:
    """Run all refund policy rules against a customer's order and return an eligibility report."""
    result = check_refund_policy(customer_id, order_id)
    return json.dumps(result)

@tool
def tool_process_refund(customer_id: str, order_id: str, reason: str) -> str:
    """Finalize a refund decision. Call this only after checking policy eligibility."""
    result = process_refund(customer_id, order_id, reason)
    return json.dumps(result)

@tool
def tool_get_policy_summary() -> str:
    """Retrieve the full refund policy summary to answer policy questions."""
    result = get_policy_summary()
    return json.dumps(result)

TOOLS = [
    tool_lookup_customer,
    tool_get_order_details,
    tool_check_refund_policy,
    tool_process_refund,
    tool_get_policy_summary,
]

TOOL_MAP = {t.name: t for t in TOOLS}

SYSTEM_PROMPT = """You are a professional AI customer support agent for ShopEasy, an e-commerce platform.
Your job is to handle refund requests by strictly following company policy.

ALWAYS follow this workflow for refund requests:
1. Use tool_lookup_customer to find the customer
2. Use tool_check_refund_policy to validate eligibility against ALL policy rules
3. Use tool_process_refund to finalize the decision
4. Report the outcome clearly to the customer

Rules you MUST follow:
- Never approve a refund without running tool_check_refund_policy first
- If any policy rule fails, deny the refund and explain why (politely but firmly)
- Do not make exceptions to policy rules — hold the line
- Be empathetic but firm when denying requests
- For non-refund questions, answer helpfully using available tools

Always be professional, concise, and clear."""


# langgraph state

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    logs: list[dict]


# agent graph

def build_agent(api_key: str):
    llm = ChatGroq(
        api_key=api_key,
        model="llama-3.3-70b-versatile",
        temperature=0,
    ).bind_tools(TOOLS)

    def agent_node(state: AgentState):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = llm.invoke(messages)
        logs = state.get("logs", [])
        if response.tool_calls:
            for tc in response.tool_calls:
                logs.append({
                    "type": "tool_call",
                    "tool": tc["name"],
                    "args": tc["args"]
                })
        else:
            logs.append({"type": "response", "content": response.content[:120]})
        return {"messages": [response], "logs": logs}

    def tool_node(state: AgentState):
        last = state["messages"][-1]
        tool_messages = []
        logs = state.get("logs", [])
        for tc in last.tool_calls:
            t = TOOL_MAP.get(tc["name"])
            if t:
                result = t.invoke(tc["args"])
            else:
                result = json.dumps({"error": f"Unknown tool: {tc['name']}"})
            logs.append({"type": "tool_result", "tool": tc["name"], "result": result[:300]})
            tool_messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
        return {"messages": tool_messages, "logs": logs}

    def should_continue(state: AgentState):
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()
