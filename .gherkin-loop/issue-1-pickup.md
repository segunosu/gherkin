# Gherkin delivery-loop — pickup of issue #1

The scheduled routine picked up `gherkin:ready` issue **#1**
("Auto-enrol eligible UK new starters and process valid statutory opt-outs")
and read its spec at `features/auto-enrol-eligible-uk-new-starters-and-process-76d9231aca.feature`.

**Routine decision: domain mismatch — no code written.**
This spec describes a UK workplace-pension auto-enrolment feature, but this
repository (`segunosu/gherkin`) is the Gherkin app itself (a Streamlit tool).
The spec does not map to this codebase, so the routine did not invent
implementation code. For a real build, point the board card at the target
project's repository instead of the app repo.

This draft PR exists only to demonstrate the loop mechanics end to end:
board → `gherkin:ready` issue → routine pickup → draft PR + issue comment.
Safe to close.

Refs #1
