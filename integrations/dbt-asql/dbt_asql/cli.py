"""
Command-line interface for dbt-asql.

Usage:
    dbt-asql compile [--models-dir=<dir>] [--dialect=<dialect>]
    dbt-asql clean [--models-dir=<dir>]
    
Commands:
    compile     Convert .asql files to .sql files
    clean       Remove generated .sql files

Options:
    --models-dir=<dir>      Path to models directory [default: models]
    --dialect=<dialect>     SQL dialect to compile to [default: postgres]
"""

from __future__ import annotations

import argparse
import sys

from dbt_asql.plugin import (
    AsqlCompilationError,
    InvalidDialectError,
    VALID_DIALECTS,
)


def main() -> int:
    """Main entry point for dbt-asql CLI."""
    parser = argparse.ArgumentParser(
        prog="dbt-asql",
        description="ASQL compiler for dbt projects",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # compile command
    compile_parser = subparsers.add_parser(
        "compile",
        help="Compile .asql files to .sql files",
    )
    compile_parser.add_argument(
        "--models-dir",
        default="models",
        help="Path to models directory (default: models)",
    )
    compile_parser.add_argument(
        "--manifest",
        default="target/manifest.json",
        help="Path to dbt manifest.json (default: target/manifest.json)",
    )
    compile_parser.add_argument(
        "--dialect",
        default="postgres",
        choices=sorted(VALID_DIALECTS),
        help="SQL dialect to compile to (default: postgres)",
    )
    compile_parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress output",
    )
    
    # clean command
    clean_parser = subparsers.add_parser(
        "clean",
        help="Remove generated .sql files for all .asql files",
    )
    clean_parser.add_argument(
        "--models-dir",
        default="models",
        help="Path to models directory (default: models)",
    )
    clean_parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress output",
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return 1
    
    if args.command == "compile":
        return cmd_compile(args)
    elif args.command == "clean":
        return cmd_clean(args)
    else:
        parser.print_help()
        return 1


def cmd_compile(args: argparse.Namespace) -> int:
    """Handle compile command."""
    from dbt_asql.plugin import compile_project
    
    try:
        compiled = compile_project(
            models_dir=args.models_dir,
            manifest_path=args.manifest,
            dialect=args.dialect,
            verbose=not args.quiet,
        )
        
        if not args.quiet:
            print(f"\n✓ Compiled {len(compiled)} file(s)")
        
        return 0
        
    except InvalidDialectError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except AsqlCompilationError as e:
        print(f"Compilation Error: {e}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def cmd_clean(args: argparse.Namespace) -> int:
    """Handle clean command."""
    from dbt_asql.plugin import clean_project
    
    try:
        removed = clean_project(
            models_dir=args.models_dir,
            verbose=not args.quiet,
        )
        
        if not args.quiet:
            print(f"\n✓ Removed {len(removed)} file(s)")
        
        return 0
        
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
