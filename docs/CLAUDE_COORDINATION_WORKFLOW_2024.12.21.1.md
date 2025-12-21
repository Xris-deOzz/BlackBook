# Claude.ai and Claude Code Coordination Workflow

**Version**: 2024.12.21.1
**Purpose**: Prevent gaps and inconsistencies when using both Claude.ai and Claude Code on BlackBook

---

## The Problem

Claude.ai and Claude Code are separate tools with **no shared memory**:
- Claude.ai has project context, userMemories, and conversation history
- Claude Code starts fresh each session with no project context
- Neither can see what the other has done unless files are read

This can cause:
- Conflicting implementations
- Missed context or requirements
- Duplicate work
- Broken code from misunderstandings

---

## Coordination Rules

### Rule 1: One Tool Completes One Feature
Never split a feature between Claude.ai and Claude Code. One tool should own a feature from start to finish.

| Tool | Best For |
|------|----------|
| **Claude.ai** | Planning, architecture, documentation, multi-file coordinated changes, complex refactoring |
| **Claude Code** | Simple file edits, running tests, terminal commands, deployment, quick fixes |

### Rule 2: Git Commits as Checkpoints
Before switching tools, commit the current work:
```bash
git add -A
git commit -m "Checkpoint: [description of current state]"
git push
```

This ensures:
- Work is saved
- The other tool can see changes by reading files
- Rollback is possible if something breaks

### Rule 3: Work Summaries in docs/
When Claude Code completes work, it should create/update a summary file:

**Location**: `docs/WORK_SUMMARY_YYYY.MM.DD.md`

**Format**:
```markdown
# Work Summary - YYYY.MM.DD

## Session: [Time]
**Tool**: Claude Code
**Task**: [What was done]

### Files Modified
- `path/to/file.py` - [what changed]
- `path/to/other.py` - [what changed]

### Key Decisions
- [Any design decisions made]
- [Any deviations from plan]

### Status
- [x] Task completed
- [ ] Needs review by Claude.ai

### Notes for Claude.ai
[Any context the other Claude needs to know]
```

### Rule 4: Read Before Writing
Before making changes, both tools should:
1. Read relevant docs in `docs/` folder
2. Check recent git commits: `git log --oneline -10`
3. Read the specific files being modified

### Rule 5: Reference Existing Patterns
Both tools should follow existing code patterns. When in doubt:
- Look at similar existing code
- Check `docs/` for architectural decisions
- Ask Christopher for clarification

---

## Workflow Example

### Scenario: Implementing Tag Subcategory Feature

**Phase 1 (Claude.ai)**:
1. Discuss requirements with Christopher
2. Create planning docs: `docs/TAG_SUBCATEGORY_MAPPING.md`
3. Create task list: `docs/TAG_SUBCATEGORY_TASKS.md`
4. Commit: `git commit -m "Add tag subcategory planning docs"`

**Phase 2 (Claude.ai)**:
1. Implement model changes
2. Update migration
3. Test locally
4. Commit: `git commit -m "Implement tag subcategory model and migration"`

**Phase 3 (Claude Code - if needed)**:
1. Read `docs/TAG_SUBCATEGORY_TASKS.md`
2. Run deployment commands
3. Test on Synology
4. Write summary: `docs/WORK_SUMMARY_2024.12.21.md`
5. Commit: `git commit -m "Deploy tag subcategory feature to Synology"`

**Phase 4 (Claude.ai)**:
1. Read Claude Code's work summary
2. Update task checklist
3. Continue with next feature

---

## Quick Reference

### Starting a New Session

**Claude.ai**:
- Has project memory automatically
- Read any recent `docs/WORK_SUMMARY_*.md` files
- Check task lists for current status

**Claude Code**:
- READ `docs/` folder first
- Check `git log` for recent changes
- Ask Christopher for context if unclear

### Handing Off Work

**From Claude.ai to Claude Code**:
1. Commit all changes
2. Update task checklist with clear instructions
3. Note any gotchas or special considerations

**From Claude Code to Claude.ai**:
1. Commit all changes
2. Write work summary in `docs/WORK_SUMMARY_*.md`
3. Update task checklist marking completed items

---

## Files to Always Check

| File | Purpose |
|------|---------|
| `docs/WORK_SUMMARY_*.md` | Recent work by either tool |
| `docs/*_TASKS_*.md` | Current task lists |
| `README.md` | Project overview |
| `alembic/versions/` | Database migrations |
| `.env.local` / `.env` | Environment configuration |

