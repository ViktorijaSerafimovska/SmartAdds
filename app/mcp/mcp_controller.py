from fastapi import APIRouter

from app.mcp.mcp_models import (
    MCPRequest,
    MCPResponse,
    MCPTool
)

from app.search.search_service import search_ads


router = APIRouter(prefix="/mcp", tags=["MCP"])


@router.get("/initialize")
def initialize():

    return {
        "server": "SmartAdds MCP Server",
        "version": "1.0"
    }


@router.get("/tools/list")
def list_tools():

    tools = [
        MCPTool(
            name="search_ads",
            description="Search ads from database"
        )
    ]

    return {
        "tools": tools
    }


@router.post("/tools/call")
def call_tool(request: MCPRequest):

    try:

        if request.tool == "search_ads":

            query = request.arguments.get("query", "")
            limit = request.arguments.get("limit", 20)

            results = search_ads(
                query=query,
                limit=limit
            )

            return MCPResponse(
                success=True,
                result=results
            )

        return MCPResponse(
            success=False,
            error=f"Unknown tool: {request.tool}"
        )

    except Exception as e:

        return MCPResponse(
            success=False,
            error=str(e)
        )