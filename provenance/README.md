# Snapshot Provenance

- `SOURCE_MANIFEST.csv` records hashes of the read-only original human/model inputs and 95 source workbooks. Source-relative paths are identifiers, not a requirement to have that repository for analysis.
- `source_projection.json` records corpus counts and the original-cell/normalized-field export boundary.
- `VALIDATION.json` records dataset checks, comparisons with all 29,925 normalized source records and original annotation-cell records, and reconciliation with the earlier label/rationale results.
- `PORTABILITY_CHECK.json` records a relocated-package smoke run without original data/code access. Point estimates and selected cases are checked against the full run; its 50-draw intervals are development-only.
- `PRIVACY_CHECK.json` records the targeted identity/credential scan. The private roster is read only, never copied, hashed into public metadata or disclosed.
- `PACKAGE_MANIFEST.csv` records paths, sizes and hashes for the complete delivered snapshot, excluding temporary work, environments and the manifest itself.

Each results directory also contains its numerical environment, input/code hashes and bootstrap configuration in `run_manifest.json`, frozen input hashes in `PACKAGE_INPUT_CHECKSUMS.json`, and a complete results inventory in `output_manifest.csv`.

These records distinguish source-input fidelity, numerical validation, portability and privacy checks. They do not certify semantic ethical correctness, representativeness, informed-consent procedures, licensing or public-release approval.
