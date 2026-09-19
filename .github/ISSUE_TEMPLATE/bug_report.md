---
name: Bug report
about: Something comes out wrong
title: ''
labels: bug
assignees: ''
---

## What happened

<!-- What the reader produced. Paste the actual text or attach a screenshot. -->

## What the page actually says

<!-- The same passage as it reads in the PDF. This pair is the evidence that
     matters most: it is what a fix gets tested against. -->

## The document

- Where it came from (title, publisher, a link if it is public):
- How it was produced, if you know (LaTeX, Word, a scanner):
- Which page or pages:
- Layout: single column / margin notes / two columns / something else:

## Steps

```
python server.py <file>.pdf <start page>
```

## Environment

- OS:
- Python version:
- pdfplumber and piper-tts versions (`pip list | grep -E "pdfplumber|piper"`):

## Anything else

<!-- If you already know which function gets it wrong, say so. If you can share
     the PDF, or a couple of pages of it, that helps a lot. -->
