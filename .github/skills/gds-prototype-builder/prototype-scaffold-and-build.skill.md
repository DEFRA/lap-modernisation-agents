# Skill: prototype-scaffold-and-build

## Purpose
Turn `prototype-build-plan.json` into an actual, clickable prototype — scaffolding the chosen
flavour and building every page and journey link the plan describes.

## Trigger Conditions
- Runs after `prototype-plan` has produced `prototype-build-plan.json`.
- Reads `flavour` from the parameters recorded by `intake-and-setup`.

---

## Step 1 — Select Mode by Flavour

| Flavour | Mode |
|---|---|
| `nodejs-nunjucks` | **Mode A** — official GOV.UK Prototype Kit |
| `html` | **Mode B** — pure HTML/CSS/vanilla-JS, no templating engine |

---

## Mode A — `nodejs-nunjucks` (Official GOV.UK Prototype Kit)

1. Scaffold with the real installer, never a hand-rolled substitute:
   ```
   npx govuk-prototype-kit@latest create
   ```
   Target `<outputPath>\<projectName>`, accepting the kit's own project structure.
2. Run `npm install` inside the new project.
3. For every page in `prototype-build-plan.json`, in phase order:
   - Create a Nunjucks template under `app/views/` extending the kit's base layout, using the
     documented `govuk-frontend` macros for the page's `pattern` (from the plan) — never hand-rolled
     markup imitating a component.
   - Wire the page into `app/routes.js` so navigating to it, and clicking through from the previous
     page, actually works.
   - Where the plan records branches (e.g. radio answer A vs B), wire the route logic to redirect
     to the correct next page based on the submitted answer — read/write only the kit's session
     data store (`req.session.data`), never a database or external service.
   - Where a later page needs to show an earlier answer back (e.g. check-answers), read it from
     `req.session.data` in the template — this is the kit's supported way to fake "remembering."
4. After all phases are built, start the kit (`npm run dev` or the kit's documented start command)
   and verify every page in the plan is reachable by clicking through from the start page,
   including every branch.
5. Do not add any real backend logic, data validation beyond what the pattern itself renders
   (e.g. `govuk-error-summary` on a deliberately-empty submit, to demonstrate the pattern — not to
   enforce real business rules), or persistence beyond the session store.

---

## Mode B — `html` (Pure HTML, No Templating Engine)

This flavour is for output that must be usable anywhere only plain HTML syntax is accepted — a
CMS field, a static hosting bucket, a hand-off to someone with no Node toolchain, an existing
static site. **Never use Nunjucks, the GOV.UK Prototype Kit, or any other templating engine to
produce this flavour** — not even internally. Every file this mode writes is hand-authored plain
HTML/CSS/vanilla-JS, full stop.

1. Create `<outputPath>\<projectName>\partials\` holding the shared fragments every page repeats,
   written as plain HTML with no templating syntax: `head.html` (doctype, `<head>`, meta, asset
   links), `header.html` (skip link, crown header, phase banner if applicable), `footer.html`
   (GOV.UK footer with required links). These are the single source of truth for layout — treat
   them the way Mode A treats its shared Nunjucks layout, just written as literal HTML instead of
   a template.
2. For every page in `prototype-build-plan.json`, in phase order, assemble the final `.html` file
   yourself by combining the shared partials with the page's own content — literally writing out
   the head/header/content/footer into one file per page. This is manual assembly, not templating:
   there is no `{{ }}`/`{% %}` syntax anywhere, no build tool runs, and the assembled file is the
   only artefact — there's no separate "source" template left behind to compile again.
   Use the documented `govuk-frontend` HTML markup for each page's `pattern` (from the plan) —
   copy the structure straight from the component's HTML examples in the Design System docs,
   never a hand-rolled approximation.
3. If the shared header, footer, or nav ever needs to change, edit the partial once and then
   reassemble every affected page from it — never hand-edit the same header markup independently
   inside multiple page files, since that is exactly the drift this approach exists to prevent.
4. Vendor the compiled `govuk-frontend` CSS and JS into `<outputPath>\<projectName>\assets\` (copy
   the package's `dist` output) so styling and interactive components (accordions, details,
   error-summary focus, back-to-top, etc.) work with no CDN dependency and no internet connection
   needed to view the prototype.
5. Wire navigation as plain links:
   - Simple "next page" links: `<a class="govuk-button" href="next-page.html">Continue</a>`.
   - Branching question pages: a plain HTML `<form>` per option, each `action` pointing straight
     at the correct next static page (radio-button choices become separate submit buttons, or
     plain links styled as the options, since there's no server to read a submitted value). Choose
     whichever reads more naturally for the specific page and note the simplification in the log.
   - "Remembered" answers (e.g. check-answers pages): pass the answer via the URL query string or
     a `sessionStorage` write in a small vanilla-JS snippet on the answering page, read back with
     vanilla JS on the page that displays it. This is a prototype convenience, not real state
     management — keep it to the minimum needed to demo the journey.
6. For any page whose legacy behaviour genuinely can't be faked this way (real dynamic content,
   server-computed values), do not improvise a fake backend — record it in `openItems` as an
   `html`-flavour limitation and suggest `nodejs-nunjucks` for that specific page.
7. After all phases are built, verify the output by opening `index.html` directly or serving the
   folder with a static file server, and click through every page and branch in the plan. Spot
   check that no file contains templating syntax left over by mistake.

---

## Step 2 — Common Verification (Both Modes)

- Every page in `prototype-build-plan.json` exists and matches its `pattern`.
- Every `next`/`branches` link in the plan is actually clickable and lands on the right page.
- No page contains real business logic, validation beyond what the component itself renders, a
  database call, or real authentication.
- No fabricated content resembles real user, claimant, or citizen data — use clearly-fake example
  content (e.g. "Jane Example", not a real name pattern that could be mistaken for live data).

---

## Outputs

| Output | Description |
|---|---|
| `<outputPath>\<projectName>\` | The built prototype — a running Node app (Mode A) or a pure static HTML/CSS/JS file set (Mode B) |
| Updated `prototype-build-plan.json` | `builtPages` marked against the plan, `openItems` updated with anything hit during the build |

---

## Constraints

- Never hand-duplicate the page template (header, nav, footer, skip link, phase banner) across
  individual page files in either mode — author it once, in the shared Nunjucks layout (Mode A) or
  the shared plain-HTML partials (Mode B).
- Never add a database, ORM, real authentication, or business-rule validation in either mode.
- Never use a non-Design-System component when an official one covers the pattern.
- Mode A: never skip `npm install` / the kit's own start command as the final verification step.
- Mode B: never use Nunjucks, the Prototype Kit, or any templating engine — every delivered file
  must be plain HTML/CSS/vanilla-JS with no templating syntax anywhere, so the output is usable
  wherever only HTML is accepted.
