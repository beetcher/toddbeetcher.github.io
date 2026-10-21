# Application-content register

October 20, 2026 · Welcome/document build · Structural placeholders only

| ID | Item | State | What comes next |
|---|---|---|---|
| APP01 | Base résumé | Placeholder | Todd supplies or separately authorizes the real content, dates, roles, contributions and document format. No résumé facts were invented. |
| APP02 | NVIDIA-specific cover letter | Placeholder | Todd identifies the actual opportunity and supplies or authorizes his reasons for interest, relevant evidence and desired invitation. The current route is a concept preview, not a completed application. |
| APP03 | Floating welcome | Starting copy implemented | Uses the introduction Todd liked. Later profile-specific refinements remain possible; it does not claim the documents exist. |

## Reading paths

- `/application/`: persistent document directory, usable without JavaScript.
- `/application/resume/`: base résumé preparation page.
- `/application/nvidia/cover-letter/`: explicit NVIDIA cover-letter preparation page.
- `/?NVIDIA` or `/?for=nvidia`: employer welcome plus opportunity and document panels.
- `/?for=school`: existing education panel; no automatic employment welcome or employment document panel.

All document destinations are real HTML routes labeled as preparation spaces. There are no fake PDF links. The base résumé is the fallback when no profile override is supplied. Letters are explicitly mapped to their opportunity and never fall back to another employer's letter.

When actual documents are provided, preserve their source, verify facts and opportunity mapping, replace the preparation page with readable content, add and inspect the real PDF if supplied or authorized, update profile availability and all preparation wording, and review the entire path before checkpointing. A tailored résumé is optional and does not replace the stored base version.

The broader enjoyable-experience, video and discovery ideas are preserved separately in [the parking lot](WELCOME-PARKING-LOT.md). They are not implemented by this build.
