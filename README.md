# mmatokovic Skills

A collection of practical, installable skills and plugins for Claude Code.

Skills follow the [Agent Skills specification](https://agentskills.io/specification).

## Installation

Install a single skill by appending its path to the repository name:

```bash
npx skills add mmatokovic/skills/skills/spring-boot
npx skills add mmatokovic/skills/skills/grilling
...
```

### Install in Claude Code

This repository ships as a Claude Code plugin marketplace (`.claude-plugin/marketplace.json`).

Register the marketplace, then install the plugins you need:

```bash
# Register this repo as a marketplace
/plugin marketplace add mmatokovic/skills

# Install one or more plugins
/plugin install code-guidelines@mmatokovic-skills
/plugin install magic-bean@mmatokovic-skills
/plugin install integration@mmatokovic-skills
/plugin install devops@mmatokovic-skills
/plugin install web-craft@mmatokovic-skills
/plugin install llm-wiki@mmatokovic-skills
/plugin install code-hooks@mmatokovic-skills
```

Already cloned the repo locally? Point the marketplace at the local path instead:

```bash
/plugin marketplace add ./
```

Browse and toggle installed plugins anytime with `/plugin`.

## Plugins

| Plugin | Contents |
|--------|----------|
| `code-guidelines` | `grilling`, `karpathy-guidelines`, `reflection` |
| `magic-bean` | `spring-boot` |
| `integration` | `webmethods-platform`, `webmethods-service`, `wireshark-analysis` — install with `magic-bean`, which `webmethods-service` builds on |
| `devops` | `observability`, `openshift-troubleshooter` |
| `web-craft` | `hugo-tailwind` |
| `llm-wiki` | `llm-wiki` — Karpathy-style Obsidian wiki maintained by the LLM (ingest, ask, lint, file) |
| `code-hooks` | Windows toast notifications for `Stop` and `Notification` hooks (see [plugins/code-hooks](plugins/code-hooks/README.md)) |

## Repository Layout

```text
.
├── .claude-plugin/
│   └── marketplace.json
├── plugins/
│   └── code-hooks/
├── skills/
│   ├── grilling/
│   ├── hugo-tailwind/
│   ├── karpathy-guidelines/
│   ├── llm-wiki/
│   ├── observability/
│   ├── openshift-troubleshooter/
│   ├── reflection/
│   ├── spring-boot/
│   ├── webmethods-platform/
│   ├── webmethods-service/
│   └── wireshark-analysis/
├── README.md
└── SKILL_AUTHORING_GUIDE.md
```

Each skill is a folder with a `SKILL.md` and optional `references/`, `assets/`, or `scripts/` subfolders. See [SKILL_AUTHORING_GUIDE.md](SKILL_AUTHORING_GUIDE.md) before adding or changing a skill.

## Author Information

[Mislav Matoković](https://github.com/mmatokovic)