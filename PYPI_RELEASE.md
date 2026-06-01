# PyPI release checklist

This folder is prepared for publishing `garminconnect-mcp` as a PyPI package.

## User commands after publishing

Run the MCP server:

```powershell
uvx garminconnect-mcp
```

Run first-time authentication:

```powershell
uvx --from garminconnect-mcp garminconnect-mcp-auth
```

`uvx garminconnect-mcp-auth` only works if there is also a PyPI package named
`garminconnect-mcp-auth`. The main package is named `garminconnect-mcp`, so the
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
PyPI project name: garminconnect-mcp
GitHub owner: BojanMakivic
GitHub repository name: garminconnect-mcp
Workflow filename: publish-to-pypi.yml
Environment name for PyPI: pypi
Environment name for TestPyPI: testpypi
```

Then publish to TestPyPI from GitHub Actions with a manual workflow run.

Publish to real PyPI by pushing a version tag:

```powershell
git tag v0.1.0
git push origin v0.1.0
```

Manual upload is also possible:

```powershell
.\.venv\Scripts\python.exe -m twine upload dist\*
```

For manual upload, use a PyPI API token, not your PyPI password.
