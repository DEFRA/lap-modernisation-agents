# Skill: intake-and-setup

## Purpose
Establish exactly what is being built before anything is created: where, what it's called, which
flavour, and whether it's rebuilding a legacy UI or starting from a blank page. This skill never
guesses — it asks, and it records the answers so every later skill and the tracking log can rely
on them.

## Trigger Conditions
- Always runs **first**, before any file is created.

---

## Step 1 — Ask for Output Path and Project Name

Ask the developer for:
- `outputPath` — absolute path to the folder the new prototype project will live under.
- `projectName` — kebab-case name for the project folder itself.

Check whether `<outputPath>\<projectName>` already exists:
- If it doesn't exist, this is a **new prototype** — proceed to Step 2.
- If it exists, ask the developer whether they want to **continue** an existing prototype (add
  more pages to it) or pick a **different name**. Never overwrite an existing project folder
  without an explicit answer.

---

## Step 2 — Ask for Flavour

Ask which flavour the developer wants, explaining the trade-off in plain terms rather than
defaulting silently:

| Flavour | Say this |
|---|---|
| `nodejs-nunjucks` | "The official GOV.UK Prototype Kit — a real Node.js app you run locally with `npm run dev`. This is what GOV.UK's own get-started guide walks through, and it's the easiest way to fake 'remembering' an answer between pages." |
| `html` | "A set of plain HTML/CSS/vanilla-JS files — no templating engine involved anywhere, so the output is safe to use wherever only HTML syntax is accepted. Layout is still kept in one place via shared HTML partials, so nothing is hand-duplicated per page. Nothing to install to view it — open a file or point any static server at the folder. No live 'remembering' between pages beyond what a hidden field or query string can carry." |

If the developer is unsure, recommend `nodejs-nunjucks` for anything involving a multi-step
journey with answers that need to reappear later (check-answers pages, personalised content), and
`html` for a quick look-and-feel demo, a stakeholder walkthrough, or an environment where Node
can't be installed.

---

## Step 3 — Ask for Source: Legacy Reference or Prompts

Ask whether this prototype is rebuilding an existing application's UI, or starting from scratch:

- **Legacy reference** — ask for `referenceProjectPath` (absolute path to the existing
  application's codebase, any tech stack — .NET, Ruby, Node, or otherwise). Confirm the path
  exists and is readable before moving on. This routes to `legacy-ui-discovery` next.
- **Greenfield** — ask for `prompts`: a free-text description of the pages, journeys, and content
  wanted. Push for enough detail to plan from — page names, the order they flow in, what each
  page asks or shows, and where branching happens (e.g. "if the answer is no, skip to page 5").
  A one-line prompt ("build me a claims service") is not enough to plan from; ask a follow-up.

Exactly one of these two must be established. If the developer gives both, ask which should lead
— the legacy inventory can still inform a greenfield redesign, but the plan needs one source of
truth for journey order.

---

## Step 4 — Create the Project Scaffold

- Create `<outputPath>\<projectName>\` if it doesn't already exist.
- Create `<outputPath>\<projectName>\prototype-reports\` for this run's JSON outputs.
- Do not scaffold the actual kit or HTML build here — that's `prototype-scaffold-and-build`'s job,
  after the plan exists.

---

## Outputs

| Output | Description |
|---|---|
| Confirmed parameters | `outputPath`, `projectName`, `flavour`, and source (`referenceProjectPath` or `prompts`), held for the remaining skills |
| `<outputPath>\<projectName>\` | Project root folder |
| `<outputPath>\<projectName>\prototype-reports\` | Reports subfolder, empty at this point |

---

## Constraints

- Never default `outputPath`, `projectName`, `flavour`, or the source. Ask for each explicitly.
- Never overwrite an existing project folder without the developer confirming continuation.
- Do not proceed to `legacy-ui-discovery` or `prototype-plan` until all parameters in Steps 1–3 are confirmed.
