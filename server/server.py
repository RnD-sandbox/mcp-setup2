from dotenv import load_dotenv
import os, httpx
from typing import Any
from mcp.server.fastmcp import FastMCP
import asyncio
import argparse
from fastapi.routing import APIRoute
import asyncio
import uvicorn
from mcp import ClientSession
from mcp.client.sse import sse_client
import asyncio

from helper_functions.schematics import *
from helper_functions.iam import *


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
            context_str = format_result(workspaces)
            print(context_str)
            return context_str


# @mcp.tool()
# async def get_grouped_schematics_workspaces(created_by: str = None, location: str = None) -> str:
#     """Get a list of schematics workspaces in my IBM cloud account, optionally filtered by creator or location."""
#     tokens = await get_api_access_token()
#     if not tokens:
#         return "Unable to fetch the access token."

#     workspaces = get_schematics_workspaces(tokens)
#     if not workspaces:
#         return "No workspaces found."

#     # Filter
#     if created_by:
#         workspaces = [w for w in workspaces if w.get("created_by", "").lower() == created_by.lower()]
#     if location:
#         workspaces = [w for w in workspaces if location.lower() in w.get("location", "").lower()]

#     return format_result(workspaces)


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


# if __name__ == "__main__":
#     # Start your MCP server in background
#     import threading

#     def start_server():
#         app = mcp.sse_app()
#         uvicorn.run(app, host="127.0.0.1", port=8000)

#     server_thread = threading.Thread(target=start_server, daemon=True)
#     server_thread.start()

#     # Give server a second to start up (or better: wait until ready)
#     import time

#     time.sleep(2)

#     # Now call your tool via asyncio event loop
#     async def main():
#         output = await call_mcp_tool()
#         print("Tool output:\n", output)

#     asyncio.run(main())


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
