# Development instructions

For full-stack Agent development and this rewrite, read and apply `.agent/skills/agent-fullstack-ddd/SKILL.md` and its task reference. For Pydantic AI code, also read `.agent/skills/building-pydantic-ai-agents/SKILL.md` and only the references needed for the current change. The `.agent` location is intentional and requested by the user.

Keep domain rules independent of FastAPI, SQLModel and Pydantic AI. Keep repository, unit of work and service responsibilities explicit. Preserve existing users, provider secrets, document ownership, conversation history and Alembic history during migration. Do not push, deploy or call paid models without task-specific authorization.
