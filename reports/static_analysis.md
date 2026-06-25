# Static Analysis Report

Generated findings should be summarized here after each review cycle.

Current gate:

- `scripts/static_analysis.sh` runs `cppcheck` when available.
- `scripts/static_analysis.sh` runs `clang-tidy` when `build-host/compile_commands.json` exists.
