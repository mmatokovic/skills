# Skill Authoring Guide

Use this guide when adding or updating skills so the repository stays consistent.

Skills follow the [Agent Skills specification](https://agentskills.io/specification). Where this guide and the spec disagree, the spec wins.

## Goals

- Keep each skill focused on one job and easy to discover.
- Make each skill usable on its own without requiring the full repo.
- Prefer verified, source-backed behavior over guesses.
- Keep file structure, tone, and metadata consistent.

## Repository Model

Skills live in a flat `skills/` directory. Hooks and other non-skill plugins live in `plugins/`. The marketplace groups skills into installable plugins.

```text
.
├── .claude-plugin/marketplace.json   # plugin catalog
├── plugins/<plugin-name>/            # self-contained plugins (hooks, commands)
└── skills/<skill-name>/
    ├── SKILL.md                      # required entry point
    ├── references/                   # optional: detail loaded on demand
    ├── assets/                       # optional: templates, catalogs, data
    └── scripts/                      # optional: executable helpers
```

## SKILL.md Front Matter

Every `SKILL.md` must start with YAML front matter containing `name` and `description`. Installers and Claude use these fields to discover the skill.

```markdown
---
name: spring-boot
description: Use when writing, reviewing, debugging, or setting up any Java backend service. Covers REST controllers, JPA, Spring Batch, and tests.
---
```

- `name` matches the folder name: lowercase, hyphen-separated.
- `description` says what the skill does **and when to use it**. Include the trigger phrases a user would actually type. This is the only part Claude sees before loading the skill, so it decides whether the skill fires.

## Path and Naming

- One skill per folder under `skills/`; folder name equals `name`.
- Use short, stable, descriptive names in lowercase with hyphens.
- Keep one primary topic per reference file, e.g. `references/jpa-patterns.md`.

## Writing Standards

- Lead with what the skill helps the reader do.
- Keep `SKILL.md` lean: workflow, routing, and key rules. Move long detail into `references/` and link to it from `SKILL.md` with a note on when to read it.
- Use short sections and concrete, realistic examples.
- Explain why a rule matters when it affects safety, correctness, or performance.
- Avoid filler, speculation, and repeated background material.

## Research and Safety

- Verify exact command names, flags, package names, and parameters.
- Distinguish documented behavior from inference; omit or mark anything unverified.
- Do not include secrets, internal credentials, or hostnames that should not be shared.
- For destructive operations, prefer safe workflows and pre-flight checks.
- List sources in a `## Sources` section where the skill relies on external documentation.

## Required Follow-Through

When adding, moving, or renaming a skill:

1. Add or update its path in the matching plugin's `skills` array in `.claude-plugin/marketplace.json`.
2. Update the plugin table and layout in `README.md`.
3. Check for stale links and old paths across the repo.
4. Validate the marketplace: `claude plugin validate .`

## Review Checklist

- Folder name and front matter `name` match.
- `description` states what and when, with trigger phrases.
- Referenced files under `references/`, `assets/`, `scripts/` exist.
- Examples use valid syntax and terminology.
- The skill is listed in `marketplace.json` and `README.md`.
