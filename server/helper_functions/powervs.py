import httpx
from typing import Any

# from iam import get_api_access_token
# import asyncio

# all_dcs = ["syd", "sao", "mon", "tor", "eu-de", "lon", "che", "tok", "osa", "mad", "us-east", "us-south"]
all_dcs = ["syd"]


def get_power_workspaces(tokens: dict) -> dict[str, Any] | None:
    """Get all the schematics workspace created in the IBM Cloud account"""
    workspaces = []
    access_token = tokens["access_token"]
    for dc in all_dcs:
        url = f"https://{dc}.power-iaas.cloud.ibm.com/v1/workspaces"
        headers = {"Authorization": f"Bearer {access_token}"}
        response = httpx.get(url, headers=headers)
        if response.status_code == 200:
            for workspace in response.json()["workspaces"]:
                workspace_obj = {
                    "id": workspace.get("id"),
                    "name": workspace.get("name"),
                    "status": workspace.get("status"),
                    "location": workspace.get("location").get("region"),
                }
                workspaces.append(workspace_obj)
        else:
            raise Exception(f"Failed to fetch workspace: {response.status_code} - {response.text}")
    return workspaces


def pvs_format_result(workspaces: dict) -> str:
    """Format the schematics workspaces response into a readable string"""

    output = []
    for i, workspace in enumerate(workspaces, start=1):
        output.append(f"Workspace {i}:")
        output.append(f"- Name: {workspace.get('name')}")
        output.append(f"- ID: {workspace.get('id')}")
        output.append(f"- Location: {workspace.get('location')}")
        output.append(f"- Status: {workspace.get('status')}")
        output.append("")  # blank line between workspaces
    return "\n".join(output)


# if __name__ == "__main__":
#     asyncio.run(fetch_powervs_workspaces())
