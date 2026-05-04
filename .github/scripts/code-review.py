#!/usr/bin/env python3
"""Automated code review for PR diffs.

Runs static analysis checks on the PR diff and posts findings
as a GitHub PR review comment. Designed to catch common issues
before human review.
"""
import os
import re
import json
import sys
from pathlib import Path

PR_NUMBER = os.environ.get('PR_NUMBER')
REPO = os.environ.get('REPO')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
DIFF_FILE = os.environ.get('DIFF_FILE', 'pr.diff')

if not all([PR_NUMBER, REPO, GITHUB_TOKEN]):
    print("Missing required environment variables")
    sys.exit(0)


def read_diff():
    """Read the PR diff file."""
    try:
        return Path(DIFF_FILE).read_text()
    except FileNotFoundError:
        print(f"Diff file {DIFF_FILE} not found")
        sys.exit(0)


def analyze_diff(diff_text):
    """Run static analysis checks on the diff."""
    findings = []
    added_lines = []
    current_file = None

    for line in diff_text.split('\n'):
        # Track which file we're in
        if line.startswith('diff --git'):
            current_file = line
        elif line.startswith('--- a/'):
            current_file = line[6:]
        elif line.startswith('+++ b/'):
            current_file = line[6:]
        elif line.startswith('+') and not line.startswith('+++'):
            added_lines.append((current_file, line[1:]))

    if not added_lines:
        findings.append({
            'severity': 'info',
            'message': 'No new lines added in this PR — might be a deletion-only change.',
            'file': 'N/A',
            'line': 0
        })
        return findings

    # Collect all added lines per file
    file_additions = {}
    for fname, line in added_lines:
        file_additions.setdefault(fname, []).append(line)

    for fname, lines in file_additions.items():
        full_text = '\n'.join(lines)

        # Check 1: Missing docstrings on new functions/classes in Python files
        if fname and fname.endswith('.py'):
            # New class without docstring
            class_matches = re.finditer(r'^class\s+(\w+)', full_text, re.MULTILINE)
            for m in class_matches:
                class_name = m.group(1)
                # Check if next non-empty line is a docstring
                rest = full_text[m.end():]
                next_line = rest.strip().split('\n')[0] if rest else ''
                if not next_line.startswith('"""') and not next_line.startswith("'''"):
                    findings.append({
                        'severity': 'suggestion',
                        'message': f'Class `{class_name}` is missing a docstring.',
                        'file': fname,
                        'line': 0
                    })

            # New public function without docstring (skip dunder methods)
            func_matches = re.finditer(r'^(?:@\w+\(.*\)\s*\n\s*)?def\s+(\w+)', full_text, re.MULTILINE)
            for m in func_matches:
                func_name = m.group(1)
                if func_name.startswith('_') and not func_name.startswith('__'):
                    continue  # skip private methods
                if func_name in ('__init__', '__repr__', '__str__'):
                    continue
                rest = full_text[m.end():]
                next_line = rest.strip().split('\n')[0] if rest else ''
                if not next_line.startswith('"""') and not next_line.startswith("'''"):
                    findings.append({
                        'severity': 'suggestion',
                        'message': f'Function `{func_name}()` could use a docstring for clarity.',
                        'file': fname,
                        'line': 0
                    })

            # Check for bare except
            if 'except:' in full_text and 'except Exception' not in full_text:
                findings.append({
                    'severity': 'warning',
                    'message': 'Bare `except:` clause detected — consider catching specific exceptions.',
                    'file': fname,
                    'line': 0
                })

            # Check for print statements (use logging instead)
            if re.search(r'^\s*print\(', full_text, re.MULTILINE):
                findings.append({
                    'severity': 'suggestion',
                    'message': '`print()` statement found — consider using `current_app.logger` for server code.',
                    'file': fname,
                    'line': 0
                })

        # Check 2: Missing test files for new Python modules
        if fname and fname.endswith('.py') and '/app/' in fname:
            module_name = Path(fname).stem
            test_name = f'test_{module_name}.py'
            if 'tests/' not in diff_text and test_name not in diff_text:
                # Only flag if there are substantial additions
                if len(lines) > 10:
                    findings.append({
                        'severity': 'suggestion',
                        'message': f'New module `{module_name}.py` with {len(lines)} lines added — consider adding `tests/{test_name}`.',
                        'file': fname,
                        'line': 0
                    })

        # Check 3: Hardcoded secrets or suspicious patterns
        suspicious_patterns = [
            (r'(?i)(password|secret|api_key|token)\s*=\s*["\'](?!.*environ|.*getenv)[^\'"]+["\']',
             'Hardcoded credential detected — use environment variables instead.'),
            (r'http://(?!localhost|127\.0\.0\.1)',
             'HTTP URL detected — consider HTTPS for external resources.'),
        ]
        for pattern, msg in suspicious_patterns:
            if re.search(pattern, full_text):
                findings.append({
                    'severity': 'warning',
                    'message': msg,
                    'file': fname,
                    'line': 0
                })

        # Check 4: Large additions without error handling
        if fname and fname.endswith('.py') and len(lines) > 20:
            if 'try:' not in full_text and 'raise' not in full_text:
                findings.append({
                    'severity': 'suggestion',
                    'message': f'Large block ({len(lines)} lines) without visible error handling — consider try/except for robustness.',
                    'file': fname,
                    'line': 0
                })

    # Sort by severity
    severity_order = {'warning': 0, 'suggestion': 1, 'info': 2}
    findings.sort(key=lambda f: severity_order.get(f['severity'], 3))

    return findings


def format_review_body(findings):
    """Format findings as a GitHub PR review comment."""
    if not findings:
        return '🤖 **Automated Code Review**\n\n✅ No issues found. Code looks clean!\n\n---\n*Review generated automatically. Human review still recommended.*'

    severity_counts = {}
    for f in findings:
        severity_counts[f['severity']] = severity_counts.get(f['severity'], 0) + 1

    # Build emoji summary
    parts = []
    if severity_counts.get('warning', 0):
        parts.append(f"⚠️ {severity_counts['warning']} warning(s)")
    if severity_counts.get('suggestion', 0):
        parts.append(f"💡 {severity_counts['suggestion']} suggestion(s)")
    if severity_counts.get('info', 0):
        parts.append(f"ℹ️ {severity_counts['info']} note(s)")

    body = f'🤖 **Automated Code Review**\n\n{" | ".join(parts) if parts else "No issues"}\n\n'

    # Group by file
    by_file = {}
    for f in findings:
        by_file.setdefault(f['file'], []).append(f)

    for fname, file_findings in by_file.items():
        short_name = fname.replace('b/', '') if fname else 'General'
        body += f'### `{short_name}`\n\n'
        for finding in file_findings:
            emoji = {'warning': '⚠️', 'suggestion': '💡', 'info': 'ℹ️'}.get(finding['severity'], '•')
            body += f'- {emoji} {finding["message"]}\n'
        body += '\n'

    body += '---\n*Review generated automatically. Human review still recommended.*'
    return body


def post_review(body):
    """Post the review as a PR comment using GitHub API."""
    import requests

    url = f'https://api.github.com/repos/{REPO}/issues/{PR_NUMBER}/comments'
    headers = {
        'Authorization': f'Bearer {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
    }

    response = requests.post(url, headers=headers, json={'body': body}, timeout=30)

    if response.status_code in (200, 201):
        print(f'✅ Review posted to PR #{PR_NUMBER}')
    else:
        print(f'❌ Failed to post review: {response.status_code} {response.text[:300]}')
        sys.exit(0)  # Don't fail the build on review posting errors


def main():
    print(f'🔍 Running automated code review for PR #{PR_NUMBER}...')
    diff_text = read_diff()
    findings = analyze_diff(diff_text)
    body = format_review_body(findings)
    print(body)
    print()
    post_review(body)


if __name__ == '__main__':
    main()
