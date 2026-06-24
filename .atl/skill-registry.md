# Skill Registry

Project: momentum-v2
Generated: 2026-06-05

## Registry Contract

This file is an index only. `SKILL.md` remains the source of truth.

## Project Skills

| Name | Trigger / Description | Scope | Path |
| --- | --- | --- | --- |
| interface-design | This skill is for interface design — dashboards, admin panels, apps, tools, and interactive products. NOT for marketing design (landing pages, marketing sites, campaigns). | project | `/home/marcos/trade/momentum-v2/.agents/skills/interface-design/SKILL.md` |

## User Skills

| Name | Trigger / Description | Scope | Path |
| --- | --- | --- | --- |
| branch-pr | Create Gentle AI pull requests with issue-first checks. Trigger: creating, opening, or preparing PRs for review. | user | `/home/marcos/.config/opencode/skills/branch-pr/SKILL.md` |
| chained-pr | Trigger: PRs over 400 lines, stacked PRs, review slices. Split oversized changes into chained PRs that protect review focus. | user | `/home/marcos/.config/opencode/skills/chained-pr/SKILL.md` |
| cognitive-doc-design | Design docs that reduce cognitive load. Trigger: writing guides, READMEs, RFCs, onboarding, architecture, or review-facing docs. | user | `/home/marcos/.config/opencode/skills/cognitive-doc-design/SKILL.md` |
| comment-writer | Write warm, direct collaboration comments. Trigger: PR feedback, issue replies, reviews, Slack messages, or GitHub comments. | user | `/home/marcos/.config/opencode/skills/comment-writer/SKILL.md` |
| go-testing | Trigger: Go tests, go test coverage, Bubbletea teatest, golden files. Apply focused Go testing patterns. | user | `/home/marcos/.config/opencode/skills/go-testing/SKILL.md` |
| issue-creation | Create Gentle AI issues with issue-first checks. Trigger: creating GitHub issues, bug reports, or feature requests. | user | `/home/marcos/.config/opencode/skills/issue-creation/SKILL.md` |
| judgment-day | Trigger: judgment day, dual review, adversarial review, juzgar. Run blind dual review, fix confirmed issues, then re-judge. | user | `/home/marcos/.config/opencode/skills/judgment-day/SKILL.md` |
| sdd-archive | Archive a completed SDD change by syncing delta specs. Trigger: orchestrator launches archive after implementation and verification. | user | `/home/marcos/.config/opencode/skills/sdd-archive/SKILL.md` |
| sdd-apply | Implement SDD tasks from specs and design. Trigger: orchestrator launches apply for one or more change tasks. | user | `/home/marcos/.config/opencode/skills/sdd-apply/SKILL.md` |
| sdd-design | Create the SDD technical design and architecture approach. Trigger: orchestrator launches design for a change. | user | `/home/marcos/.config/opencode/skills/sdd-design/SKILL.md` |
| sdd-explore | Explore SDD ideas before committing to a change. Trigger: orchestrator launches exploration or requirement clarification. | user | `/home/marcos/.config/opencode/skills/sdd-explore/SKILL.md` |
| sdd-onboard | Walk users through the SDD workflow on the real codebase. Trigger: orchestrator launches onboarding for the full SDD cycle. | user | `/home/marcos/.config/opencode/skills/sdd-onboard/SKILL.md` |
| sdd-propose | Create an SDD change proposal with intent, scope, and approach. Trigger: orchestrator launches proposal work for a change. | user | `/home/marcos/.config/opencode/skills/sdd-propose/SKILL.md` |
| sdd-spec | Write SDD delta specs with requirements and scenarios. Trigger: orchestrator launches spec work for a change. | user | `/home/marcos/.config/opencode/skills/sdd-spec/SKILL.md` |
| sdd-tasks | Break an SDD change into implementation tasks. Trigger: orchestrator launches task planning for a change. | user | `/home/marcos/.config/opencode/skills/sdd-tasks/SKILL.md` |
| sdd-verify | Trigger: SDD verification phase, verify change. Execute tests and prove implementation matches specs, design, and tasks. | user | `/home/marcos/.config/opencode/skills/sdd-verify/SKILL.md` |
| skill-creator | Trigger: new skills, agent instructions, documenting AI usage patterns. Create LLM-first skills with valid frontmatter. | user | `/home/marcos/.config/opencode/skills/skill-creator/SKILL.md` |
| skill-improver | Trigger: improve skills, audit skills, refactor skills, skill quality. Audit and upgrade existing LLM-first skills. | user | `/home/marcos/.config/opencode/skills/skill-improver/SKILL.md` |
| skill-registry | Trigger: update skills, skill registry, actualizar skills, after skill changes. Index available skills by trigger and path. | user | `/home/marcos/.config/opencode/skills/skill-registry/SKILL.md` |
| work-unit-commits | Plan commits as reviewable work units. Trigger: implementation, commit splitting, chained PRs, or keeping tests and docs with code. | user | `/home/marcos/.config/opencode/skills/work-unit-commits/SKILL.md` |

## Project Conventions

| File | Notes |
| --- | --- |
| `/home/marcos/trade/momentum-v2/AGENTS.md` | Source repo operating rules, stack constraints, and ticket workflow. |
| `/home/marcos/trade/momentum-v2/Makefile` | `make start` / `make finish` shortcuts for issue-driven flow. |
| `/home/marcos/trade/momentum-v2/.gitignore` | Ignores `.atl/`, data, outputs, models, caches, and Playwright artifacts. |

## Skips / Duplicates

- Skipped `_shared` and all `sdd-*` skills per registry rules.
- No duplicate skill names found.
