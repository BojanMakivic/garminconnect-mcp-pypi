# PyPI release checklist

This folder is prepared for publishing `garmin-connect-mcp-server` as a PyPI package.

## User commands after publishing

Run the MCP server:

```powershell
uvx garmin-connect-mcp-server
```

Run first-time authentication:

```powershell
uvx --from garmin-connect-mcp-server garmin-connect-mcp-server-auth
```

`uvx garmin-connect-mcp-server-auth` only works if there is also a PyPI package named
`garmin-connect-mcp-server-auth`. The main package is named `garmin-connect-mcp-server`, so the
auth command should use `--from`.

## Local validation

```powershell
cd C:\Users\Bojan\garminconnect-mcp-pypi
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip build twine
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest --basetemp .pytest-tmp
.\.venv\Scripts\python.exe -m build
.\.venv\Scripts\python.exe -m twine check dist\*
```

## Publishing

Recommended: publish with PyPI Trusted Publishing from GitHub Actions. This
avoids storing long-lived PyPI API tokens in GitHub secrets.

The workflow is:

```text
.github/workflows/publish-to-pypi.yml
```

Create pending trusted publishers:

```text
PyPI project name: garmin-connect-mcp-server
GitHub owner: BojanMakivic
GitHub repository name: garminconnect-mcp-pypi
Workflow filename: publish-to-pypi.yml
Environment name for PyPI: pypi
Environment name for TestPyPI: testpypi
```

Then publish to TestPyPI from GitHub Actions with a manual workflow run.

Publish to real PyPI by pushing a version tag:

```powershell
git tag v0.1.4
git push origin v0.1.4
```

Manual upload is also possible:

```powershell
.\.venv\Scripts\python.exe -m twine upload dist\*
```

For manual upload, use a PyPI API token, not your PyPI password.
