#!/usr/bin/env python3
"""Prepare docs for build by replacing playground URLs with environment variable."""

import os
import re
from pathlib import Path

def replace_playground_urls(content: str, playground_url: str) -> str:
    """Replace relative playground URLs with absolute URL."""
    # Replace iframe src="/playground/embed" with full URL
    content = re.sub(
        r'src="/playground/embed"',
        f'src="{playground_url}/embed"',
        content
    )
    # Replace href="/playground" with full URL (but not in code blocks)
    # Match href="/playground" that's not inside code blocks
    content = re.sub(
        r'href="/playground"',
        f'href="{playground_url}"',
        content
    )
    # Replace iframe src="/playground" with full URL
    content = re.sub(
        r'src="/playground"',
        f'src="{playground_url}"',
        content
    )
    return content

def main():
    """Main function to process docs."""
    playground_url = os.environ.get('PLAYGROUND_URL', 'https://play.analyticsql.com')
    docs_dir = Path(__file__).parent.parent / 'docs'
    
    # Process all markdown files
    for md_file in docs_dir.rglob('*.md'):
        try:
            content = md_file.read_text(encoding='utf-8')
            updated_content = replace_playground_urls(content, playground_url)
            if content != updated_content:
                md_file.write_text(updated_content, encoding='utf-8')
                print(f"Updated {md_file}")
        except Exception as e:
            print(f"Error processing {md_file}: {e}")

if __name__ == '__main__':
    main()

