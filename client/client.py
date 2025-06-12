import asyncio
import json
import warnings
from dotenv import load_dotenv
from typing import Annotated, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
import httpx
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

# Load environment variables
load_dotenv()

# Suppress specific warning about json_schema fallback
warnings.filterwarnings(
    "ignore",
    message=".*Cannot use method='json_schema' with model gpt-3.5-turbo.*",
    category=UserWarning,
)

# Initialize LLM
llm = ChatOpenAI(model="gpt-3.5-turbo")


# Define structured output schema
class MessageClassifier(BaseModel):
    message_type: Literal["powervs", "schematics"] = Field(
        ..., description="Classify if the message is about schematics or powervs workspaces."
    )


# Define state
class State(TypedDict):
    messages: Annotated[list, add_messages]
    message_type: str | None
    powervs_context: str | None


# Classifier node
async def classify_message(state: State):
    last_message = state["messages"][-1]
    classifier_llm = llm.with_structured_output(MessageClassifier, method="function_calling")

    result = await classifier_llm.ainvoke(
        [
            {
                "role": "system",
                "content": """Classify the user message as either:
                - 'powervs': if it mentions power, power virtual server, powervs, POWER, or pvs
                - 'schematics': if it mentions deployment, schematics, sch, DA, DAs, das, or da""",
            },
            {"role": "user", "content": last_message.content},
        ]
    )
    print(result.message_type)
    return {"message_type": result.message_type}


# Router node
def router(state: State):
    return {"next": state.get("message_type", "powervs")}


# PowerVS agent node
async def powervs_agent(state: State):
    last_message = state["messages"][-1]
    powervs_context = state.get("powervs_context") or "No PowerVS context available."

    messages = [
        {
            "role": "system",
            "content": f"""
            You are an AI assistant answering questions about PowerVS Workspaces in IBM Cloud.
            Use the following context:
            {powervs_context}
            """,
        },
        {"role": "user", "content": last_message.content},
    ]

    reply = await llm.ainvoke(messages)
    return {"messages": [{"role": "assistant", "content": reply.content}]}


# Schematics agent node
async def schematics_agent(state: State):
    last_message = state["messages"][-1]
    print("Schematics Agent called.")

    try:
        context = await call_mcp_tool(tool_name="fetch_schematics_workspaces")
    except Exception as e:
        context = f"Error fetching schematics workspaces: {str(e)}"

    messages = [
        {
            "role": "system",
            "content": f"""
            You are an AI assistant answering questions about Schematics Workspaces in IBM Cloud.
            Use the following context:
            {context}
            """,
        },
        {"role": "user", "content": last_message.content},
    ]

    reply = await llm.ainvoke(messages)
    return {"messages": [{"role": "assistant", "content": reply.content}]}


async def call_mcp_tool(tool_name: str):
    url = "http://127.0.0.1:8000/sse"
    async with sse_client(url) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            response = await session.call_tool(name=tool_name)
            # print("Tool response:", response.content)
            return response.content


# Build the graph
graph_builder = StateGraph(State)
graph_builder.add_node("classifier", classify_message)
graph_builder.add_node("router", router)
graph_builder.add_node("powervs", powervs_agent)
graph_builder.add_node("schematics", schematics_agent)

graph_builder.add_edge(START, "classifier")
graph_builder.add_edge("classifier", "router")
graph_builder.add_conditional_edges("router", lambda state: state.get("next"), {"powervs": "powervs", "schematics": "schematics"})
graph_builder.add_edge("powervs", END)
graph_builder.add_edge("schematics", END)

graph = graph_builder.compile()


# Chat loop using SSE
async def run_chatbot():
    state = {"messages": [], "message_type": None}

    while True:
        user_input = input("^_^ You      : ")
        if user_input == "exit":
            print("Bye")
            break

        state["messages"] = state.get("messages", []) + [{"role": "user", "content": user_input}]

        state = await graph.ainvoke(state)

        if state.get("messages") and len(state["messages"]) > 0:
            last_message = state["messages"][-1]
            print(f"o_o Assistant: {last_message.content}")


if __name__ == "__main__":
    asyncio.run(run_chatbot())
