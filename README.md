# 🧠 Son of Anton - AI Code Reviewer

> Inspired by Gilfoyle's masterpiece from *Silicon Valley*.

---

## ⚙️ Features
- Reviews GitHub or local repos
- Suggests bug fixes and improvements
- Optionally generates patches (diffs)
- Runs basic linting and testing
- Safe mode by default — requires `force_apply=true` to make changes

---

## 🪄 Setup

```bash
git clone https://github.com/yourname/son-of-anton.git
cd son-of-anton
```

Create a `.env` file:
```
OPENAI_API_KEY=your_api_key_here
GITHUB_TOKEN=ghp_xxx   # optional, for PR creation script
```

Build & run:
```bash
docker compose up --build
```

Access at → http://localhost:8000/docs

---

## 💬 Example API Call

### Review Code
```bash
curl -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/youruser/yourrepo.git","branch":"main","ask_to_fix":true}'
```

### Apply Patch
```bash
curl -X POST http://localhost:8000/apply \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/youruser/yourrepo.git","patch":"<PATCH_TEXT>","force_apply":true}'
```

