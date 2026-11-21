# Agentic runs — opus-5.5-cc-vs-glm-5.3 · run 20261121T034210Z

The model works on a copy of the project inside a sandbox with an agent (Claude Code for Claude models, opencode for open-weight models): edit, build, test, fix, until its `/goal` is met or the time limit is hit; what it delivered is then scored by the case's acceptance check, including hidden tests it never saw. Infra errors (the session never ran) are left out.

## Summary

| Case | Model | Effort | Passed | Mean time (min) | Mean cost (USD) | Mean turns |
|---|---|---|---:|---:|---:|---:|
| r8_shogun_rust | GLM-5.3 · opencode | high | 0/1 | 163.4 | $31.57 | 344 |

## Per attempt

| Case | Rep | Model | Result | Time (min) | Cost (USD) | Turns | Tool calls | Files | Reason |
|---|---:|---|---|---:|---:|---:|---:|---:|---|
| r8_shogun_rust | 1 | GLM-5.3 · opencode | ❌ | 163.4 | $31.57 | 344 | 346 | 15 | failed checks: crud, permissions, queries, database |
