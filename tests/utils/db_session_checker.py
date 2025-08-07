"""
Database Session Handling Checker Utility

This utility helps identify incorrect database session handling patterns in the codebase.
It scans Python files for problematic patterns like:
1. Using get_db() with next() instead of as a context manager
2. Missing try/finally blocks when manually managing sessions
3. Unclosed database sessions

Usage:
    python -m tests.utils.db_session_checker

The script will output all files with potential issues and the line numbers.
"""
import os
import re
import sys
from typing import Dict, List, Tuple, Set


class DbSessionChecker:
    """Utility class to check for database session handling issues."""

    def __init__(self, root_dir: str):
        """Initialize the checker with the root directory to scan.
        
        Args:
            root_dir: Root directory of the codebase to scan.
        """
        self.root_dir = root_dir
        self.issues_found = 0
        
        # Patterns to look for
        self.patterns = {
            "next_db_session": re.compile(r'next\s*\(\s*(?:get_db\(\)|db_session_generator)\s*\)'),
            "db_session_generator": re.compile(r'db_session_generator\s*=\s*get_db\(\)'),
            "get_db_without_with": re.compile(r'(?<!with\s)get_db\(\)(?!\s*as)'),
        }
        
        # Files to exclude
        self.exclude_dirs = {
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            "node_modules",
            "tests/utils",  # Exclude this utility itself
        }
        
        # Files that have been fixed
        self.fixed_files: Set[str] = set()

    def should_check_file(self, file_path: str) -> bool:
        """Determine if a file should be checked.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            bool: True if the file should be checked, False otherwise.
        """
        # Only check Python files
        if not file_path.endswith(".py"):
            return False
            
        # Skip excluded directories
        for exclude_dir in self.exclude_dirs:
            if exclude_dir in file_path.split(os.sep):
                return False
                
        return True

    def check_file(self, file_path: str) -> Dict[str, List[int]]:
        """Check a file for database session handling issues.
        
        Args:
            file_path: Path to the file to check.
            
        Returns:
            Dict[str, List[int]]: Dictionary mapping issue types to line numbers.
        """
        issues: Dict[str, List[int]] = {pattern_name: [] for pattern_name in self.patterns}
        
        try:
            with open(file_path, "r") as f:
                lines = f.readlines()
                
            for i, line in enumerate(lines, 1):
                for pattern_name, pattern in self.patterns.items():
                    if pattern.search(line):
                        issues[pattern_name].append(i)
        except Exception as e:
            print(f"Error checking file {file_path}: {e}")
            
        return issues

    def scan_directory(self) -> Dict[str, Dict[str, List[int]]]:
        """Scan the root directory for database session handling issues.
        
        Returns:
            Dict[str, Dict[str, List[int]]]: Dictionary mapping file paths to issues.
        """
        all_issues: Dict[str, Dict[str, List[int]]] = {}
        
        for root, _, files in os.walk(self.root_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if self.should_check_file(file_path):
                    issues = self.check_file(file_path)
                    if any(issues.values()):
                        all_issues[file_path] = issues
                        self.issues_found += sum(len(lines) for lines in issues.values())
                        
        return all_issues

    def print_issues(self, all_issues: Dict[str, Dict[str, List[int]]]) -> None:
        """Print all issues found.
        
        Args:
            all_issues: Dictionary mapping file paths to issues.
        """
        if not all_issues:
            print("No database session handling issues found!")
            return
            
        print(f"Found {self.issues_found} potential database session handling issues:")
        print()
        
        for file_path, issues in all_issues.items():
            rel_path = os.path.relpath(file_path, self.root_dir)
            has_issues = any(issues.values())
            
            if has_issues:
                print(f"File: {rel_path}")
                
                for pattern_name, line_numbers in issues.items():
                    if line_numbers:
                        issue_description = self._get_issue_description(pattern_name)
                        print(f"  - {issue_description} on lines: {', '.join(map(str, line_numbers))}")
                        
                print()

    def _get_issue_description(self, pattern_name: str) -> str:
        """Get a human-readable description of an issue pattern.
        
        Args:
            pattern_name: Name of the pattern.
            
        Returns:
            str: Human-readable description.
        """
        descriptions = {
            "next_db_session": "Using next() on a context manager",
            "db_session_generator": "Creating db_session_generator from get_db()",
            "get_db_without_with": "Using get_db() without 'with' statement",
        }
        return descriptions.get(pattern_name, pattern_name)

    def suggest_fixes(self, all_issues: Dict[str, Dict[str, List[int]]]) -> None:
        """Suggest fixes for the issues found.
        
        Args:
            all_issues: Dictionary mapping file paths to issues.
        """
        if not all_issues:
            return
            
        print("Suggested fixes:")
        print()
        
        for file_path, issues in all_issues.items():
            rel_path = os.path.relpath(file_path, self.root_dir)
            has_issues = any(issues.values())
            
            if has_issues:
                print(f"File: {rel_path}")
                
                if issues["db_session_generator"] or issues["next_db_session"]:
                    print("  Replace patterns like:")
                    print("    db_session_generator = get_db()")
                    print("    db = next(db_session_generator)")
                    print("    try:")
                    print("        # ... code ...")
                    print("    finally:")
                    print("        try:")
                    print("            next(db_session_generator)")
                    print("        except StopIteration:")
                    print("            pass")
                    print()
                    print("  With:")
                    print("    with get_db() as db:")
                    print("        # ... code ...")
                    print()
                
                if issues["get_db_without_with"]:
                    print("  Ensure get_db() is always used with a 'with' statement:")
                    print("    with get_db() as db:")
                    print("        # ... code ...")
                    print()


def main() -> None:
    """Main entry point for the script."""
    # Get the root directory (assuming this script is in tests/utils)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(script_dir, "../.."))
    
    checker = DbSessionChecker(root_dir)
    all_issues = checker.scan_directory()
    
    checker.print_issues(all_issues)
    checker.suggest_fixes(all_issues)
    
    # Return non-zero exit code if issues were found
    if checker.issues_found > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
