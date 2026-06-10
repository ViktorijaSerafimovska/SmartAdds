import uuid
import requests


MCP_ENDPOINT = "http://127.0.0.1:8000/mcp"


def call_mcp(method: str, params: dict | None = None):
    request_id = str(uuid.uuid4())

    body = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {}
    }

    print("\n[MCP CLIENT] Sending request to MCP server")
    print(f"[MCP CLIENT] endpoint={MCP_ENDPOINT}")
    print(f"[MCP CLIENT] method={method}")
    print(f"[MCP CLIENT] params={params}")

    response = requests.post(
        MCP_ENDPOINT,
        json=body,
        timeout=120
    )

    print(f"[MCP CLIENT] HTTP status={response.status_code}")

    response.raise_for_status()

    data = response.json()

    print(f"[MCP CLIENT] response_id={data.get('id')}")
    print(f"[MCP CLIENT] has_error={data.get('error') is not None}")

    if data.get("error"):
        raise Exception(data["error"].get("message", "MCP error"))

    return data.get("result")


def initialize():
    return call_mcp("initialize")


def list_tools():
    return call_mcp("tools/list")


def search_ads(query: str, limit: int = 20):
    result = call_mcp(
        "tools/call",
        {
            "name": "search_ads",
            "arguments": {
                "query": query,
                "limit": limit
            }
        }
    )

    ads = (
        result
        .get("content", [{}])[0]
        .get("json", [])
    )

    print(f"[MCP CLIENT] Extracted ads={len(ads)}")

    return ads