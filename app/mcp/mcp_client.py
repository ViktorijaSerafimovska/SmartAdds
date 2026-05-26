import requests


MCP_BASE_URL = "http://127.0.0.1:8000/mcp"


def initialize():

    response = requests.get(
        f"{MCP_BASE_URL}/initialize"
    )

    response.raise_for_status()

    return response.json()


def list_tools():

    response = requests.get(
        f"{MCP_BASE_URL}/tools/list"
    )

    response.raise_for_status()

    return response.json()


def search_ads(query: str, limit: int = 20):

    payload = {
        "tool": "search_ads",
        "arguments": {
            "query": query,
            "limit": limit
        }
    }

    response = requests.post(
        f"{MCP_BASE_URL}/tools/call",
        json=payload
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("success"):
        raise Exception(data.get("error"))

    return data.get("result", [])