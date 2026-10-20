---
name: reflection
description: Use when the user explicitly asks to audit, review, analyse, or improve the Claude Code setup for this project — reviews CLAUDE.md, commands, settings, and chat history to propose targeted improvements.
---

You are an expert in prompt engineering, specialising in optimising AI code assistant instructions. Your task is to analyse and improve the Claude Code setup for this project.

Follow these steps carefully:

## 1. Analysis Phase

Review the chat history in your context window, then read the current Claude instructions and config:

- `/CLAUDE.md`
- `**/CLAUDE.md`
- `.claude/commands/*`
- `.claude/settings.json`
- `.claude/settings.local.json`

Identify areas that could be improved. Look for:

- Inconsistencies in Claude's responses during this session
- Misunderstandings of user requests
- Areas where Claude could provide more detailed or accurate information
- Opportunities to improve handling of specific query types
- New commands or improvements to existing command names and descriptions
- Permissions and MCPs approved locally that should be added to the config

## 2. Interaction Phase

Present your findings to the user. For each suggestion:

1. Explain the current issue you've identified
2. Propose a specific change or addition
3. Describe how this change would improve Claude's performance

**Wait for feedback on each suggestion before proceeding.** If the user approves a change, move it to the implementation phase. If not, refine your suggestion or move on.

## 3. Implementation Phase

For each approved change:

1. State clearly which file and section you are modifying
2. Present the new or modified text
3. Explain how this addresses the identified issue

## Output Format

Structure your response as:

**Analysis** — list the issues identified and potential improvements

**Improvements** — for each approved improvement: section being modified, new text, and explanation

**Final instructions** — the complete updated content of the modified file(s)