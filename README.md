# ENE-C2-064 — Renewable Energy Certificate Evidence Reconciliation Brief

> **Category**: Cat 2 (orchestrates multiple steps to accomplish a specific use case)
> **Industry**: ENE

## Overview

This agent reconciles renewable-energy certificate records from three sources and produces a
brief that a compliance or operations reviewer checks before a certificate audit or retirement
decision. It does not retire certificates, make market claims or attest compliance.

The caller sends one JSON document in the `input` string with three lists:
`registry_export` (certificate records from the registry), `generation_evidence` (metered
generation records) and `facility_master` (facility reference data). Records are keyed by
`facility_id`, `period` and `certificate_serial`.

The pipeline:

1. **Input validation** rejects credential-shaped strings and path-traversal sequences. It
   redacts owner and contact fields (names, e-mail addresses, phone numbers) in the facility
   master instead of rejecting them.
2. **Evidence extraction** normalizes the registry and evidence records into a canonical form.
3. **Reconciliation** is deterministic. An evidence record with no exact registry match becomes a
   mismatch (`id_mismatch` when the facility is unknown, otherwise `period_mismatch`). A
   certificate key that appears twice in the registry export becomes a `duplicate` exception.
4. **Brief rendering** produces a summary plus the cited mismatches and exceptions.
5. **Output validation** drops any entry whose source reference is not traceable to the input
   and fails the run if it had to drop anything.

An LLM client is optional. When one is configured it writes the summary text, and it is also
called during evidence extraction, although the reconciliation itself never depends on it.
Without an LLM, which is how the repository ships, the summary is a fixed sentence built from
the counts. Every result is computed deterministically either way.

This is an agent template built with the **AGENTIC STAR** development platform and the
**AgentCore Framework**. It is intended to be taken as a starting point: fork it, adapt it to
your own data and policies, and run it inside your own AGENTIC STAR deployment.

## Requirements

**This template does not run standalone.** It requires:

| Requirement | Notes |
|---|---|
| **AGENTIC STAR platform** | The agent connects to the platform at start-up. Without it, start-up fails immediately (see *Behaviour without the platform* below). Deployment guides and API documentation: [AGENTIC STAR Developers](https://developers.fd.agenticstar.tm.softbank.jp/) |
| **AgentCore Framework** (`agenticstar-agentcore`) | Installed from PyPI as a dependency. |
| Python | 3.11 or later |

```bash
pip install -e .
```

### Behaviour without the platform

The framework is designed to run **only** on AGENTIC STAR. There is no fallback or degraded
mode. If the platform is unreachable or the SDK version does not match, the agent raises
`PlatformRequired` during graph compile / start-up preflight rather than starting in a partially
working state. This is intentional — a half-running agent is worse than one that refuses to start.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Tests run without a platform connection. Running the agent itself does not.

## Project Structure

```
src/          agent implementation (nodes, services, schemas)
tests/        unit, integration and boundary tests
config/       agent configuration
docs/         design and test specification
```

See `docs/02_design.md` for the design and `docs/03_test_spec.md` for the test specification.

## Customising

1. Adjust `config/` for your own environment and policies.
2. Replace the knowledge sources and sample data with your own.
3. Review the node implementations under `src/nodes/` for domain-specific logic.
4. Re-run the test suite.

## License

MIT — see [LICENSE](LICENSE).

## Status of this repository

This template is published **as is**, by its individual author, under the MIT license. It carries
**no warranty and no support commitment**, and no organisation stands behind its behaviour or
fitness for any purpose. Issues and pull requests may or may not receive a response; that is at
the sole discretion of the repository owner.
