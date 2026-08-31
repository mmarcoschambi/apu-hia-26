# Tasks: feat(tui): persistent validation progress indicator and explicit completion modal on [v]

## Problem Statement
1. Pressing \[v]\ triggers an asynchronous validation routine in BubbleTea. If the operator presses any key during execution, the toast notification is cleared, leaving no visual indicator of ongoing progress or final seal success.
2. The operator is currently forced to inspect raw terminal logs or query \loomctl status <id>\ to verify whether sealing completed.

## Proposed Solution
1. Render a persistent spinner or progress badge (\⏳ VALIDATING & SEALING...\) in the inspector header while the validation goroutine is executing.
2. Display a distinct confirmation modal or sticky banner (\✅ SEALED: Revision #<rev> | Ready for [p] PR or [d] Done\) upon successful transition to \[SEALING]\.
3. If validation fails, keep the failure reason permanently visible in the inspector until the operator acts.

## Acceptance Criteria
- [x] Active validation shows persistent busy state in the inspector pane.
- [x] Successful validation displays a non-transient success banner in [SEALING].
- [x] Error toasts from rejected reviews remain pinned until dismissed.

URL: https://github.com/mmarcoschambi/loom/issues/31
Labels: enhancement