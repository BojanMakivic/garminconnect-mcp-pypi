# Claude Desktop setup

Claude Desktop can run this server directly from PyPI with `uvx`.

## Authenticate Garmin locally

Run this once in a normal terminal:

```powershell
uvx --from garmin-connect-mcp-server garmin-connect-mcp-server-auth
```

Garmin tokens stay on this machine in:

```text
C:\Users\YOUR_WINDOWS_USERNAME\.garminconnect
```

## Add the MCP server

Add this entry to Claude Desktop. Replace `YOUR_WINDOWS_USERNAME` with your
Windows username.

```json
{
  "mcpServers": {
    "garminconnect": {
      "command": "uvx",
      "args": [
        "garmin-connect-mcp-server"
      ],
      "env": {
        "GARMINTOKENS": "C:\\Users\\YOUR_WINDOWS_USERNAME\\.garminconnect",
        "GARMINCONNECT_MCP_CONFIG": "C:\\Users\\YOUR_WINDOWS_USERNAME\\.garminconnect-mcp\\config.json"
      }
    }
  }
}
```
