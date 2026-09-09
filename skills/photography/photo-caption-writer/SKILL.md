---
name: photo-caption-writer
description: Write a factual short photo caption or a longer artist statement from photographer-provided context and optional EXIF metadata. Use when a user asks for a caption, wall label, portfolio note, or brief statement for an existing photograph. Do not infer emotions, intent, place, identity, or circumstances from the image alone.
category: photography
version: 0.1.0
status: draft
priority: P2
compatible_agents:
  - claude-code
  - openclaw
  - cursor
  - codebuddy
  - generic-llm-agent
---

# Photo Caption Writer

Write concise, usable copy without turning guesses about a photograph into facts.

## Inputs

Collect only what the requested output needs:

- the photograph, or a description of it;
- output mode: `short` or `long`;
- destination or audience, if relevant;
- facts the photographer confirms: time, place, subject, event, process, or circumstances;
- the photographer's own intent, memory, or interpretation;
- optional EXIF metadata.

Do not block on missing optional inputs. If the user asks for a factual detail that is absent, ask for it or omit it. Never fill the gap by guessing from pixels, filenames, or nearby context.

## Workflow

1. **Separate the evidence.** Make three private working lists:
   - `confirmed`: explicitly supplied by the photographer or extracted from metadata;
   - `attributed`: interpretations or intentions stated by the photographer;
   - `unknown`: anything merely inferred from the image.
2. **Extract metadata when useful.** If a local image is available and the runtime can execute Python, run:

   ```text
   python scripts/extract_exif.py IMAGE
   ```

   The script requires Pillow. Treat `null` fields as unavailable; do not mention them. If the script cannot run, use only metadata the user provides.
3. **Choose the mode.**
   - `short`: one sentence, normally 15–35 words. State only useful context; include camera settings only when requested or editorially relevant.
   - `long`: one restrained paragraph, normally 70–150 words. Connect confirmed context, the photographer's attributed intent, and relevant process details.
4. **Draft in the user's language and requested voice.** Prefer concrete nouns and verbs. Preserve uncertainty with wording such as “the photographer recalls” or “appears” only when uncertainty itself is useful and clearly marked.
5. **Run the honesty check.** For every claim, identify its source. Remove or qualify any claim supported only by visual inference.
6. **Return clean copy.** Give the finished caption first. Add a brief `待确认` list only when unresolved facts materially affect publication.

## Source and attribution rules

- EXIF supports capture settings and recorded timestamps; it does not establish creative intent.
- A user-provided account supports that person's stated memory or intention, not an objective claim about every viewer's experience.
- Visible content can support neutral description, but not hidden identity, exact location, relationship, emotion, symbolism, or cause.
- Do not identify people, private places, medical conditions, political affiliation, or other sensitive traits from appearance.
- Do not claim that a photograph “expresses,” “captures,” or “symbolizes” an idea unless the photographer supplied that interpretation. Attribute it when appropriate.
- Preserve the distinction between capture time and file creation or modification time.
- Do not expose GPS or other sensitive metadata unless the user explicitly asks and understands the publication context.

## Output patterns

### Short

```text
[Publication-ready caption]

待确认（only if needed）:
- [missing fact that materially changes the caption]
```

### Long

```text
[Publication-ready paragraph based on confirmed context and attributed intent]

待确认（only if needed）:
- [missing fact that materially changes the statement]
```

Do not append an EXIF dump unless requested.

## Quality checklist

- The requested mode and approximate length are respected.
- Every factual claim is confirmed, extracted, or visibly qualified.
- Creative intent is supplied by or attributed to the photographer.
- Missing EXIF fields were omitted rather than invented.
- Technical settings earn their place instead of reading like a camera log.
- No sensitive metadata or inferred sensitive trait is exposed.
- The copy can be pasted into its destination without editing away process notes.

## Tests

1. **Short, complete context:** Given a confirmed place, date, and subject, produce one compact sentence without adding mood or symbolism.
2. **Long, photographer-supplied intent:** Turn supplied facts and a first-person explanation into a restrained paragraph; do not strengthen the explanation into an objective truth.
3. **Missing EXIF:** Given metadata with absent aperture and lens fields, omit both and do not estimate them.
4. **Inference pressure:** If asked to “explain what the lonely person is feeling” from the image alone, decline to assert an emotion and offer neutral visual description or ask for the photographer's intent.
5. **Privacy boundary:** If GPS is present but the user did not request location disclosure, do not surface coordinates or derive a place name.
