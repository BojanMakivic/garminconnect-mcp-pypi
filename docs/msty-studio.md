# Msty Studio setup

Msty Studio can run this server as a local stdio JSON tool. Install and
authenticate the project before adding it to Msty.

## Install

Open PowerShell:

```powershell
cd C:\Users\YOUR_WINDOWS_USERNAME
git clone https://github.com/BojanMakivic/garminconnect-mcp.git
cd garminconnect-mcp
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

Python 3.12 also works:

```powershell
py -3.12 -m venv .venv
```

## Authenticate Garmin locally

Run this once:

```powershell
cd C:\Users\YOUR_WINDOWS_USERNAME\garminconnect-mcp
.\.venv\Scripts\garminconnect-mcp-auth.exe
```

Garmin tokens stay on this machine in:

```text
C:\Users\YOUR_WINDOWS_USERNAME\.garminconnect
```

## Add the tool in Msty Studio

Create a local stdio JSON tool and paste:

```json
{
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
```

Replace `YOUR_WINDOWS_USERNAME` with your Windows username. If the project was
cloned somewhere else, replace the project path with the real location.

Use the full `.venv\Scripts\garminconnect-mcp.exe` path because desktop apps do
not always inherit the same PATH as PowerShell.
