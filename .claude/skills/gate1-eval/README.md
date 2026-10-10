# gate1-eval skill

Agent instructions for running and checking Gate 1 (see `SKILL.md`). It lives in
the repo so it changes together with the harness and is reviewed in PRs.

## Using it with each agent

| Agent | Setup |
|---|---|
| **Claude Code** | None: it loads `.claude/skills/` from the repo automatically. |
| **OpenClaw** | Add this repo's skill folder to `skills.load.extraDirs` in `~/.openclaw/openclaw.json` (see below). `git pull` then keeps it current. |
| **opencode** | Point it at `.claude/skills/gate1-eval/SKILL.md` (skills setting or `AGENTS.md`), or ask it to read that file first. |

OpenClaw config:

```json
{
  "skills": {
    "load": {
      "extraDirs": ["/path/to/your/clone/.claude/skills"]
    }
  }
}
```

OpenClaw finds any `SKILL.md` under that folder. Copying the folder into
`~/.openclaw/skills/` also works, but the copy goes stale when the repo changes.
Docs: https://docs.openclaw.ai/tools/skills
