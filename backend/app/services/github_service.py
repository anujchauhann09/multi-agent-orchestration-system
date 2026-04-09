from typing import Optional
from github import Github, GithubException
from app.core.settings import settings

_github = Github(settings.GITHUB_TOKEN)


def _parse_repo(repo_url: str):
    """Extract owner/repo from GitHub URL."""
    parts = repo_url.rstrip("/").split("/")
    return _github.get_repo(f"{parts[-2]}/{parts[-1]}")


def get_issue(issue_url: str) -> dict:
    """
    Fetch GitHub issue details — no LLM needed.
    Returns title, body, labels, number.
    """
    parts = issue_url.rstrip("/").split("/")
    issue_number = int(parts[-1])
    repo = _parse_repo("/".join(parts[:-2]))
    issue = repo.get_issue(issue_number)
    return {
        "number": issue.number,
        "title": issue.title,
        "body": issue.body or "",
        "labels": [l.name for l in issue.labels],
        "url": issue_url,
    }


def get_repo_files(repo_url: str, extensions: tuple = (".py",)) -> list[dict]:
    """
    Fetch all source files from repo — deterministic, no LLM.
    Returns list of {path, content}.
    """
    repo = _parse_repo(repo_url)
    files = []
    contents = repo.get_contents("")

    while contents:
        item = contents.pop(0)
        if item.type == "dir":
            contents.extend(repo.get_contents(item.path))
        elif item.path.endswith(extensions):
            try:
                files.append({
                    "path": item.path,
                    "content": item.decoded_content.decode("utf-8", errors="ignore"),
                })
            except Exception:
                continue

    return files


def create_pull_request(repo_url: str, branch: str, title: str, body: str, base: str = "main") -> str:
    """Create a PR and return its URL."""
    repo = _parse_repo(repo_url)
    pr = repo.create_pull(title=title, body=body, head=branch, base=base)
    return pr.html_url


def create_branch_and_commit(repo_url: str, branch: str, file_path: str, content: str, commit_message: str) -> None:
    """Create a branch and commit a file change."""
    repo = _parse_repo(repo_url)
    source = repo.get_branch("main")
    repo.create_git_ref(ref=f"refs/heads/{branch}", sha=source.commit.sha)

    try:
        existing = repo.get_contents(file_path, ref=branch)
        repo.update_file(file_path, commit_message, content, existing.sha, branch=branch)
    except GithubException:
        repo.create_file(file_path, commit_message, content, branch=branch)
