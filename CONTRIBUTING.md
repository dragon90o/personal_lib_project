# Contributing

Thanks for looking. This started as a personal tool for studying, so it is small
and opinionated, but it is meant to be worked on by other people now.

## The one rule

**Don't lose content.** Every design decision here answers to that. A change
that makes the output prettier but drops a formula, a diagram, a code block or
the indentation inside it is not an improvement. Fidelity over elegance.

That is why the code is full of thresholds and safeguards that look paranoid:
each one exists because a real page came out wrong. The README section *Things I
learned along the way* is the log of those, and it is worth reading before
changing any of the detection heuristics.

## Getting set up

```
git clone https://github.com/dragon90o/personal_lib_project.git
cd personal_lib_project
python -m venv venv
venv/Scripts/activate        # on Linux: source venv/bin/activate
pip install -r requirements.txt
```

Then download at least the English voice model, as described in the README, and
point the reader at a PDF:

```
python server.py some-book.pdf
```

Nothing is installed system-wide and nothing is written outside the project
folder: processed books go to `books/<name>/`.

## Running the tests

```
python tests.py
```

`tests.py` is a plain script, not pytest: it prints what it is checking and
stops at the first failed assertion, so the output doubles as a description of
the invariants. Run it before and after your change.

One check (5) reads from `books/`, so it needs a processed book on disk and
reports that it was skipped when there is none. The rest build their pages out
of synthetic `extract_text_lines()`-shaped dictionaries and run anywhere.

If you fix a bug in the extraction, **add a check for it**. The pattern is in
the file: build the smallest page that reproduces the problem as a list of
fake lines or words, then assert on the blocks that come out. Those synthetic
pages are cheap, they run without a PDF, and they are the only thing standing
between a threshold tweak and a silent regression somewhere else.

## Everything in English

Identifiers, file names, comments, docstrings, documentation, printed messages
and the reader interface are all in English. The project was written in Spanish
first and then translated wholesale, for exactly this reason: someone who does
not read Spanish should still be able to follow the code.

Please keep it that way in a pull request, commit messages included. Issues and
discussion, on the other hand, are welcome in either language.

## Code style

- Plain Python, standard library plus `pdfplumber` and `piper-tts`. New
  dependencies need a good reason.
- No classes where a function does; the code is a pipeline of small functions
  that hand dictionaries to each other.
- Tunable numbers go in keyword arguments with defaults, not inline: see
  `margin_note_gap(words, width, minimum=8, enough=40, spare=0.3)`.
- **Docstrings explain the why, not the what.** This is the house style, and the
  most useful thing you can copy. A docstring here says what went wrong before
  the function existed, with the real broken output quoted. If you tune a
  threshold, say what you measured and on which document.
- 4-space indentation, lines under 80 columns.

## What kind of change is most useful

In rough order:

1. **A PDF that comes out wrong.** The most valuable contribution, even without
   a fix. Open an issue saying what the reader produced and what the page
   actually says. Layouts that have never been tried — scanned books, right-to-
   left scripts, tables, footnotes, multi-level lists — are where the bodies
   are buried.
2. **More voices.** Add the model to `VOICES` and the stop words to `STOP_WORDS`,
   both in `book.py`. Nothing else should need touching.
3. **Figure captions.** They currently end up baked into the PNG and are never
   read out loud, which is a real content loss.
4. **Making the reader interface translatable.** The buttons and labels are
   hard-coded English in `template.py`, which is fine until someone wants the
   controls in the language of the book they are reading.
5. **Tests for the parts that have none**, particularly `server.py`.

## Pull requests

- One change per pull request.
- Say what document made you write it, and paste the before/after text. That is
  the evidence that matters here.
- Run `python tests.py` and mention the result.
- Keep everything in English, the code included.
- If you changed a heuristic, explain what else you checked it against. A
  threshold that fixes one book and breaks another is the failure mode of this
  whole project.

Issues and questions are welcome too, in English or Spanish.
