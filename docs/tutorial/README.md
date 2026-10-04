# skill-trainer tutorial

You have a coding agent. You have a `SKILL.md` you wrote by hand. You
suspect it could be better but you have no way to tell whether a change
helped or hurt. This tutorial takes you from that spot to a trained skill,
with a number attached to every edit.

Every command below was run while writing this, on macOS with Python
3.12 and Claude Code 2.1. Output blocks are real output, trimmed only for
length. Where a step costs model calls, the chapter says so up front.

## Who this is for

Someone who already uses Claude Code, Codex, Copilot, Cursor or opencode,
and wants their skill files to earn their place instead of being a guess.
You do not need to know anything about optimization. You do need to be
comfortable in a terminal and with git.

## What you will have at the end

- A trained skill on a git branch, where every accepted edit is a commit
  you can diff.
- A task suite of your own, with a scorer that runs without an LLM.
- A `results.tsv` you can read at a glance to see what training did.
- Enough understanding of the loop to know when it is lying to you.

## Chapters

1. [Why train a skill](01-why-train-a-skill.md). The mental model: what
   a training step is, why there is a held-out set, and why git is the
   checkpoint.
2. [Setup and first run](02-setup-and-first-run.md). Install, run the
   tests, and watch the loop rediscover a deleted rule. About ten
   minutes, a handful of editor calls.
3. [Anatomy of a suite](03-anatomy-of-a-suite.md). Every file in a task
   suite, what each field means, and the five scoring modes.
4. [Build your own suite](04-build-your-own-suite.md). Build a SQL
   query suite from scratch: database, tasks, rubric, and the probes
   that turn "wrong" into a named symptom.
5. [Launch a training run](05-launch-a-training-run.md). Config, the
   launch, what to watch, and how to read what came out.
6. [LLM-judged suites](06-llm-judged-suites.md). For skills a script
   cannot score: writing a judge prompt, references versus rubrics, and
   what a verdict looks like.

Read them in order the first time. Chapters 3 and 6 work as reference
afterwards.

## Before you start

You need Python 3.11 or newer, git, and at least one agent CLI installed
and logged in. The tutorial uses `claude` for its examples; chapter 5
shows the flags for the others. Chapter 6 additionally needs a MiniMax
API key.
