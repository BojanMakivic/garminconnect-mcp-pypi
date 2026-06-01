# PyPI and uvx usage

After `garmin-connect-mcp-server` is published to PyPI, users can run it without cloning
the repository.

## First-time authentication

Run this once in a normal terminal:

```powershell
uvx --from garmin-connect-mcp-server garmin-connect-mcp-server-auth
```

On macOS or Linux:

```bash
uvx --from garmin-connect-mcp-server garmin-connect-mcp-server-auth
```

This stores Garmin tokens locally on the user's machine, usually in:

```text
~/.garminconnect
```

On Windows, that normally resolves to:

```text
C:\Users\YOUR_WINDOWS_USERNAME\.garminconnect
```

## Run the MCP server

```powershell
uvx garmin-connect-mcp-server
```

For MCP desktop clients, use this command configuration:

```json
{
  "command": "uvx",
  "args": [
    "garmin-connect-mcp-server"
  ],
  "env": {
    "GARMINTOKENS": "C:\\Users\\YOUR_WINDOWS_USERNAME\\.garminconnect"
  }
}
```

## Why auth uses `--from`

`uvx` assumes the package name and command name are the same. The package is
named `garmin-connect-mcp-server`, and it provides two commands:

```text
garmin-connect-mcp-server
garmin-connect-mcp-server-auth
```

Because `garmin-connect-mcp-server-auth` comes from the `garmin-connect-mcp-server` package, the
auth command is:

```powershell
uvx --from garmin-connect-mcp-server garmin-connect-mcp-server-auth
```

The shorter command below would require publishing a second PyPI package named
`garmin-connect-mcp-server-auth`:

```powershell
uvx garmin-connect-mcp-server-auth
```
