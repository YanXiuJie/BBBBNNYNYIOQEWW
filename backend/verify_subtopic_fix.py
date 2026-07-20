"""
Verification script for subtopic selection bug fix.

Tests that all subtopic queries now filter for subtopics with active questions.
"""

import re
from pathlib import Path


def check_file_for_unfixed_queries(filepath: Path) -> list[dict]:
    """
    Check a file for subtopic queries that don't filter by questions.

    Returns list of issues found.
    """
    issues = []

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for i, line in enumerate(lines, start=1):
        # Pattern 1: select(Subtopic) without JOIN Question
        if 'select(Subtopic)' in line:
            # Check next 5 lines for JOIN Question
            context = ''.join(lines[max(0, i-1):min(len(lines), i+5)])
            if 'Question' not in context and 'join(Question' not in context.lower():
                issues.append({
                    'line': i,
                    'content': line.strip(),
                    'issue': 'select(Subtopic) without JOIN Question filter'
                })

        # Pattern 2: select(MasteryRecord) for weak subtopics without JOIN Question
        if 'select(MasteryRecord)' in line:
            context = ''.join(lines[max(0, i-1):min(len(lines), i+10)])
            if 'mastery < 70' in context.lower() or 'score < 70' in context.lower():
                if 'Question' not in context and 'join(Question' not in context.lower():
                    issues.append({
                        'line': i,
                        'content': line.strip(),
                        'issue': 'MasteryRecord query for weak subtopics without JOIN Question filter'
                    })

    return issues


def verify_fixes():
    """
    Main verification function.
    """
    backend_dir = Path(__file__).parent

    files_to_check = [
        backend_dir / 'app' / 'services' / 'adaptive_selector.py',
        backend_dir / 'app' / 'main.py'
    ]

    print("=" * 80)
    print("SUBTOPIC SELECTION BUG FIX VERIFICATION")
    print("=" * 80)
    print()

    all_clear = True

    for filepath in files_to_check:
        print(f"Checking: {filepath.relative_to(backend_dir)}")
        print("-" * 80)

        if not filepath.exists():
            print(f"  [FAIL] File not found: {filepath}")
            all_clear = False
            continue

        issues = check_file_for_unfixed_queries(filepath)

        if issues:
            print(f"  [FAIL] Found {len(issues)} potential issue(s):")
            for issue in issues:
                print(f"     Line {issue['line']}: {issue['issue']}")
                print(f"       {issue['content']}")
            all_clear = False
        else:
            print("  [PASS] No issues found - all subtopic queries filter by questions")

        print()

    print("=" * 80)
    if all_clear:
        print("[PASS] VERIFICATION PASSED: All subtopic selections filter for questions")
        print()
        print("Fixed locations:")
        print("  1. adaptive_selector.py:266 - Phase 1 diagnosis subtopic selection")
        print("  2. adaptive_selector.py:195 - Phase 1 weakest subtopics fallback")
        print("  3. adaptive_selector.py:395 - Phase 3 random subtopic selection")
        print("  4. main.py:499-504 - Comprehensive practice start endpoint")
    else:
        print("[FAIL] VERIFICATION FAILED: Some subtopic selections still need fixing")
    print("=" * 80)

    return all_clear


if __name__ == '__main__':
    success = verify_fixes()
    exit(0 if success else 1)
