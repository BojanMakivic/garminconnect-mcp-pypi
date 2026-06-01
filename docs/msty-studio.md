# Msty Studio setup

Msty Studio can run this server directly from PyPI with `uvx`.

## Authenticate Garmin locally

Run this once in a normal terminal:

```powershell
uvx --from garmin-connect-mcp-server garmin-connect-mcp-server-auth
```

Garmin tokens stay on this machine in:

```text
C:\Users\YOUR_WINDOWS_USERNAME\.garminconnect
```

## Add the tool in Msty Studio

Create a local stdio JSON tool and paste:

```json
{
  "command": "uvx",
  "args": [
    "garmin-connect-mcp-server"
  ],
  "env": {
    "GARMINTOKENS": "C:\\Users\\YOUR_WINDOWS_USERNAME\\.garminconnect",
    "GARMINCONNECT_MCP_CONFIG": "C:\\Users\\YOUR_WINDOWS_USERNAME\\.garminconnect-mcp\\config.json"
  }
}
```

Replace `YOUR_WINDOWS_USERNAME` with your Windows username. The token path must
match the directory created by the auth command.
