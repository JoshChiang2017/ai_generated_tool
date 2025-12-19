#!/usr/bin/env python3
"""
Search for commits with specific messages across multiple Git/SVN repositories.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict

# Configuration
REPOSITORIES = [
    "D:\\work\\Grace\\code\\git2",
    "D:\\work\\Grace\\code\\g56\\trunk\\Board\\Nvidia\\ServerMultiBoardPkg",
    "D:\\work\\Grace\\code\\g56\\trunk\\Nvidia",
    "D:\\vera\\trunk\\Board\\Nvidia\\VeraMultiBoardPkg",
    "D:\\vera\\trunk\\Nvidia",
    "D:\\work\\Grace\\code\\old_repo\\svn_Grace_56",
    "D:\\work\\Grace\\code\\old_repo\\svn-Grace",
    "D:\\work\\Grace\\code\\old_repo\\svn-Jetson"
]

SVN_LOG_LIMIT = 200


def is_git_repo(path: str) -> bool:
    """Check if the path is a Git repository"""
    git_dir = os.path.join(path, '.git')
    return os.path.isdir(git_dir)


def is_svn_repo(path: str) -> bool:
    """Check if the path is an SVN repository"""
    svn_dir = os.path.join(path, '.svn')
    return os.path.isdir(svn_dir)


def search_git_commits(repo_path: str, search_terms: List[str]) -> List[Dict]:
    """Search for commits in a Git repository"""
    results = []
    
    try:
        # Use a unique separator to avoid conflicts
        # Build command with multiple --grep options (AND logic with --all-match)
        cmd = ['git', 'log', '--all']
        
        # Add --all-match to require all grep patterns to match (AND logic)
        if len(search_terms) > 1:
            cmd.append('--all-match')
        
        # Add each search term as a separate --grep option
        for term in search_terms:
            cmd.extend(['--grep', term])
        
        cmd.extend(['-i', '--pretty=format:COMMIT_START%n%H%n%an%n%ae%n%ad%nMSG_START%n%B%nCOMMIT_END', '--date=iso'])
        
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        if result.returncode == 0 and result.stdout.strip():
            # Split by COMMIT_START marker
            commits_raw = result.stdout.strip().split('COMMIT_START\n')
            
            for commit_block in commits_raw:
                if not commit_block.strip():
                    continue
                
                lines = commit_block.split('\n')
                if len(lines) < 5:
                    continue
                
                # Extract commit info
                commit_hash = lines[0].strip()
                author = lines[1].strip()
                email = lines[2].strip()
                date = lines[3].strip()
                
                # Find MSG_START and extract message
                msg_start_idx = -1
                for i, line in enumerate(lines):
                    if line.strip() == 'MSG_START':
                        msg_start_idx = i
                        break
                
                if msg_start_idx == -1:
                    continue
                
                # Get message lines (skip MSG_START and COMMIT_END)
                message_lines = []
                for i in range(msg_start_idx + 1, len(lines)):
                    if lines[i].strip() == 'COMMIT_END':
                        break
                    message_lines.append(lines[i])
                
                # Join message and strip trailing empty lines
                message = '\n'.join(message_lines).rstrip()
                
                if commit_hash and message:
                    results.append({
                        'hash': commit_hash,
                        'author': author,
                        'email': email,
                        'date': date,
                        'message': message
                    })
        
    except Exception as e:
        print(f"Warning: Error searching Git repo {repo_path}: {e}")
    
    return results


def search_svn_commits(repo_path: str, search_terms: List[str], log_limit: int = 100) -> List[Dict]:
    """Search for commits in an SVN repository"""
    results = []
    
    try:
        cmd = ['svn', 'log', '--xml', '-l', str(log_limit)]
        
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        if result.returncode != 0:
            # Check if it's a network error
            if result.stderr and ('Unable to connect' in result.stderr or 'E731001' in result.stderr or '無法識別這台主機' in result.stderr):
                print(f"Warning: Cannot connect to SVN server for {repo_path} - skipping")
            else:
                print(f"Warning: SVN log failed for {repo_path}: {result.stderr[:100]}")
            return results
        
        if result.stdout.strip():
            import xml.etree.ElementTree as ET
            root = ET.fromstring(result.stdout)
            
            # Convert all search terms to lowercase for case-insensitive search
            search_lower_list = [term.lower() for term in search_terms]
            
            for logentry in root.findall('logentry'):
                msg_elem = logentry.find('msg')
                message = msg_elem.text if msg_elem is not None and msg_elem.text else ''
                message_lower = message.lower()
                
                # Check if ALL search terms are present (AND logic)
                if all(term in message_lower for term in search_lower_list):
                    author_elem = logentry.find('author')
                    date_elem = logentry.find('date')
                    
                    results.append({
                        'revision': logentry.get('revision'),
                        'author': author_elem.text if author_elem is not None else 'Unknown',
                        'date': date_elem.text if date_elem is not None else 'Unknown',
                        'message': message
                    })
        
    except Exception as e:
        print(f"Warning: Error searching SVN repo {repo_path}: {e}")
    
    return results


def print_results(repo_path: str, repo_type: str, commits: List[Dict], verbose: bool = False, search_terms: List[str] = None):
    """Print search results for a repository"""
    if not commits:
        return
    
    print(f"")
    print(f"Repository: {repo_path}")
    if verbose:
        print(f"Type: {repo_type.upper()}")
        if search_terms and len(search_terms) > 1:
            print(f"Search terms: {', '.join(search_terms)}")
        print(f"Found {len(commits)} commit(s)")
    
    for i, commit in enumerate(commits, 1):
        if repo_type == 'git':
            print(f"  Hash:    {commit['hash'][:12]}...")
            print(f"  Author:  {commit['author']} <{commit['email']}>")
            print(f"  Date:    {commit['date']}")
        else:  # SVN
            print(f"  Revision: r{commit['revision']}")
            print(f"  Author:   {commit['author']}")
            print(f"  Date:     {commit['date']}")
        
        # Print message with preserved formatting
        message = commit['message']
        print(f"  Message:")
        for line in message.split('\n'):
            print(f"    {line}")
        print(f"")

def main():
    parser = argparse.ArgumentParser(
        description='Search for commits with specific messages across multiple Git/SVN repositories',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python search_commit_msg.py -s IBxxxx0001 -s "Bug fix"
  python search_commit_msg.py -s IBxxxx0001 -s Grace -s ACPI
        '''
    )
    
    parser.add_argument('-s', '--string', action='append', dest='search_strings', required=True,
                        help='Search term (can be specified multiple times for AND logic)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Show detailed information (hash/revision, author, date)')
    
    args = parser.parse_args()
    
    # Get search terms from -s options
    search_terms = args.search_strings
    
    if not REPOSITORIES:
        print("Error: No repositories configured")
        sys.exit(1)
    
    if args.verbose:
        if len(search_terms) == 1:
            print(f"Searching for: '{search_terms[0]}'")
        else:
            print(f"Searching for commits containing ALL of: {', '.join(repr(t) for t in search_terms)}")
        print(f"Repositories to search: {len(REPOSITORIES)}")
    
    total_commits = 0
    searched_repos = 0
    skipped_repos = 0
    
    for repo_path in REPOSITORIES:
        if args.verbose:
            print(f"Searching: {repo_path}")
        
        if not os.path.isdir(repo_path):
            print(f"Skipping (not found): {repo_path}")
            skipped_repos += 1
            continue
        
        repo_type = None
        commits = []
        
        if is_git_repo(repo_path):
            repo_type = 'git'
            commits = search_git_commits(repo_path, search_terms)
        elif is_svn_repo(repo_path):
            repo_type = 'svn'
            commits = search_svn_commits(repo_path, search_terms, SVN_LOG_LIMIT)
        else:
            print(f"Skipping (not a Git/SVN repo): {repo_path}")
            skipped_repos += 1
            continue
        
        searched_repos += 1
        
        if commits:
            print_results(repo_path, repo_type, commits, args.verbose, search_terms)
            total_commits += len(commits)
    
    if args.verbose:
        print(f"\n{'='*80}")
        print(f"Search Summary:")
        print(f"  Repositories searched: {searched_repos}")
        print(f"  Repositories skipped:  {skipped_repos}")
        print(f"  Total commits found:   {total_commits}")
        print(f"{'='*80}")
    elif total_commits == 0:
        if len(search_terms) == 1:
            print(f"\nNot found: No commits matching '{search_terms[0]}' in any repository")
        else:
            print(f"\nNot found: No commits matching ALL of [{', '.join(repr(t) for t in search_terms)}] in any repository")


if __name__ == '__main__':
    main()
