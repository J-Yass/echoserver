import json
import sys
import asyncio
from typing import Any, Dict
import httpx

# Constants
CHESSCOM_API_BASE = "https://api.chess.com"
USER_AGENT = "chesscom-app/1.0"

class EchoserverMCP:
    def __init__(self):
        #List of the tools offered in this server
        self.tools = {
            "echoserver":{
                "name":"echoserver",
                "description":"Reply to a message with its echo (the message itself)",
                "inputSchema":{
                    "type":"object",
                    "properties":{
                        "msg":{
                            "type":"string",
                            "description":"Message to reply"
                        }
                    },
                    "required": ["msg"]
                }
            },
            "chesscomProfileFollowers":{
                "name":"chesscomProfileFollowers",
                "description":"Get a chess.com player followers",
                "inputSchema":{
                    "type":"object",
                    "properties":{
                        "username":{
                            "type":"string",
                            "description":"Chess.com username"
                        }
                    },
                    "required":["username"]
                }
            }
        }

    #https://modelcontextprotocol.io/specification/2025-06-18/basic
    #Section 1.2 Responses

    def create_response(self, request_id: int, result: Any) -> Dict[str, Any]:
        return{
            "jsonrpc": "2.0",
            "id": request_id,
            "result":result
        }
    
    #https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle
    #Section 3. Error Handling

    def create_error_response(self, request_id: int, code: int, message: str) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error":{
                "code":code,
                "message":message
            }
        }
    
    async def make_chess_request(self, url: str) -> dict[str, Any] | None:
        """Make a request to the Chess.com API with proper error handling."""
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json"
        }

        async with httpx.AsyncClient() as client:
            try:
                response= await client.get(url, headers=headers, timeout=30.0)
                response.raise_for_status()
                return response.json()
            except Exception:
                return None
    
    async def handle_jsonrpc(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle JSON RPC 2.0 Request"""
        try:
            method=request.get("method")
            params=request.get("params", {})
            request_id = request.get("id")
            
            #https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle
            #Section 1.1.
            #In the protocol lifecycle, the initialization is the first interaction between the client and server
            #In this case, we offer only tools
            if method=="initialize":
                return self.create_response(request_id, {
                    "protocolVersion":"2024-11-05",
                    "capabilities":{
                        "tools":{}
                    },
                    "serverInfo":{
                        "name":"echoserver",
                        "version":"1.0.0"
                    }
                })
            
            elif method=="tools/list":
                return self.create_response(request_id,{
                    "tools":list(self.tools.values())
                })
            
            elif method=="tools/call":
                tool_name = params.get("name")
                if tool_name == "echoserver":
                    arguments = params.get("arguments")
                    client_msg = arguments.get("msg")
                    result={
                        "type":"text",
                        "text":client_msg
                    }
                    return self.create_response(request_id, {
                        "content":[result]
                    })
                elif tool_name == "chesscomProfileFollowers":
                    arguments = params.get("arguments")
                    player = arguments.get("username")

                    headers = {
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json"
                    }

                    url = f"{CHESSCOM_API_BASE}/pub/player/{player}"
                    data = await self.make_chess_request(url)

                    if not data:
                        return self.create_error_response(request_id, -1, "Chess.com user profile not found")
                    
                    #user_profile = json.dumps(data, indent=2)
                    
                    result={
                        "type":"text",
                        "text":str(data["followers"])
                    }
                    return self.create_response(request_id, {
                        "content":[result]
                    })
                else:
                    return self.create_error_response(request_id, -32601, "tool not found")
            else:
                return self.create_error_response(request_id, -32601,"method not found")
        except Exception as e:
            return self.create_error_response(request.get("id"), -32603, str(e))
        
async def main():
    server = EchoserverMCP()

    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break

            request = json.loads(line.strip())
            response = await server.handle_jsonrpc(request)

            print(json.dumps(response), flush=True)
        except Exception as e:
            error_response = {
                "jsonrpc":"2.0",
                "id":None,
                "error":{"code":-32700, "message":"Parse error"}
            }
            print(json.dumps(error_response), flush=True)

if __name__ == "__main__":
    asyncio.run(main())

#Terminal testing
#Initialization
#echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}' | python echoserver.py

#Tools request
#echo '{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}' | python echoserver.py  

#Echoserver tool execution - Actual call from Claude Desktop
#echo '{"method":"tools/call","params":{"name":"echoserver","arguments":{"msg":"Hi"}},"jsonrpc":"2.0","id":23}' | python echoserver.py

#Chess.com tool execution - Actual call from Claude Desktop
#echo '{"method":"tools/call","params":{"name":"chesscomProfileFollowers","arguments":{"username":"jyassgt"}},"jsonrpc":"2.0","id":23}' | python echoserver.py