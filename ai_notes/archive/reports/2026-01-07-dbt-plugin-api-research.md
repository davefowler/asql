# dbt Plugin API Research for Custom File Extensions

**Date**: January 7, 2026  
**Status**: Complete  
**Related**: [dbt-asql Design Doc](archive/designs/2026-01-06-dbt-asql-integration.md)

## Summary

Investigated whether dbt's plugin API supports custom file extensions (e.g., `.asql`). **Result: It does not.** File extensions are hardcoded in dbt-core.

## Findings

### 1. dbt's Plugin API (`dbtPlugin`)

dbt provides a `dbtPlugin` base class in `dbt.plugins`:

```python
class dbtPlugin:
    """
    EXPERIMENTAL: dbtPlugin is the base class for creating plugins.
    Its interface is **not** stable and will likely change.
    """
    
    def get_nodes(self) -> PluginNodes:
        """Provide PluginNodes to dbt for injection into dbt's DAG."""
        ...
    
    def get_manifest_artifacts(self, manifest) -> PluginArtifacts:
        """Given a manifest, provide PluginArtifacts for writing."""
        ...
```

**Purpose**: Injecting nodes into the DAG and creating artifacts. **Not** for file types.

### 2. File Extension Handling

File extensions are defined in `dbt/parser/read_files.py`:

```python
def get_file_types_for_project(project):
    file_types = {
        ParseFileType.Model: {
            "paths": project.model_paths,
            "extensions": [".sql", ".py"],  # HARDCODED
            "parser": "ModelParser",
        },
        # ... other file types
    }
```

**Models only support `.sql` and `.py`**. There's no hook to add custom extensions.

### 3. ModelLanguage Enum

```python
from dbt.parser.base import ModelLanguage
ModelLanguage.__members__  # {'python': <python>, 'sql': <sql>}
```

Only SQL and Python languages are supported. No extension mechanism.

### 4. How dbt-prql Works

dbt-prql uses a **Jinja extension** approach, NOT native file support:

1. Uses a `.pth` file (`zzz_dbt_prql.pth`) for automatic loading
2. Patches dbt's Jinja environment via `dbt.clients.jinja`
3. Adds a `PrqlExtension` with `{% prql %}...{% endprql %}` tags
4. Still requires `.sql` file extension and wrapper tags

**dbt-prql does NOT support native `.prql` files.**

## Approaches for dbt-asql

### Approach 1: CLI Preprocessor ✅ (Implemented)

```bash
dbt-asql compile  # .asql → .sql
dbt run
```

**Pros:**
- Works with any dbt version
- No monkey-patching
- Native `.asql` files
- Clear separation of concerns

**Cons:**
- Extra build step
- Generated `.sql` files in repo (can add to .gitignore)

### Approach 2: Jinja Extension ✅ (Implemented)

```sql
{% asql %}
from orders
  where status = 'completed'
{% endasql %}
```

**Pros:**
- Works automatically when installed
- No extra build step

**Cons:**
- Requires wrapper tags (not "native")
- Uses `.sql` extension

### Approach 3: dbt Core Feature Request ⏳

Request a plugin hook for custom file extensions. Would enable:

```python
# Future API (hypothetical)
@dbt.register_file_type
class AsqlFileType:
    extension = ".asql"
    parser = "ModelParser"
    
    def preprocess(self, content: str) -> str:
        return compile_asql_to_sql(content)
```

**Status**: Could file a dbt-labs/dbt-core issue/discussion.

## Implementation Decision

**Use both approaches:**

1. **CLI Preprocessor** — For users who want native `.asql` files
2. **Jinja Extension** — For users who prefer no extra build step

This matches what users expect:
- Clean `.asql` files with native syntax
- Automatic compilation without wrappers (via CLI)
- Fallback to inline `{% asql %}` blocks

## Code References

### Key dbt modules examined:

- `dbt/plugins/__init__.py` — Plugin manager and base class
- `dbt/parser/read_files.py` — File extension definitions
- `dbt/parser/base.py` — Parser base classes, ModelLanguage enum
- `dbt/contracts/files.py` — File handling contracts

### dbt-prql implementation:

- `dbt_prql/patch.py` — Jinja environment patching
- `zzz_dbt_prql.pth` — Automatic loading via site-packages

## Next Steps

1. ✅ Implement CLI preprocessor
2. ✅ Implement Jinja extension
3. ✅ Write tests for both approaches
4. ⏳ Consider filing dbt-core feature request
5. ⏳ Publish to PyPI
