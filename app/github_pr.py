import os
from github import Github
import requests
import pathlib, tempfile, subprocess, shutil

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
if not GITHUB_TOKEN:
    raise RuntimeError('Set GITHUB_TOKEN env var to enable PR creation helper')

def create_pr_from_local(repo_clone_dir, base_branch='main', pr_branch=None, title='son-of-anton: automated patch', body='Automated patch created by Son of Anton'):
    # repo_clone_dir: path to a local repo with changes already committed on a branch
    repo_clone_dir = pathlib.Path(repo_clone_dir)
    # discover remote origin
    res = subprocess.run('git config --get remote.origin.url', cwd=repo_clone_dir, shell=True, capture_output=True, text=True)
    origin = res.stdout.strip()
    if not origin:
        raise RuntimeError('No origin found in local repo')
    # convert origin to API repo format if it's github.com
    if origin.startswith('https://github.com/'):
        parts = origin.replace('https://github.com/', '').rstrip('.git')
        owner_repo = parts
    else:
        raise RuntimeError('Only https GitHub remotes supported in helper')

    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(owner_repo)
    # find branch
    branch = pr_branch or subprocess.run('git rev-parse --abbrev-ref HEAD', cwd=repo_clone_dir, shell=True, capture_output=True, text=True).stdout.strip()
    # push branch with token auth
    # Note: user should set remote origin to include token or use gh cli; this helper assumes push already done.
    pr = repo.create_pull(title=title, body=body, head=branch, base=base_branch)
    return pr.html_url
