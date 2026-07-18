# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## MANDATORY: do not read other `.md` files

Most `.md` files in this repo are throwaway brainstorming/design notes and do **not** describe what is actually running. For **every** task, you MUST NOT read, open, `grep`, or otherwise inspect any `.md` file in the repo — the sole exception is this `CLAUDE.md`. Only read another `.md` file when the user explicitly names it or explicitly tells you to. This applies to all tasks, including searches, audits, and "read everything relevant" style requests: exclude `.md` files by default.

## What this is

A proof-of-concept PyPSA model of the Bangladesh power transmission grid (132/230/400 kV), built from raw Google Sheets exports. The repo turns spreadsheet data into a `pypsa.Network` and runs linear economic dispatch on it with HiGHS.


## Environment and dependencies

- Treat `requirements.txt` as the authoritative dependency manifest. Add every new runtime dependency there before relying on it.
- Run repository Python scripts and checks with the local virtual environment. On Windows use `.venv\Scripts\python.exe`; do not use a system interpreter.

## Plan-driven work

When starting work from a plan:

1. Ask the user which plan task they want to start with before implementation.
2. Inspect the current implementation and dependencies to verify that task is unblocked. If an assumption in the plan or user request is incorrect, say so with evidence, and recommend the task that should start instead.
3. As each task completes, report what was completed and its position in the overall plan before moving to the next task.
