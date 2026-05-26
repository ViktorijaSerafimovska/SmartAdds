from typing import Dict, Any, Optional

from pydantic import BaseModel


class MCPRequest(BaseModel):

    tool: str
    arguments: Dict[str, Any] = {}


class MCPResponse(BaseModel):

    success: bool = True
    result: Optional[Any] = None
    error: Optional[str] = None


class MCPTool(BaseModel):

    name: str
    description: str