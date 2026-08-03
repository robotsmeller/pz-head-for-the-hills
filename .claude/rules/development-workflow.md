# Development Workflow Rules

**DO NOT REMOVE** - These rules define how we develop and maintain this project together.

## Core Principles

1. **You direct, Claude builds**: You set priorities and make decisions, I implement and maintain
2. **GitHub Issues for tracking**: Non-trivial features, bugs, and tasks go in GitHub Issues
3. **Privacy first**: Never commit PII, credentials, or sensitive data
4. **Test before claiming done**: Verify in a live PZ instance (via pz-test-pilot, or manually) before reporting a change works
5. **Incremental progress**: Small commits, clear descriptions
6. **Do it right, not right now**: Don't defer work that will need to be done anyway

## Branch Strategy

Solo mod project, no staging/deploy pipeline. Matches the other `pz-*` repos under this account.

- `main` - always in a loadable state (mod.info valid, no syntax errors)
- Direct commits to `main` are fine for normal work
- Use a short-lived branch + PR only for a change big enough that you want a diff to review before it lands

## Commit Messages

Format:
```
Short description of change

- Detail 1
- Detail 2

Fixes #123
```

**No `Co-Authored-By` / AI-attribution trailer, ever, in this repo.** Standing rule across this user's projects: AI involvement stays off the public record. Do not add it even if a default harness behavior would.

### Auto-Close Issues in Commits

- `Fixes #123` / `Closes #123` / `Resolves #123` - closes the issue when the commit lands on `main`

No emojis. No "Generated with Claude Code" footer.

## Destructive Actions

**Always require confirmation before:**
- Deleting files or directories
- Force pushing to any branch
- Resetting git history
- Bulk updates/deletes
- Editing a live save under `Zomboid/Saves/` or overwriting installed mods under `Zomboid/mods/`

## Before Every Commit

- [ ] No credentials or PII in changed files
- [ ] Changes match the task scope
- [ ] `mod.info` present and identical in both `mod/` and `mod/42/` if either changed (B42 silently rejects a mod missing the versioned copy — see CLAUDE.md)
- [ ] Tested in a live PZ instance where applicable

## Before Every Push

- [ ] Review `git diff` for sensitive data
- [ ] `.gitignore` excludes anything that shouldn't be public (this repo is public)

## GitHub Issues

```bash
gh issue list --state open
gh issue create --title "Title" --body "Description" --label "enhancement"
# Prefer closing via commit message ("Fixes #123") over a manual gh issue close
```

## Session Handoff

Use the global `/handoff` skill. It folds session state into `.claude/context.md` (the single handoff file for this repo — no separate `HANDOFF.md`). Don't hand-roll a handoff outside that skill.

---

*These rules evolve as we work together. Update as needed.*
