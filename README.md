# Skills

[![library](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FChromiteCr%2FSkills%2Fmain%2F.claude-plugin%2Fplugin.json&query=%24.version&label=library&color=2f81f7&style=flat-square)](VERSIONING.md)
[![skills](https://img.shields.io/badge/skills-61-2f81f7?style=flat-square)](SKILL_INDEX.md)
[![last commit](https://img.shields.io/github/last-commit/ChromiteCr/Skills?style=flat-square&color=555555)](https://github.com/ChromiteCr/Skills/commits)
[![commit activity](https://img.shields.io/github/commit-activity/m/ChromiteCr/Skills?style=flat-square&color=555555)](https://github.com/ChromiteCr/Skills/commits)
[![stars](https://img.shields.io/github/stars/ChromiteCr/Skills?style=flat-square&color=555555)](https://github.com/ChromiteCr/Skills/stargazers)
[![agents](https://img.shields.io/badge/agents-claude--code%20%7C%20codex%20%7C%20cursor%20%7C%20nestudy-555555?style=flat-square)](#compatibility)

My own set of agent skills. They exist so that when I write code, lyrics, application materials or an essay, the agent stops reaching for the default.

Judging whether a choice was any good is harder than making the choice. What these skills do is write down the criteria I had already explained too many times, so the agent usually arrives there on the first try instead of the fourth.

They are a byproduct of doing the work. AI amplifies what you already know rather than standing in for it. So go learn to code, or design, or get good at whatever field you are actually in. That value has only gone up.

## Install

Claude Code:

```bash
/plugin marketplace add ChromiteCr/Skills
/plugin install skills-library@skills-library
```

Any other agent, just pull it down and read it:

```bash
git clone https://github.com/ChromiteCr/Skills.git
```

## Why use it?

**Agents have the capability. At every single step they still take the default.**

Ask one for an interface and you get Inter, `#3b82f6`, 8px radius on everything, a `0 4px 12px rgba(0,0,0,.1)` shadow underneath. Ask for lyrics and you get every scar turning into starlight. Ask for Chinese prose and you get an em dash in every other sentence, three tidy bullet points, and a paragraph that lifts off into significance right at the end. Ask for a study plan and every single day is full.

Every one of those is defensible on its own. Stacked together they produce the thing anyone can now spot in about two seconds.

These skills close the defaults off one at a time. A color has to be justified against the project it belongs to. A lyric line has to be something you could point a camera at. An em dash in a finished essay counts as a violation, no exceptions. Once the criteria are written down, there is nothing left to pick from.

The other half of this is token cost. Never read the whole repo by default. Compress before acting. Give a subagent only the context that subagent needs, and get a short handoff back instead of a reasoning log. That half is not written yet: it is the `planned` rows under `coding-helper` in [SKILL_INDEX.md](SKILL_INDEX.md).

## Reference

**Code**

- **[`ui-design-system-builder`](skills/coding-helper/ui-design-system-builder/SKILL.md)**: Pulls a concrete image out of the project itself, derives a set of CSS tokens and a type scale from it, then builds components on top. Ships with an anti-default checklist.
- **[`maestrwave-ui-system`](skills/coding-helper/maestrwave-ui-system/SKILL.md)**: Drops in my dark serif visual system. The `global.css` and the component layer are copy-paste ready.
- **[`launch-summary-panel`](skills/coding-helper/launch-summary-panel/SKILL.md)**: Turns scattered product material into one 16:9 bento summary panel. It writes a brief first and waits, and every number has to trace back to the source or get flagged.
- **[`radio-quote-card`](skills/coding-helper/radio-quote-card/SKILL.md)**: Name, line, accent color in; one team-radio-style quote card out. Single file, no team badges, and it will not put invented words in a real person's mouth.
- **[`keynote-deck-builder`](skills/coding-helper/keynote-deck-builder/SKILL.md)**: A description, a speech script or an existing deck becomes a keynote-style presentation, for a product launch or for a classroom, a lecture or a research talk. It settles the occasion and the narrative beats first and waits. One idea per slide, no bullet points anywhere, the slide never repeats the sentence you are about to say, and nothing appears before you get to it: steps reveal on click, what you have covered dims, and the same symbol glides from one slide to the next. In the classroom three launch habits give way to learning research: evidence slides carry a one-sentence claim, real questions are allowed as long as the answer gets revealed, and the recap makes people recall before it shows. Native MathML for equations, a presenter window, a handout for what the projector leaves out, and exports to PDF and to an editable deck that carries the builds, the dimming, the accent marks and the morph between adjacent slides, plus speaker notes.
- **[`photo-spread-composer`](skills/coding-helper/photo-spread-composer/SKILL.md)**: A set of photographs becomes a printed spread. It hands you a grammar rather than a template: band composition, caption and credit conventions, and one equation that solves every position, so which photo leads and how the page divides stay judgment calls. Under-resolution stops the build. For your own 3–9 photos kept in order as one long image, grid or PDF, use `photo-series-layout`.

**Music**

- **[`llm-midi-composition`](skills/songwriting/llm-midi-composition/SKILL.md)**: Gets an LLM to write a score instead of audio. Two-stage calls, salvage of truncated output, deterministic repair, and a rule-based fallback that never pretends to be the model.

**Mathematical modeling**

- **[`modeling-problem-reading-coach`](skills/modeling/modeling-problem-reading-coach/SKILL.md)**: Turns a modeling prompt into a checkable contract: objectives, variables and units, constraints, subproblem dependencies, ambiguities, and missing information. It stops before model selection or solution writing.
- **[`model-selection-tutor`](skills/modeling/model-selection-tutor/SKILL.md)**: Compares genuinely different model families against a simple baseline, data and assumptions, identifiability, validation cost, extrapolation, and failure behavior. Recommendations stay conditional until a discriminating test is run.
- **[`modeling-assumption-builder`](skills/modeling/modeling-assumption-builder/SKILL.md)**: Separates prompt facts, definitions, calibration choices, numerical settings, and actual assumptions. Every assumption gets a scope, failure consequence, load-bearing rank, and falsification or stress test.
- **[`model-critique-coach`](skills/modeling/model-critique-coach/SKILL.md)**: Reconstructs the submitted model before attacking it, traces each claim back to runs, data, equations, and assumptions, then ranks findings by their effect on the conclusion and gives a cheap falsifying check.
- **[`modeling-code-builder`](skills/modeling/modeling-code-builder/SKILL.md)**: Implements only a student-confirmed model. An implementation contract, hand-calculated fixture, invariants, validation matrix, explicit solver status, and run manifest keep code, figures, and claims reproducible.
- **[`paper-structure-coach`](skills/modeling/paper-structure-coach/SKILL.md)**: Builds a claim-to-evidence map before moving sections. Each section answers a modeling question; abstract numbers trace to results and runs; validation, interpretation, and limitations stay distinct.
- **[`paper-enhancement-builder`](skills/modeling/paper-enhancement-builder/SKILL.md)**: Turns located draft gaps, critique findings, rubric requirements, and real resource limits into a ranked backlog. Every enhancement has dependencies, validation, acceptance criteria, a failure fallback, and a reason not to add decorative complexity.
- **[`latex-paper-formatter`](skills/modeling/latex-paper-formatter/SKILL.md)**: Freezes content before touching layout, then checks references, citations, figures, notation, tables, template rules, compilation, and the final PDF. A standard-library checker catches deterministic source defects without pretending to validate mathematics.
- **[`team-role-coach`](skills/modeling/team-role-coach/SKILL.md)**: Assigns owners and reviewers to artifacts and decisions, not vague silos. A single source of truth, critical path, nine review gates, short handoffs, freeze points, and honest contribution records keep parallel work aligned.

**Physics**

- **[`physics-problem-router`](skills/physics/physics-problem-router/SKILL.md)**: The way in. Three questions settle it — is the answer unique, what counts as done, and where exactly are you stuck — and only then does anything get routed. It also catches the two ways people walk through the wrong door: asking for a number when the question is open, and asking for anything at all when the statement is still short a quantity.
- **[`competition-scenario-extractor`](skills/physics/competition-scenario-extractor/SKILL.md)**: A long problem, an IYPT one-liner, a paragraph of a paper or a lab log becomes a clean statement and a subproblem tree. Every "neglect", "ideal" and "assume" gets pulled out of the prose onto a ledger with the mechanism it switched off and the dimensionless ratio that decides when the switch fails. It counts unknowns against equations and will not patch an underdetermined problem with a reasonable-sounding assumption.
- **[`problem-formalization-coach`](skills/physics/problem-formalization-coach/SKILL.md)**: Every condition gets traced to the law behind it, and the law does not go on the ledger until you can say why it holds here. Momentum conservation means the external impulse is small compared to the internal one, not "because it's a collision". Then it counts degrees of freedom and equations and stops — writing and solving the system is the part you keep.
- **[`problem-representation-scout`](skills/physics/problem-representation-scout/SKILL.md)**: Being stuck usually means working in the wrong representation. It cuts the process at the only five places a stage can end, handles the impulsive limit exactly — position cannot jump, velocity can, gravity's impulse vanishes — and then fits each stage with a representation chosen by what the wanted quantity does *not* contain.
- **[`reference-frame-choice-guide`](skills/physics/reference-frame-choice-guide/SKILL.md)**: Compares the candidate frames by what each one costs in pseudo-forces and buys in simpler constraints. The required output is the invariance list: which conservation laws still hold, which quantities never moved, and which only looked like they did.
- **[`physics-mechanism-decomposer`](skills/physics/physics-mechanism-decomposer/SKILL.md)**: Turns "why does it do that" into propositions you can test. Conservation budgets catch the mechanism you forgot, every scaling law carries an exponent and a provenance, ranking happens between quantities of the same dimension, and each pair of mechanisms gets an observable that actually separates them — different exponent or different sign, never a different coefficient.
- **[`dimensional-analysis-checker`](skills/physics/dimensional-analysis-checker/SKILL.md)**: The cheapest gate a formula has to pass. It normalises the notation, builds a symbol-to-dimension map, and points at the first place the dimensions stop agreeing — unlike terms added together, an equation whose sides differ, a temperature sitting inside an exponential. Every term that survives still has to be given a physical meaning; a term nobody can name is a term nobody understood. Passing is never reported as being right.
- **[`concept-to-formula-deriver`](skills/physics/concept-to-formula-deriver/SKILL.md)**: Rebuilds a formula from the principle it descends from, so it stops being something you memorised. Each assumption is written at the step that actually uses it, not stacked at the top, and when a quantity cancels you get told why it cancels. The derivation that gets graded stays yours.
- **[`symbolic-first-discipline-coach`](skills/physics/symbolic-first-discipline-coach/SKILL.md)**: Holds the symbols until the structure stops changing, then puts that side by side with the substitute-early path. What it exposes is what numbers hide: the quantity that cancels, the two parameters that only ever appear as one product, the threshold that was a comparison between two symbols before it became a decimal.
- **[`fermi-estimation-coach`](skills/physics/fermi-estimation-coach/SKILL.md)**: Once the mechanisms are ranked, this puts numbers on them. An explicit factorisation, low/central/high for every factor with its evidence tier, intervals rather than decorative decimals, and a script that checks the worksheet's own arithmetic. It will not discover mechanisms for you.
- **[`limiting-case-validator`](skills/physics/limiting-case-validator/SKILL.md)**: Picks the smallest useful set of limits and makes you write down what physics says should happen **before** doing the algebra. Then it compares. Catches the expression that diverges where nothing should, flips sign where nothing should, or quietly loses the special case you already know.
- **[`answer-plausibility-checker`](skills/physics/answer-plausibility-checker/SKILL.md)**: The smell test a number has to pass before you believe it — units, sign, magnitude, limiting behaviour, reference values with a date on them, and whether the conserved totals still balance. Where no ground truth exists it switches to order-of-magnitude plus a conservation audit instead of inventing one.
- **[`derivation-step-checker`](skills/physics/derivation-step-checker/SKILL.md)**: Walks an existing derivation step by step for algebraic equivalence, dimensions and sign — and then for the thing that actually breaks derivations: whether the law invoked at that step still applies there. Constant mass, inertial frame, quasi-static: these die mid-page and the algebra never notices.
- **[`uncertainty-propagator`](skills/physics/uncertainty-propagator/SKILL.md)**: Linear covariance propagation including correlations, with symbolic sensitivities, a contribution budget, and a Monte Carlo run to check the linearisation held. It keeps a large derivative and a large contribution firmly apart, which is what tells you where the next measurement should go.
- **[`model-fit-auditor`](skills/physics/model-fit-auditor/SKILL.md)**: Residual structure, uncertainty-aware goodness of fit, leverage and influence, information criteria. Structure left in the residuals means one of three things is incomplete: the model, the measurement process, or the uncertainty model. The report has to say which it might be, handing drift and apparatus effects to `dataset-systematic-error-hunter`, rather than reach for another parameter.
- **[`dataset-systematic-error-hunter`](skills/physics/dataset-systematic-error-hunter/SKILL.md)**: Scans raw data for drift, temperature dependence, nonlinearity, hysteresis and repeat inconsistency, then pins each signature to a specific physical process in the apparatus. The script produces leads, not causes; correlation is labelled as correlation.
- **[`numerical-stability-auditor`](skills/physics/numerical-stability-auditor/SKILL.md)**: Decides whether a simulation is showing you physics or its own discretisation. Invariant drift, observed order of convergence, and suspicious high-frequency content — and where the drift begins tells you which process the stepping scheme broke.

**Lyrics**

- **[`lyric-concept-builder`](skills/songwriting/lyric-concept-builder/SKILL.md)**: Settles the situation, the image system and the hook candidates before a single line gets written. "Healing" is an effect, not a subject.
- **[`lyric-structure-mapper`](skills/songwriting/lyric-structure-mapper/SKILL.md)**: Parses an `xxxxx` syllable template line by line into a skeleton table. Changing the count changes the melody.
- **[`adversarial-lyric-writer`](skills/songwriting/adversarial-lyric-writer/SKILL.md)**: Three subagents draft in parallel and in isolation, each on a different track. A red team then picks the drafts apart line by line, and the main agent assembles a version by choosing line by line.
- **[`lyric-doctor`](skills/songwriting/lyric-doctor/SKILL.md)**: Checks a finished draft. A script counts syllables and flags clichés, the model judges rhyme group and visual concreteness, and you get a targeted fix list rather than a rewrite.

**Prose**

- **[`writing-rules`](skills/writing/writing-rules/SKILL.md)**: Fifteen rules against the AI register in Chinese, including a hard banned-word list and a tone spec. Only active when I ask for it by name, dormant the rest of the time.
- **[`zlc`](skills/writing/zlc/SKILL.md)**: A four-beat Chinese comment cadence lifted from a classmate. The joke lives in beat two, where a ceremonial tone gets pinned to one very small concrete fact. Mutually exclusive with `writing-rules`, which bans exactly this register.

**Applications and growth records**

- **[`project-brainstorm`](skills/study-planning/project-brainstorm/SKILL.md)**: Deduplicates what you have already accumulated, then gives three options with genuinely different costs and tells you where each one is likely to die.
- **[`admissions-reader`](skills/study-planning/admissions-reader/SKILL.md)**: Reads your record the way an admissions officer would and names the strengths and the gaps. Reads only, writes nothing.
- **[`activity-profile-builder`](skills/study-planning/activity-profile-builder/SKILL.md)**: Turns one spoken account into a structured record and marks what is missing as pending, without filling it in for you.
- **[`activity-list-optimizer`](skills/study-planning/activity-list-optimizer/SKILL.md)**: Compresses activity descriptions into the Common App character limits and verifies every draft's length: with the nestudy tool where it exists, otherwise with a counted fallback that is labelled as such.
- **[`reflection-interviewer`](skills/study-planning/reflection-interviewer/SKILL.md)**: A STAR reflection interview, one question at a time, keeping your own words. It will not summarize on your behalf.
- **[`deadline-to-study-plan`](skills/study-planning/deadline-to-study-plan/SKILL.md)**: Works backward from a deadline into checkpoints that each have a deliverable. It leaves slack and never invents a due date.
- **[`weekly-study-review`](skills/study-planning/weekly-study-review/SKILL.md)**: A weekly review. The test it has to pass is whether you will do something differently next week.
- **[`application-timeline-builder`](skills/study-planning/application-timeline-builder/SKILL.md)**: Works backward from each school's deadline into the milestones of an application season, converted to Beijing time.

**Community programs**

- **[`program-maturity-navigator`](skills/community-programs/program-maturity-navigator/SKILL.md)**: Where an activity actually is, decided by the traces it left — the dates, the headcounts, what people took away — not by what it is called. Three trunk stages, then a fork into two independent axes: depth, where participants make something, and reach, where strangers show up and come back. Neither outranks the other and staying put is a legitimate answer. Each gate is an evidence checklist rather than a judgement call, so it can and does refuse to let you advance; the sharpest requirement is that a trial run must have produced at least one observation you did not expect, because a session that went exactly to plan produced no information. A script decides whether a series has real order — every session after the first has to consume something an earlier one produced — and there is a template for shutting something down, which is what most seeds actually do.

**Photography**

- **[`photo-caption-writer`](skills/photography/photo-caption-writer/SKILL.md)**: Writes a caption or artist statement only from facts the photographer confirmed plus optional EXIF. It will not read emotions, intent, or a location into the pixels; gaps get asked about or left out.
- **[`photo-exif-frame`](skills/photography/photo-exif-frame/SKILL.md)**: Adds a configurable information band below a photograph — aperture, shutter, exposure compensation, ISO, capture time, camera. Missing fields stay blank rather than invented, and the source file is never overwritten.
- **[`photo-poster-stylist`](skills/photography/photo-poster-stylist/SKILL.md)**: Turns the photographer's own account of a photo into a minimal geometric SVG poster — restrained palette, grid, typography, bleed — with a script checking the palette and element counts stay minimal.
- **[`photo-series-layout`](skills/photography/photo-series-layout/SKILL.md)**: Lays out 3–9 finished photographs as one cohesive page, long image, or PDF with consistent frames and gutters. The photographer's order is preserved unless sequencing suggestions are explicitly requested. For a publication-style spread with bands and credits, see `photo-spread-composer`.
- **[`shoot-outing-review-card`](skills/photography/shoot-outing-review-card/SKILL.md)**: Turns one outing into a shareable review card: cover image, focal-length/aperture/shutter habit summaries, and a capture timeline. It shows the habits; it never grades them, and it never exposes GPS or serial numbers.

**Working with AI**

- **[`prompt-brief-builder`](skills/ai-usage/prompt-brief-builder/SKILL.md)**: "Write me something" becomes a brief anyone can execute. It asks at most three to five questions — the ones whose answers actually change the work — and everything still unknown is labelled as an assumption rather than quietly decided. A script checks the brief has no empty sections.
- **[`ai-answer-triage`](skills/ai-usage/ai-answer-triage/SKILL.md)**: Sorts an AI answer into what you can use now, what has to be checked first, and what is only a suggestion. Anything that executes or changes state is marked do-not-run-as-is (review it, try it in a sandbox, have a rollback ready), and destructive or privileged commands go to the front of the queue.
- **[`ai-output-fact-checker`](skills/ai-usage/ai-output-fact-checker/SKILL.md)**: Breaks the answer into checkable claims — links, package versions, DOIs, flags, API names, numbers, quotes — and gives each one the shortest route to being confirmed. Built for the failure that actually bites: a library, a paper or a command that does not exist. One true claim never buys a blessing for the rest.
- **[`ai-code-onboarding-checklist`](skills/ai-usage/ai-code-onboarding-checklist/SKILL.md)**: An intake exam for AI-written code before you decide to trust it: size and nesting, whether any test evidence exists, leftover placeholders, secrets, whether the imports are real packages, and dangerous calls (eval, shell=True, recursive deletes, unsafe deserialization, privilege changes, outbound network) found with ready-made grep patterns. It states plainly that it cannot check whether the algorithm is correct.
- **[`ai-diff-review-protocol`](skills/ai-usage/ai-diff-review-protocol/SKILL.md)**: Reviews an AI's change by risk instead of by line. Does it match what was asked, does it touch a dangerous boundary, how wide is the blast radius, can it be undone — with the counts pulled from the diff first by a script that also reads diffs pasted into a chat, a mandatory hunk-by-hunk human pass whenever a threshold is crossed, and a hard stop when the refactor smuggled in is bigger than the fix requested.
- **[`ai-session-handoff-writer`](skills/ai-usage/ai-session-handoff-writer/SKILL.md)**: For when the work has to survive the session. Decisions carry their reasons so the next reader does not retry the road you already abandoned, verified and unverified are never merged, and credentials are referenced by location rather than copied.
- **[`ai-generated-test-auditor`](skills/ai-usage/ai-generated-test-auditor/SKILL.md)**: A green suite can mean the code works or that the tests cannot tell. This checks the four ways they fail to tell: assertions copied from the implementation, no boundary or error cases, failure signals too weak to notice, and whether breaking the code on purpose would turn them red. For the last one it plans two to five sample mutations; they are only run when the agent can execute the tests, and the report says which.

**Skills**

- **[`skill-creator`](skills/skill-authoring/skill-creator/SKILL.md)**: Works out what you already have in hand, skips anything it can extract from the conversation, and writes out a `SKILL.md` that actually runs.

Everything, including status, is in [SKILL_INDEX.md](SKILL_INDEX.md).

## Boundaries

Application essays, coursework, competition entries: for anything that goes out under your name, these skills help you revise a draft you wrote and will not produce one for you. Missing material gets a question rather than an invention. No fabricated experiences, no fabricated numbers, no fabricated sources.

## Compatibility

`claude-code`, `codex`, `cursor`, `codebuddy`, `nestudy`, and any agent that can read Markdown. Each `SKILL.md` declares its own list in the frontmatter. A skill that names a tool only one runtime has (nestudy's planning tools, Claude Code's subagents) either narrows that list or carries a degraded-mode section saying what to do without the tool, and labels degraded output as such ([CONTRIBUTING.md](CONTRIBUTING.md) §3.2).

## Add your own

Copy [templates/skill-template.md](templates/skill-template.md) to `skills/<category>/<skill-name>/SKILL.md`, write a `tests/cases/<skill-name>.md`, then run:

```bash
./scripts/validate.sh
```

It enforces the layout, the plugin manifest, the frontmatter, the test case and the index registration. Do not commit until it passes; `git config core.hooksPath scripts/git-hooks` makes git run it for you. Single-skill zips come from `./scripts/package.sh`. Process is in [CONTRIBUTING.md](CONTRIBUTING.md), version rules in [VERSIONING.md](VERSIONING.md).

## Not written yet

The token-discipline half of `coding-helper` (project briefs, architecture planning, repo maps, context budgets, edit plans, patch scope, multi-agent routing, the test–debug loop), `workshop-designer` in `community-programs`, `reading-notes` for textual analysis instead of plot summary, `research-coaching` for research questions and experiment design, `competition-literacy` for defense practice and AI-use limits, plus `vocabulary-learning` and `social-practice`. Priorities and the initial skill lists are in [SKILL_INDEX.md](SKILL_INDEX.md).
