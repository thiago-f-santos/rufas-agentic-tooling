# RuFaS Agentic Tooling - Agent Guidelines

## Directives
- **Zero Assumptions**: Never assume ambiguous parameters or simulation logic; verify or ask.
- **Semantic Commits**: Always format commits following Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
- **Branching Workflow**: Always branch from `main` for any new task (e.g. `feat/`, `fix/`) unless explicitly instructed otherwise.
- **Context Grounding**: When inspecting or running RuFaS models, reference source schemas and cross-validation files in `RuFaS/input/metadata/`.
- **Token Efficiency**: Use `rtk` prefix for CLI commands to optimize token consumption.
- **Skill Usage**: Consult `skills/rufas-specialist/SKILL.md` before analyzing, modifying, or executing RuFaS simulations.
