# Repository agent instructions

## Environment and dependencies

- Treat `requirements.txt` as the authoritative dependency manifest. Add every new runtime
  dependency there before relying on it.
- Run repository Python scripts and checks with the local virtual environment. On Windows use
  `.venv\\Scripts\\python.exe`; do not use a system interpreter.

## Plan-driven work

When starting work from a plan:

1. Ask the user which plan task they want to start with before implementation.
2. Inspect the current implementation and dependencies to verify that task is unblocked. If an
   assumption in the plan or user request is incorrect, say so with evidence, and recommend the
   task that should start instead.
3. As each task completes, report what was completed and its position in the overall plan before
   moving to the next task.
