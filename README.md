# CASR

**Correction-Aware Selective Repair for Long-Horizon Coding Agents**

CASR studies how a coding agent should selectively repair historical work after a user amends, supersedes, or revokes a requirement, while preserving functionality that remains valid.

## Frozen scope

- Scenario: long-horizon coding agents.
- Approach: Harness + Verifier.
- Core modules: requirement state, execution provenance graph, dependency-aware selective repair, independent verification.
- Not in the current scope: DPO, agentic RL, GUI agents, or a general multi-agent framework.

The authoritative V1.0 documents are preserved in [docs/research_problem.md](docs/research_problem.md) and [docs/experiment_plan.md](docs/experiment_plan.md).

## Current status

Milestone 2 is implemented as a runnable Harness + Verifier MVP: requirement versions, provenance graphs, Git artifact recovery, dependency-aware repair planning, isolated execution, and independent PASS/FAIL/UNKNOWN verification. The offline demo passes. Two saved synthetic studies cover policy comparison and provenance-fidelity ablation; no model API or real benchmark performance claim is made.

See [MVP_REPORT.md](MVP_REPORT.md) for the research question, measured results, limitations, and next experiment. Generated evidence is versioned under `results/offline_demo`, `results/mvp_experiment`, and `results/graph_ablation`.

## Environment

Validated on Windows 11 with Python 3.12, Git, and `uv`. Docker CLI is present, but the Docker daemon was not running during the audit. An NVIDIA RTX 4060 Laptop GPU with 8 GB VRAM is available; large local models and training are not required for the first prototype.

```bash
uv sync
uv run pytest
uv run python scripts/check_env.py

# Offline end-to-end selective-repair demo
uv run python scripts/demo_offline.py --output-dir results/offline_demo

# 3 cases x 3 repair policies
uv run python scripts/run_mvp_experiment.py \
  --config experiments/mvp_synthetic.json \
  --output-dir results/mvp_experiment

# 3 cases x 3 provenance-graph conditions
uv run python scripts/run_graph_ablation.py \
  --config experiments/graph_ablation.json \
  --output-dir results/graph_ablation
```

Copy `.env.example` to `.env` only when model access is needed. Never commit `.env` or credentials. The audit script reports credential presence only and never prints secret values.

## Layout

- `docs/`: research documents, audit reports, related work, and implementation plans.
- `src/casr/`: minimal Python package.
- `data/cases/`: versioned case specifications; large raw data stays untracked.
- `tests/`: automated unit and integration tests.
- `scripts/`: environment checks and reproducible command-line entry points.
- `configs/`: experiment configurations.
- `baselines/`, `experiments/`: baseline and CASR implementations.
- `results/`, `logs/`: generated artifacts, ignored by Git by default.

## Windows to cluster workflow

The cluster workflow is semi-automatic: the scripts prepare, synchronize, test, and collect artifacts, while a user confirms GPU resources and submits jobs in the Crater web UI. A 1 CPU / 2 GiB / 0 GPU Jupyter development job was used for a real offline smoke through the official web terminal; the platform-independent run passed and the job was stopped. SSH transport was reachable, but existing user-key authentication failed, so no SSH/SCP alias was configured.

```powershell
# One-command lightweight local test
uv run pytest -q

# Preview remote synchronization without connecting
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/local/sync.ps1 -DryRun

# After configuring the casr-cluster SSH alias and starting a development job
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/local/sync.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/local/smoke-test.ps1
```

See [docs/cluster_environment_report.md](docs/cluster_environment_report.md), [docs/network_diagnosis.md](docs/network_diagnosis.md), [docs/cluster_usage.md](docs/cluster_usage.md), and [docs/cluster_execution_record.md](docs/cluster_execution_record.md) for evidence, limitations, and exact next steps.

## Reproducibility rules

Every experiment must record its configuration, model identifier, prompts, tool trajectory, Git diffs, test outputs, token usage, and wall-clock time. Agent self-report is not accepted as verification evidence. `PASS`, `FAIL`, and `UNKNOWN` must remain distinct.

See [docs/milestone_1_report.md](docs/milestone_1_report.md) for measured environment details and [docs/superpowers/plans/2026-11-25-casr-m2-prototype.md](docs/superpowers/plans/2026-11-25-casr-m2-prototype.md) for the next implementation plan.
