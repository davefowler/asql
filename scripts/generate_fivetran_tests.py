#!/usr/bin/env python3
"""Generate pytest tests from Fivetran dbt examples.

This script tests all Fivetran dbt examples and generates a pytest file
with the passing examples. Run from project root:

    ./venv/bin/python scripts/generate_fivetran_tests.py
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from playground import strip_jinja_templates
from asql.reverse_compiler import reverse_compile
from asql.errors import ASQLCompilationError
import re


def generate_fivetran_tests():
    """Test all Fivetran examples and generate pytest file."""
    real_examples_dir = project_root / 'examples' / 'real'
    if not real_examples_dir.exists():
        print(f"Directory {real_examples_dir} does not exist")
        return 1
    
    sql_files = sorted(real_examples_dir.glob('dbt_*.sql'))
    print(f"Testing {len(sql_files)} Fivetran examples...\n")
    
    passed = []
    failed = []
    skipped = []
    
    for sql_file in sql_files:
        try:
            content = sql_file.read_text()
            
            # Skip files that are too small or contain errors
            if len(content) < 100 or '404: Not Found' in content:
                skipped.append((sql_file.name, 'File too small or contains 404'))
                continue
            
            # Clean Jinja templates
            cleaned = strip_jinja_templates(content)
            
            # Check for remaining macros
            macro_count = len(re.findall(r'\{\{[^}]+\}\}', cleaned)) + len(re.findall(r'\{%[^%]+%\}', cleaned))
            if macro_count > 0:
                failed.append((sql_file.name, f'Still contains {macro_count} dbt macros'))
                continue
            
            # Check for broken SQL (empty FROM, etc.)
            if re.search(r'\bfrom\s*$', cleaned, re.MULTILINE | re.IGNORECASE):
                failed.append((sql_file.name, 'Broken FROM clause (missing table name)'))
                continue
            
            # Try reverse compilation
            asql = reverse_compile(cleaned, source_dialect='snowflake')
            
            # Verify ASQL is not empty
            if not asql.strip():
                failed.append((sql_file.name, 'Generated empty ASQL'))
                continue
            
            passed.append(sql_file.name)
            
        except ASQLCompilationError as e:
            error_msg = str(e)[:150]
            failed.append((sql_file.name, f'Compilation error: {error_msg}'))
        except Exception as e:
            error_msg = str(e)[:150]
            failed.append((sql_file.name, f'Error: {error_msg}'))
    
    # Print results
    print("=" * 80)
    print("Test Results")
    print("=" * 80)
    print(f"\n✓ Passed: {len(passed)}/{len(sql_files)}")
    print(f"✗ Failed: {len(failed)}/{len(sql_files)}")
    print(f"⊘ Skipped: {len(skipped)}/{len(sql_files)}")
    
    if failed:
        print(f"\n{'=' * 80}")
        print("Failed Examples:")
        print("=" * 80)
        for name, error in failed[:20]:  # Show first 20 failures
            print(f"\n✗ {name}")
            print(f"  {error}")
        if len(failed) > 20:
            print(f"\n... and {len(failed) - 20} more failures")
    
    if skipped:
        print(f"\n{'=' * 80}")
        print("Skipped Examples:")
        print("=" * 80)
        for name, reason in skipped:
            print(f"⊘ {name}: {reason}")
    
    # Save passing examples to a test file
    if passed:
        test_file = project_root / 'tests' / 'test_fivetran_examples_compilation.py'
        with open(test_file, 'w') as f:
            f.write('''"""Test that Fivetran examples compile correctly to ASQL.

This test file is auto-generated. Run scripts/generate_fivetran_tests.py to regenerate.
"""

import pytest
from playground import strip_jinja_templates
from asql.reverse_compiler import reverse_compile
from asql.errors import ASQLCompilationError
from pathlib import Path

REAL_EXAMPLES_DIR = Path(__file__).parent.parent / 'examples' / 'real'

''')
            f.write(f'# {len(passed)} passing examples\n')
            f.write('PASSING_EXAMPLES = [\n')
            for name in sorted(passed):
                f.write(f"    '{name}',\n")
            f.write(']\n\n')
            
            f.write('''
@pytest.mark.parametrize("filename", PASSING_EXAMPLES)
def test_fivetran_example_compiles(filename):
    """Test that a Fivetran example compiles to ASQL."""
    sql_file = REAL_EXAMPLES_DIR / filename
    assert sql_file.exists(), f"File {filename} does not exist"
    
    content = sql_file.read_text()
    cleaned = strip_jinja_templates(content)
    
    # Should not have any macros remaining
    import re
    macro_count = len(re.findall(r'\\{\\{[^}]+\\}\\}', cleaned)) + len(re.findall(r'\\{%[^%]+%\\}', cleaned))
    assert macro_count == 0, f"File {filename} still contains {macro_count} dbt macros"
    
    # Should compile to ASQL
    asql = reverse_compile(cleaned, source_dialect='snowflake')
    assert asql.strip(), f"File {filename} generated empty ASQL"
''')
        
        print(f"\n{'=' * 80}")
        print(f"✓ Saved {len(passed)} passing examples to {test_file}")
    
    return 0 if len(failed) == 0 else 1


if __name__ == '__main__':
    sys.exit(generate_fivetran_tests())

