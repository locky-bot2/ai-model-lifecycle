# Agentic runs — opus-5.5-cc-vs-glm-5.3 · run 20261120T140449Z

The model works on a copy of the project inside a sandbox with an agent (Claude Code for Claude models, opencode for open-weight models): edit, build, test, fix, until its `/goal` is met or the time limit is hit; what it delivered is then scored by the case's acceptance check, including hidden tests it never saw. Infra errors (the session never ran) are left out.

## Summary

| Case | Model | Effort | Passed | Mean time (min) | Mean cost (USD) | Mean turns |
|---|---|---|---:|---:|---:|---:|
| r8_shogun_rust | Claude Opus 5.5 (CC) | high | 1/1 | 154.0 | $26.29 | 192 |

## Per attempt

| Case | Rep | Model | Result | Time (min) | Cost (USD) | Turns | Tool calls | Files | Reason |
|---|---:|---|---|---:|---:|---:|---:|---:|---|
| r8_shogun_rust | 1 | Claude Opus 5.5 (CC) | ✅ | 154.0 | $26.29 | 192 | 178 | 32 |  |
