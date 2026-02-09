# Proxy Flow - External MCP Servers

OneTool can proxy calls to external MCP servers defined in `servers.yaml`,
exposing them as regular pack namespaces (e.g., `github.get_file_contents()`).

## Connection Types

| Transport | Config | Example |
|-----------|--------|---------|
| **stdio** | `command` + `args` | `npx @anthropic-ai/github-mcp-server` |
| **HTTP** | `url` | `http://localhost:8080` |

## Sequence Diagram

```mermaid
sequenceDiagram
    participant C as Client Code
    participant P as PackProxy (McpProxyPack)
    participant M as ProxyManager
    participant T as Transport (stdio/HTTP)
    participant E as External MCP Server

    Note over M,E: Startup (server.py init)
    M->>M: Load servers.yaml config
    M->>T: Create transport (stdio or HTTP)
    T->>E: Connect
    E-->>T: Connection established
    T-->>M: Client ready

    Note over C,E: Tool Invocation
    C->>P: github.get_file_contents(path="README.md")
    P->>P: Map function name to MCP tool
    P->>M: call_tool("github", "get_file_contents", {path: ...})
    M->>M: Look up connected client
    M->>T: Send MCP tool/call
    T->>E: {"method": "tools/call", "params": {...}}
    E->>E: Execute tool
    E-->>T: {"result": {"content": [...]}}
    T-->>M: MCP CallToolResult
    M->>M: Extract text content
    M-->>P: Result dict
    P-->>C: Return to caller

    Note over M,E: Shutdown
    M->>T: Disconnect
    T->>E: Close connection
```


## Key Files

| File | Role |
|------|------|
| `src/ot/proxy/manager.py` | Connection management and tool routing |
| `src/ot/executor/pack_proxy.py` | McpProxyPack wraps proxy as dot-notation namespace |
| `.onetool/config/servers.yaml` | External server definitions |
