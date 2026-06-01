# Claude Desktop setup

Install and authenticate first:

```powershell
cd C:\Users\YOUR_WINDOWS_USERNAME
git clone https://github.com/BojanMakivic/garminconnect-mcp.git
cd garminconnect-mcp
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\garminconnect-mcp-auth.exe
```

Then add this stdio server entry to Claude Desktop. Replace
`YOUR_WINDOWS_USERNAME` with your Windows username, and adjust the project path
if you cloned the repo somewhere else.

```json
{
  "mcpServers": {
    "garminconnect": {
      "command": "C:\\Users\\YOUR_WINDOWS_USERNAME\\garminconnect-mcp\\.venv\\Scripts\\garminconnect-mcp.exe",
      "args": [
        "--tokenstore",
        "C:\\Users\\YOUR_WINDOWS_USERNAME\\.garminconnect"
      ],
      "env": {
        "GARMINTOKENS": "C:\\Users\\YOUR_WINDOWS_USERNAME\\.garminconnect",
        "GARMINCONNECT_MCP_CONFIG": "C:\\Users\\YOUR_WINDOWS_USERNAME\\.garminconnect-mcp\\config.json"
      }
    }
  }
}
```
