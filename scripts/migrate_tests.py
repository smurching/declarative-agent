#!/usr/bin/env python3
"""
Script to migrate tests from async_client to openai_client.

Updates test files to use the OpenAI client directly instead of extracting
the underlying httpx client.
"""
import re
import sys
from pathlib import Path


def migrate_test_file(file_path: Path) -> tuple[bool, int]:
    """
    Migrate a single test file.

    Returns:
        (changed, num_replacements): Whether file was changed and number of replacements made
    """
    content = file_path.read_text()
    original_content = content
    num_replacements = 0

    # Pattern 1: Replace fixture parameter type annotation
    # async_client: AsyncClient -> openai_client
    pattern1 = r'(\s+)(self,\s+)async_client:\s*AsyncClient'
    replacement1 = r'\1\2openai_client'
    content, count1 = re.subn(pattern1, replacement1, content)
    num_replacements += count1

    # Pattern 2: Replace async_client usage in function bodies
    # async_client.post -> openai_client.post (and get, etc.)
    pattern2 = r'\basync_client\.(post|get|put|delete|patch)\('
    replacement2 = r'openai_client.\1('
    content, count2 = re.subn(pattern2, replacement2, content)
    num_replacements += count2

    # Pattern 3: Replace standalone async_client references
    # (but be careful not to replace in comments or strings)
    # This handles cases like: await async_client.get(...)
    pattern3 = r'(\s+)async_client(\s+)'
    replacement3 = r'\1openai_client\2'
    content, count3 = re.subn(pattern3, replacement3, content)
    num_replacements += count3

    changed = content != original_content

    if changed:
        file_path.write_text(content)

    return changed, num_replacements


def main():
    """Main migration function."""
    # Get test directory
    tests_dir = Path(__file__).parent.parent / "tests"

    if not tests_dir.exists():
        print(f"Error: Tests directory not found: {tests_dir}")
        sys.exit(1)

    # Find all test files
    test_files = list(tests_dir.glob("test_*.py"))

    if not test_files:
        print(f"No test files found in {tests_dir}")
        sys.exit(1)

    print(f"Found {len(test_files)} test files to migrate\n")

    total_changed = 0
    total_replacements = 0

    for test_file in test_files:
        print(f"Processing {test_file.name}...", end=" ")

        changed, num_replacements = migrate_test_file(test_file)

        if changed:
            print(f"✓ Updated ({num_replacements} replacements)")
            total_changed += 1
            total_replacements += num_replacements
        else:
            print("- No changes needed")

    print(f"\n{'='*60}")
    print(f"Migration complete!")
    print(f"  Files updated: {total_changed}/{len(test_files)}")
    print(f"  Total replacements: {total_replacements}")
    print(f"{'='*60}")

    if total_changed > 0:
        print("\nNext steps:")
        print("  1. Review the changes: git diff tests/")
        print("  2. Run tests: pytest tests/")
        print("  3. Commit if everything works: git add tests/ && git commit -m 'Migrate tests to use openai_client'")


if __name__ == "__main__":
    main()
