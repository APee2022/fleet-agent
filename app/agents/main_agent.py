from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.tools import Tool
from ..llm_model.llm_model import llm
from ..tools.fleet_tools import plan_route_to_csv
import json

# System prompt: tell the model to prefer the CSV tool when the user asks for data.
SYSTEM = (
"You are a helpful, concise assistant for a fleet simulator. "
"When the user asks to generate or update telemetry/CSV, "
"call the tool `plan_route_to_csv` with sensible defaults (6-hour duty) "
"unless the user provides specific values. "
"Return a short summary and the CSV path."
)

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM),
    ("placeholder", "{chat_history}"),
    ("user", "{input}"),
    ("placeholder", "{agent_scratchpad}")
])

tools = [plan_route_to_csv]
agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

# Simple in-memory chat store
_store = {}

def _get_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in _store:
        _store[session_id] = ChatMessageHistory()
    return _store[session_id]

def run_general_chat_agent(user_input: str, session_id: str = "default"):
    with_history = RunnableWithMessageHistory(
        agent_executor,
        lambda: _get_history(session_id),
        input_messages_key="input",
        history_messages_key="chat_history",
    )
    result = with_history.invoke({"input": user_input}, config={"configurable": {"session_id": session_id}})
    print(f"Agent result: {result}")
    # If the tool returned JSON, surface it nicely
    out = result.get("output") if isinstance(result, dict) else result
    # print(f"Agent output: {out}")
    try:
        parsed = json.loads(out) if isinstance(out, str) and out.strip().startswith("{") else None
        # print(f"Parsed tool result: {parsed}")
        return {"response": out, "tool_result": parsed}
    except Exception:
        return {"response": out, "tool_result": None}
