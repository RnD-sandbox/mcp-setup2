import httpx
from typing import Any
import os

api_key = os.getenv("IBMCLOUD_API_KEY")


async def get_api_access_token() -> dict[str, Any] | None:
    """Make a request to get an IBM Cloud Account access token(bearer token)"""

    url = "https://iam.cloud.ibm.com/identity/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
        "apikey": api_key,
    }
    auth = ("bx", "bx")  # equivalent to -u "bx:bx"

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, data=data, auth=auth)

        if response.status_code == 200:
            json_data = response.json()
            # access_token = json_data.get("access_token")
            # refresh_token = json_data.get("refresh_token")
            # print(json_data)
            return json_data
        else:
            raise Exception(f"Request failed: {response.status_code} - {response.text}")
