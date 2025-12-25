# ASQL Versioning Strategy

**Date**: 2025-12-20

## Current State

Version is currently duplicated in 3 places:
1. `pyproject.toml`: `version = "0.1.0"` (Python package standard)
2. `asql/__init__.py`: `__version__ = "0.1.0"` (runtime access)
3. `vscode-extension/package.json`: `"version": "0.1.0"` (VS Code extension)

There's a test in `tests/test_basic.py` that verifies `asql.__version__ == "0.1.0"`.

## Versioning Strategy

### 1. Single Source of Truth

**Decision**: Use `pyproject.toml` as the single source of truth.

**Implementation**:
- `pyproject.toml` contains the canonical version
- `asql/__init__.py` dynamically reads from package metadata using `importlib.metadata`
- VS Code extension version is synchronized manually (or via release script)
- Tests verify the version can be accessed, not a hardcoded value

**Benefits**:
- Standard Python packaging approach
- Version defined in one place
- No duplication to keep in sync
- Works with build tools, CI/CD, and pip

### 2. Semantic Versioning (SemVer)

ASQL follows [Semantic Versioning 2.0.0](https://semver.org/): `MAJOR.MINOR.PATCH`

For a language/compiler like ASQL:

| Version Part | When to Increment | Examples |
|--------------|-------------------|----------|
| **MAJOR** | Breaking syntax changes that could cause existing `.asql` files to fail compilation | Removing a keyword, changing operator precedence |
| **MINOR** | New features (backwards compatible) | New operators, new functions, new clauses |
| **PATCH** | Bug fixes, performance improvements, documentation | Fixing edge cases, dialect improvements |

**Pre-1.0 Convention** (current state):
- While in `0.x.y`, MINOR version changes may include breaking changes
- Move to `1.0.0` when the language specification stabilizes

### 3. What Gets Versioned

| Component | Version Strategy |
|-----------|------------------|
| **Python Package** (`asql`) | Main version, source of truth |
| **Language Spec** (`docs/spec.md`) | Follows package version |
| **Documentation** | Latest only (for now) |
| **VS Code Extension** | Synchronized with package version |

### 4. Documentation Versioning

**Current Phase** (Experimental):
- Single version of docs (latest)
- Document breaking changes in a CHANGELOG
- Version is displayed in docs when relevant

**Future Phase** (Post-1.0):
- Use [mike](https://github.com/jimporter/mike) for versioned MkDocs
- Maintain docs for latest + LTS versions
- Version selector dropdown on docs site

### 5. Version Access

After implementation, version can be accessed:

```python
import asql
print(asql.__version__)  # "0.1.0"

# Or using importlib directly
from importlib.metadata import version
print(version("asql"))  # "0.1.0"
```

### 6. Release Process (Future)

When ready for releases:

1. Update version in `pyproject.toml`
2. Update `vscode-extension/package.json` (can be automated)
3. Update CHANGELOG.md
4. Create git tag: `git tag v0.2.0`
5. Push tag: `git push --tags`
6. CI builds and publishes to PyPI
7. VS Code extension published to marketplace

## Implementation Checklist

- [x] Document versioning strategy (this file)
- [x] Update `asql/__init__.py` to read version dynamically
- [x] Update test to verify version is accessible (not hardcoded)
- [x] Add CHANGELOG.md to track changes
- [x] Add `__version__` to `__all__` exports
- [ ] (Future) Add release workflow in GitHub Actions
- [ ] (Future) Add `mike` for versioned docs
- [ ] (Future) Sync VS Code extension version via release script

## Files Changed

1. `asql/__init__.py` - Dynamic version reading via `importlib.metadata`
2. `tests/test_basic.py` - Updated test to check version format, not hardcoded value
3. `CHANGELOG.md` - New file for tracking changes

## References

- [PEP 517](https://peps.python.org/pep-0517/) - Build system interface
- [Semantic Versioning](https://semver.org/)
- [mike - MkDocs versioning](https://github.com/jimporter/mike)
- [importlib.metadata](https://docs.python.org/3/library/importlib.metadata.html)
