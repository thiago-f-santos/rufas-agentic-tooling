# RuFaS Agentic Tooling - Agent Guidelines

## Directives
- **Zero Assumptions**: Never assume ambiguous parameters or simulation logic; verify or ask.
- **Semantic Commits**: Always format commits following Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
- **Branching Workflow**: Always branch from `main` for any new task (e.g. `feat/`, `fix/`) unless explicitly instructed otherwise.
- **RuFaS Boundary Containment**: Never search or access files outside `<rufas_root>` or `rufas-agentic-tooling` autonomously. Always ask explicit confirmation before accessing external directories or repos.
- **Ground Truth & Context Grounding**: Use `<rufas_root>/RUFAS/` Python code and `<rufas_root>/input/metadata/` as the single source of truth for all simulation mechanics, equations, schemas, and cross-validation rules.
- **Scoped Tooling Execution**: Explicitly pass directory paths in `grep_search`, `find_by_name`, `codegraph_explore`, and shell commands. Never run unscoped searches across parent or sibling directories.
- **Subagent Context Propagation**: Always pass resolved `rufas_root` and boundary rules to child subagents spawned via `invoke_subagent`.
- **Token Efficiency**: Use `rtk` prefix for CLI commands to optimize token consumption.
- **Skill Usage**: Consult `skills/rufas/SKILL.md` before analyzing, modifying, or executing RuFaS simulations.
