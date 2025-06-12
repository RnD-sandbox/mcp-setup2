import httpx
from typing import Any


def get_schematics_workspaces(tokens: dict) -> dict[str, Any] | None:
    """Get all the schematics workspace created in the IBM Cloud account"""

    access_token = tokens["access_token"]
    url = f"https://schematics.cloud.ibm.com/v1/workspaces"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = httpx.get(url, headers=headers)
    if response.status_code == 200:
        # print(response.json())
        workspaces = []
        for workspace in response.json()["workspaces"]:
            workspace_obj = {
                "id": workspace.get("id"),
                "name": workspace.get("name"),
                "resource_group": workspace.get("resource_group"),
                "location": workspace.get("location"),
                "status": workspace.get("status"),
                "created_at": workspace.get("created_at"),
                "created_by": workspace.get("created_by"),
            }
            workspaces.append(workspace_obj)
        return workspaces
    else:
        raise Exception(f"Failed to fetch workspace: {response.status_code} - {response.text}")


def sch_format_result(workspaces: dict) -> str:
    """Format the schematics workspaces response into a readable string"""

    output = []
    for i, workspace in enumerate(workspaces, start=1):
        output.append(f"Workspace {i}:")
        output.append(f"- Name: {workspace.get('name')}")
        output.append(f"- ID: {workspace.get('id')}")
        output.append(f"- Resource Group: {workspace.get('resource_group')}")
        output.append(f"- Location: {workspace.get('location')}")
        output.append(f"- Status: {workspace.get('status')}")
        output.append(f"- Created At: {workspace.get('created_at')}")
        output.append(f"- Created By: {workspace.get('created_by')}")
        output.append("")  # blank line between workspaces
    return "\n".join(output)
