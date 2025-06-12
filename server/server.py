from dotenv import load_dotenv

# import os, httpx
# from typing import Any
from mcp.server.fastmcp import FastMCP

# import asyncio
import argparse

# from fastapi.routing import APIRoute
# import asyncio
# import uvicorn
from mcp import ClientSession
from mcp.client.sse import sse_client

# import asyncio

from helper_functions.schematics import *
from helper_functions.iam import *
from helper_functions.powervs import *


load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("server")

# Environment Variables


# Define services
@mcp.tool()
async def fetch_schematics_workspaces() -> str:
    """Get a list of schematics workspaces in my IBM cloud account."""
    tokens = await get_api_access_token()

    if not tokens:
        return "Unable to fetch the access token."
    else:
        workspaces = get_schematics_workspaces(tokens)
        if not workspaces:
            return "Unable to fetch the workspaces"
        else:
            # print(workspaces)
            context_str = sch_format_result(workspaces)
            print(context_str)
            return context_str


@mcp.tool()
async def fetch_powervs_workspaces() -> str:
    """Get a list of PowerVS or Power Virtual Server workspaces in my IBM cloud account."""
    tokens = await get_api_access_token()

    if not tokens:
        return "Unable to fetch the access token."
    else:
        workspaces = get_power_workspaces(tokens)
        if not workspaces:
            return "Unable to fetch the workspaces"
        else:
            # print(workspaces)
            context_str = pvs_format_result(workspaces)
            print(context_str)
            return context_str


@mcp.resource("echo://{name}")
def welcome_msg(name: str) -> str:
    """This is a greeting message."""
    return f"Hello {name}, welcome to Mars!"


async def call_mcp_tool():
    url = "http://127.0.0.1:8000/sse"
    async with sse_client(url) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            response = await session.call_tool(name="fetch_schematics_workspaces")
            print("Tool response:", response.content)


if __name__ == "__main__":
    print("🚀 Starting server... ")

    app = mcp.sse_app()
    print("Registered routes:")
    for route in app.routes:
        print(f"  {route.path}")

    # mcp.run("sse")

    # Debug Mode
    # uv run mcp dev server.py

    # Production Mode
    # uv run server.py --server_type=sse

    parser = argparse.ArgumentParser()
    parser.add_argument("--server_type", type=str, default="sse", choices=["sse", "stdio"])

    args = parser.parse_args()

    app = mcp.sse_app()

    print(app.routes)

    mcp.run(args.server_type)
