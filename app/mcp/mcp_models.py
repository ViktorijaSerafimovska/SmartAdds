# from typing import Dict, Any, Optional
#
# from pydantic import BaseModel
#
#
# class MCPRequest(BaseModel):
#
#     tool: str
#     arguments: Dict[str, Any] = {}
#
#
# class MCPResponse(BaseModel):
#
#     success: bool = True
#     result: Optional[Any] = None
#     error: Optional[str] = None
#
#
# class MCPTool(BaseModel):
#
#     name: str
#     description: str

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class MCPJsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str = "1"
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)


class MCPJsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: str
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None