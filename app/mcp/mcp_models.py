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