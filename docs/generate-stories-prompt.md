# Story Generator for Qwen Town

You are generating stories for the Qwen Town PRD (prd.json). Each story is a task
for an AI (Qwen 3.5:35b) to implement by writing Python code that passes pytest tests.

## Current Stack
- Backend: Python 3.11+, FastAPI, SQLAlchemy 2.0, SQLite/Postgres
- Templates: Jinja2 + HTMX + Tailwind CSS
- Tests: pytest
- All state in SQLite. No global variables.
- Models in engine/models.py. Simulation in engine/simulation.py.
- Routers in engine/routers/. Templates in engine/templates/.

## Story Format
```json
{
  "id": "NNN",
  "title": "Short imperative title (what to build)",
  "description": "2-4 sentences. Be SPECIFIC about what functions/endpoints/models to create. Name exact files. Describe exact behavior.",
  "acceptance": "What 'done' looks like. Reference specific test assertions.",
  "test_file": "tests/test_something.py",
  "context_files": ["engine/models.py", "engine/simulation.py"],
  "tags": ["simulation", "economy"],
  "priority": N,
  "status": "pending",
  "attempts": 0
}
```

## Rules for Good Stories
1. ONE concept per story. If it takes more than one sentence to describe, split it.
2. Description must name exact files to create/modify.
3. context_files should include ONLY files Qwen needs to see (keep small).
4. Each story must be testable with a pytest file.
5. Stories build on each other — reference prior stories' outputs.
6. Complexity comes from INTERACTION between systems, not from any single story.
7. Tags should match docs/index.json entries for auto-discovery.

## Test File Format
Write the test file too. Tests should:
- Import from engine modules
- Use the `db` fixture from conftest.py for database tests
- Use the `client` fixture for API tests
- Use the `admin_key` fixture for admin endpoint tests
- Assert specific, measurable outcomes (counts, values, states)
- Be simple enough that a 35B model can understand what's expected

## What's Already Built
[Paste the current prd.json here, or list completed stories]

## What I Want Next
[Describe the complexity/features you want to add]

## Generate
Create 5-10 new stories with incrementing IDs and priorities.
For each story, also generate the corresponding test file contents.
Output as valid JSON that can be appended to the prd.json stories array.
