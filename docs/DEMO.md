# Demo Script

## Setup

1. Start API and web app.
2. Use a small local git repository with `README.md`, or use `examples/sample-repo`.
3. Paste the absolute repository path into the dashboard.
4. Click `Index`.

## Run

1. Keep task text: `Prepare a safe README improvement with verified patch evidence.`
2. Click `Start`.
3. Show run status changing to `awaiting approval`.
4. Open `VerifiedPatch`.
5. Show:
   - changed files
   - base SHA
   - clean apply status
   - check rows
   - unified diff
   - provenance
6. In `Approval`, compare reject and approve controls.
7. Reject path demo: type a reason and click `Reject`.
8. Approve path demo: create a new run and click `Approve and apply`.
9. Show run completes through Reviewer and Documenter.
10. Show README changed in target repo.
11. Show review and changelog artifacts.

## Recruiter Angle

ForgeAI is not chat with docs. It is a verified patch control plane:

- graph orchestration
- repository retrieval
- approval-gated mutation
- clean-apply evidence
- diff and provenance
- run telemetry
- security documentation
- plugin boundaries for future cloud and browser tools
