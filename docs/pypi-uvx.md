# PyPI and uvx usage

After `garminconnect-mcp` is published to PyPI, users can run it without cloning
the repository.

## First-time authentication

Run this once in a normal terminal:

```powershell
uvx --from garminconnect-mcp garminconnect-mcp-auth
```

On macOS or Linux:

```bash
uvx --from garminconnect-mcp garminconnect-mcp-auth
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
uvx garminconnect-mcp
```

For MCP desktop clients, use this command configuration:

```json
{
  "command": "uvx",
  "args": [
    "garminconnect-mcp"
  ],
  "env": {
    "GARMINTOKENS": "C:\\Users\\YOUR_WINDOWS_USERNAME\\.garminconnect"
  }
}
```

## Why auth uses `--from`

`uvx` assumes the package name and command name are the same. The package is
named `garminconnect-mcp`, and it provides two commands:

```text
garminconnect-mcp
garminconnect-mcp-auth
```

Because `garminconnect-mcp-auth` comes from the `garminconnect-mcp` package, the
auth command is:

```powershell
uvx --from garminconnect-mcp garminconnect-mcp-auth
```

The shorter command below would require publishing a second PyPI package named
`garminconnect-mcp-auth`:

```powershell
uvx garminconnect-mcp-auth
```
