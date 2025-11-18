#!/usr/bin/env python3
"""Test that all ASQL examples in examples/real/ compile successfully."""

import sys
from pathlib import Path
from typing import List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from asql import compile


def test_asql_file(asql_path: Path) -> Tuple[bool, str, Optional[str]]:
    """Test that an ASQL file compiles."""
    try:
        asql_content = asql_path.read_text()
        # Remove comments and header for compilation test
        lines = asql_content.split('\n')
        # Skip comment lines at the start
        code_lines = []
        for line in lines:
            if line.strip().startswith('--'):
                continue
            if line.strip():
                code_lines.append(line)
        
        if not code_lines:
            return False, "No ASQL code found (only comments)", None
        
        asql_code = '\n'.join(code_lines)
        compiled_sql = compile(asql_code)
        return True, "Compiled successfully", compiled_sql
    except Exception as e:
        return False, str(e), None


def main():
    """Test all ASQL files in examples/real/."""
    real_dir = project_root / "examples" / "real"
    
    if not real_dir.exists():
        print(f"❌ Directory not found: {real_dir}")
        return 1
    
    asql_files = sorted(real_dir.glob("*.asql"))
    
    if not asql_files:
        print(f"⚠️  No ASQL files found in {real_dir}")
        print("   Run scripts/fetch_fivetran_queries.py first to fetch SQL files")
        print("   Then create ASQL equivalents manually")
        return 0
    
    print(f"Testing {len(asql_files)} ASQL files...\n")
    
    passed = 0
    failed = []
    
    for asql_file in asql_files:
        print(f"Testing {asql_file.name}...", end=" ")
        success, message, compiled = test_asql_file(asql_file)
        
        if success:
            print(f"✅ {message}")
            passed += 1
        else:
            print(f"❌ {message}")
            failed.append((asql_file.name, message))
    
    print(f"\n{'='*60}")
    print(f"Results: {passed}/{len(asql_files)} passed")
    
    if failed:
        print(f"\n❌ Failed ({len(failed)}):")
        for filename, error in failed:
            print(f"  - {filename}: {error}")
        return 1
    else:
        print("\n✅ All ASQL files compile successfully!")
        return 0


if __name__ == "__main__":
    sys.exit(main())

