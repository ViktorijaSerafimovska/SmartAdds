from fastapi import APIRouter

from app.mcp.mcp_models import MCPJsonRpcRequest, MCPJsonRpcResponse
from app.search.search_service import search_ads

router = APIRouter(prefix="/mcp", tags=["MCP"])


def ok(request_id: str, result):
    return MCPJsonRpcResponse(
        id=request_id,
        result=result
    )


def error(request_id: str, code: int, message: str):
    return MCPJsonRpcResponse(
        id=request_id,
        error={
            "code": code,
            "message": message
        }
    )


@router.post("")
def handle_mcp(request: MCPJsonRpcRequest):

    print("\n[MCP SERVER] Request received")
    print(f"[MCP SERVER] jsonrpc={request.jsonrpc}")
    print(f"[MCP SERVER] id={request.id}")
    print(f"[MCP SERVER] method={request.method}")
    print(f"[MCP SERVER] params={request.params}")

    if request.method == "initialize":
        print("[MCP SERVER] initialize called")

        return ok(request.id, {
            "server": "SmartAdds MCP Server",
            "version": "1.0",
            "capabilities": {
                "tools": True
            }
        })

    if request.method == "tools/list":
        print("[MCP SERVER] tools/list called")

        return ok(request.id, {
            "tools": [
                {
                    "name": "search_ads",
                    "description": "Search ads from Reklama5 and Pazar3 stored in the database.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "limit": {"type": "integer"}
                        },
                        "required": ["query"]
                    }
                }
            ]
        })

    if request.method == "tools/call":
        params = request.params or {}
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        print(f"[MCP SERVER] tools/call tool={tool_name}")
        print(f"[MCP SERVER] arguments={arguments}")

        if tool_name != "search_ads":
            print(f"[MCP SERVER ERROR] Unsupported tool: {tool_name}")
            return error(request.id, -32602, f"Unsupported tool: {tool_name}")

#ako sakame da imame poveke ads limit go zgolemuvame
        query = arguments.get("query", "")
        limit = int(arguments.get("limit", 20))

        print(f"[MCP SERVER] Calling search_service.search_ads query='{query}' limit={limit}")

        results = search_ads(
            query=query,
            limit=limit
        )

        print(f"[MCP SERVER] DB/search returned {len(results)} ads")

        return ok(request.id, {
            "content": [
                {
                    "type": "json",
                    "json": results
                }
            ],
            "isError": False
        })

    print(f"[MCP SERVER ERROR] Unknown method: {request.method}")
    return error(request.id, -32601, f"Unknown method: {request.method}")
