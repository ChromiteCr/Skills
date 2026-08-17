# Skills

[![library](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FChromiteCr%2FSkills%2Fmain%2F.claude-plugin%2Fplugin.json&query=%24.version&label=library&color=2f81f7&style=flat-square)](VERSIONING.md)
[![skills](https://img.shields.io/badge/skills-30-2f81f7?style=flat-square)](SKILL_INDEX.md)
![commit activity](https://img.shields.io/github/commit-activity/m/ChromiteCr/MaestrWave)
[![last commit](https://img.shields.io/github/last-commit/ChromiteCr/Skills?style=flat-square&color=555555)](https://github.com/ChromiteCr/Skills/commits)
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

The other half of this is token cost. Never read the whole repo by default. Compress before acting. Give a subagent only the context that subagent needs, and get a short handoff back instead of a reasoning log. That part lives in `coding-helper`.

## Reference

**Code**

- **[`ui-design-system-builder`](skills/coding-helper/ui-design-system-builder/SKILL.md)**: Pulls a concrete image out of the project itself, derives a set of CSS tokens and a type scale from it, then builds components on top. Ships with an anti-default checklist.
- **[`maestrwave-ui-system`](skills/coding-helper/maestrwave-ui-system/SKILL.md)**: Drops in my dark serif visual system. The `global.css` and the component layer are copy-paste ready.
- **[`launch-summary-panel`](skills/coding-helper/launch-summary-panel/SKILL.md)**: Turns scattered product material into one 16:9 bento summary panel. It writes a brief first and waits, and every number has to trace back to the source or get flagged.
- **[`radio-quote-card`](skills/coding-helper/radio-quote-card/SKILL.md)**: Name, line, accent color in; one team-radio-style quote card out. Single file, no team badges, and it will not put invented words in a real person's mouth.
- **[`keynote-deck-builder`](skills/coding-helper/keynote-deck-builder/SKILL.md)**: A description, a speech script or an existing deck becomes a product-launch presentation. It settles the narrative beats first and waits. One idea per slide, no bullet points anywhere, and the slide never repeats the sentence you are about to say. Exports to PDF and to an editable deck.

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
- **[`activity-list-optimizer`](skills/study-planning/activity-list-optimizer/SKILL.md)**: Compresses activity descriptions into the Common App character limits, verifying every draft with a tool.
- **[`reflection-interviewer`](skills/study-planning/reflection-interviewer/SKILL.md)**: A STAR reflection interview, one question at a time, keeping your own words. It will not summarize on your behalf.
- **[`deadline-to-study-plan`](skills/study-planning/deadline-to-study-plan/SKILL.md)**: Works backward from a deadline into checkpoints that each have a deliverable. It leaves slack and never invents a due date.
- **[`weekly-study-review`](skills/study-planning/weekly-study-review/SKILL.md)**: A weekly review. The test it has to pass is whether you will do something differently next week.
- **[`application-timeline-builder`](skills/study-planning/application-timeline-builder/SKILL.md)**: Works backward from each school's deadline into the milestones of an application season, converted to Beijing time.

**Skills**

- **[`skill-creator`](skills/skill-authoring/skill-creator/SKILL.md)**: Works out what you already have in hand, skips anything it can extract from the conversation, and writes out a `SKILL.md` that actually runs.

Everything, including status, is in [SKILL_INDEX.md](SKILL_INDEX.md).

## Boundaries

Application essays, coursework, competition entries: for anything that goes out under your name, these skills help you revise a draft you wrote and will not produce one for you. Missing material gets a question rather than an invention. No fabricated experiences, no fabricated numbers, no fabricated sources.

## Compatibility

`claude-code`, `codex`, `cursor`, `codebuddy`, `nestudy`, and any agent that can read Markdown. Each `SKILL.md` declares its own list in the frontmatter. The modeling suite uses semantic actions and explicit no-tool fallbacks rather than depending on host-specific capability names.

## Add your own

Copy [templates/skill-template.md](templates/skill-template.md) to `skills/<category>/<skill-name>/SKILL.md`, write a `tests/cases/<skill-name>.md`, then run:

```bash
./scripts/validate.sh
```

It enforces the layout, the frontmatter, the test case and the index registration. Do not open a PR until it passes. Process is in [CONTRIBUTING.md](CONTRIBUTING.md), version rules in [VERSIONING.md](VERSIONING.md).

## Not written yet

`reading-notes` for textual analysis instead of plot summary, `research-coaching` for research questions and experiment design, `competition-literacy` for defense practice and AI-use limits, plus `vocabulary-learning` and `social-practice`. Priorities and the initial skill lists are in [SKILL_INDEX.md](SKILL_INDEX.md).
