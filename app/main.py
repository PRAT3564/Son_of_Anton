from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess, tempfile, os, shutil, uuid, json, pathlib, time, re
from typing import Optional
import openai

app = FastAPI(title="Son of Anton - AI Code Reviewer")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Set OPENAI_API_KEY in environment variables")

openai.api_key = OPENAI_API_KEY


class ReviewRequest(BaseModel):
    repo_url: str
    branch: Optional[str] = "main"
    path: Optional[str] = None
    ask_to_fix: bool = False
    max_file_bytes: int = 20000


class ApplyRequest(BaseModel):
    repo_url: str
    base_branch: Optional[str] = "main"
    branch_name: Optional[str] = None
    patch: str
    force_apply: bool = False


def run_cmd(cmd, cwd=None, timeout=60):
    completed = subprocess.run(
        cmd, cwd=cwd, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout
    )
    return completed.returncode, completed.stdout, completed.stderr


def clone_repo(repo_url, branch="main"):
    tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="son-of-anton-"))
    cmd = f"git clone --depth 1 --branch {branch} {repo_url} {tmpdir}"
    code, out, err = run_cmd(cmd, timeout=90)
    if code != 0:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise RuntimeError(f"Git clone failed: {err}")
    return tmpdir


def collect_files(repo_dir, path=None, max_file_bytes=20000):
    repo_dir = pathlib.Path(repo_dir)
    paths = []
    if path:
        target = repo_dir / path
        if target.is_file():
            paths.append(target)
        else:
            paths += list(target.rglob("*"))
    else:
        paths += list(repo_dir.glob("**/*.py")) + list(repo_dir.glob("**/*.js"))

    files = []
    for p in paths:
        if p.is_file() and p.stat().st_size <= max_file_bytes:
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                files.append({"path": str(p.relative_to(repo_dir)), "content": content})
            except Exception:
                pass
    return files


def run_linters(repo_dir):
    results = {}
    code, out, err = run_cmd("pytest -q", cwd=repo_dir, timeout=120)
    results["pytest"] = {"code": code, "stdout": out, "stderr": err}
    code, out, err = run_cmd("flake8 --version", cwd=repo_dir, timeout=10)
    if code == 0:
        code2, out2, err2 = run_cmd("flake8", cwd=repo_dir, timeout=60)
        results["flake8"] = {"code": code2, "stdout": out2, "stderr": err2}
    else:
        results["flake8"] = {"code": None, "stdout": "", "stderr": "flake8 not installed"}
    return results


def ask_model_for_review(files, ask_patch=False):
    system = (
        "You are an expert senior developer. "
        "You must output TWO blocks:\n"
        "1. A JSON code review object in ```json``` fences.\n"
        "2. If a patch is requested, a unified diff in ```diff``` fences.\n"
        "Never include text outside these blocks."
    )

    file_chunks = []
    for f in files:
        file_chunks.append(f"// FILE: {f['path']}\n{f['content']}")
    files_text = "\n\n---\n\n".join(file_chunks)[:200000]

    user_prompt = f"""
Review this code and find problems, improvements, and possible bug fixes.
Also generate a unified diff patch if asked.

FILES:
{files_text}

Return:
```json
{{"summary":"...", "issues":[{{"path":"...","line":123,"severity":"medium","message":"..."}}]}}
```
If patch requested, then:
```diff
--- file
+++ file
@@ -1 +1 @@
changes here
```
"""

    resp = openai.ChatCompletion.create(
        model=OPENAI_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user_prompt}],
        temperature=0.1,
        max_tokens=3000
    )

    return resp["choices"][0]["message"]["content"]


@app.post("/review")
def review(req: ReviewRequest):
    tmp = None
    try:
        tmp = clone_repo(req.repo_url, req.branch)
        files = collect_files(tmp, req.path, req.max_file_bytes)
        linters = run_linters(tmp)
        raw_response = ask_model_for_review(files, req.ask_to_fix)

        json_block = None
        diff_block = None
        m_json = re.search(r"```json\s*(\{.*?\})\s*```", raw_response, re.S)
        if m_json:
            json_block = m_json.group(1)
        m_diff = re.search(r"```diff\s*(---.*?)(?:```|$)", raw_response, re.S)
        if m_diff:
            diff_block = m_diff.group(1)

        return {
            "review_json": json_block,
            "patch": diff_block,
            "lint_results": linters
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


@app.post("/apply")
def apply_patch(req: ApplyRequest):
    if not req.force_apply:
        raise HTTPException(status_code=400, detail="force_apply=true required for safety")

    tmp = None
    try:
        tmp = clone_repo(req.repo_url, req.base_branch)
        branch_name = req.branch_name or f"sonofanton-{uuid.uuid4().hex[:6]}"
        run_cmd(f"git checkout -b {branch_name}", cwd=tmp)

        patch_file = tmp / "patch.diff"
        patch_file.write_text(req.patch)
        code, out, err = run_cmd(f"git apply --index {patch_file}", cwd=tmp)
        if code != 0:
            raise RuntimeError(f"Patch failed: {err}")

        run_cmd('git commit -am "Son of Anton: applied AI patch"', cwd=tmp)
        return {"status": "Patch applied locally", "branch": branch_name}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
