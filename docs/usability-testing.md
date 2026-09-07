# FitForge usability testing

## The rule

**Every finding in this document comes from watching a real person use FitForge.**

No invented participants, no invented percentages, no "users found it confusing"
without a specific person who was specifically confused. When only three people
have tried something, the write-up says three — not "76% of users". A portfolio
that quotes fabricated adoption numbers is worse than one that quotes none,
because the numbers are the first thing an interviewer will ask about.

Observations that come from the team rather than a participant belong in the
[Internal observations](#internal-observations) section, clearly separated. They
are hypotheses to test, not findings.

## Running a session

Aim for 3–5 participants. Fresh accounts, not the demo login — the demo account
is pre-seeded, which hides exactly the first-run problems worth finding.

**Setup:** a laptop, the participant driving, you watching. Ask them to think
aloud. Record the screen only with permission.

**Say this once, at the start:**

> I'm testing the app, not you. If something is confusing, that's a problem with
> what I built. Please say what you're thinking as you go — including when you're
> stuck or annoyed.

**Then stay quiet.** The single most common way to ruin a usability session is to
help. When someone hesitates, count to ten before saying anything. If they ask
"what should I do here?", answer with "what would you do if I weren't here?"

## The tasks

Give one at a time. Do not read out the UI labels — if the task says "log the
workout" and the button says "Log This Workout", saying the button's name out
loud tests nothing.

| # | Task given to the participant | What you are actually watching for |
|---|---|---|
| 1 | "Sign up and get yourself a workout plan for three days a week." | Where they stall in the five-step wizard. Does the equipment step make sense? Do they understand what "no equipment" excludes? |
| 2 | "You just finished the first day's workout. Record what you did." | Can they find the logging entry point at all? Do the pre-filled sets and reps help or mislead? What do they do with an exercise measured in seconds? |
| 3 | "You did that workout again a week later, but heavier. Record that too." | Whether logging a second session is obvious once the first is done. |
| 4 | "Find the plan you made earlier and open it." | Whether "My Plans" reads as history. |
| 5 | "Show me how your bench press has changed over time." | Whether the dashboard's exercise picker is discoverable. |
| 6 | "Sign out and back in." | Whether anything is unexpectedly lost. |

**Also worth watching, without prompting:** leave the session open long enough
for the access token to lapse (30 minutes) and see whether anything visibly
breaks. The refresh path is covered by automated tests, but only a person can
tell you whether the app *feels* like it dropped them.

## Recording what happened

For each task, write down:

- **Completed?** yes / yes-with-difficulty / no
- **Time**, roughly. Precision is not the point; "about 20 seconds" vs. "nearly
  two minutes" is.
- **What they actually did**, in their words and clicks. Not your interpretation.
- **Where they hesitated.** Hesitation is the signal; people rarely say "I am
  confused", they just stop moving.

Write it down during the session. Reconstructing afterwards turns observation
into memory, and memory into what you expected to happen.

## Findings

One row per distinct problem. `n` is how many participants hit it, out of how
many tried — always both numbers.

| # | Finding | n | Severity | Status | Fix |
|---|---------|---|----------|--------|-----|
| _(none yet — no sessions have been run)_ | | | | | |

**Severity:** _blocker_ (could not complete the task) · _major_ (completed, but
struggled or needed a hint) · _minor_ (noticed and disliked it, task unaffected).

Fix at least one finding before calling this done, and link the commit in the
Fix column.

## Internal observations

Not findings. These are things we noticed ourselves and think are worth putting
in front of a participant. They stay here until a real person hits them, at which
point they move up to the table with an `n`.

| # | Observation | Where | Why we suspect it matters |
|---|-------------|-------|---------------------------|
| I1 | An exercise prescribed as "30 seconds" pre-fills the log as **30 reps**. The field takes the leading number of the free-text `reps` value, which is right for "8-10" and wrong for a duration. | `LogWorkoutModal.tsx` → `toLogRow` | A plank logged as 30 reps inflates volume charts and can set a nonsense personal record. Pinned by a test in `LogWorkoutModal.test.tsx` that documents the behaviour without endorsing it. |
| I2 | Nothing on the plan page says a plan has been saved. | `WorkoutPlanPage.tsx` | Participants may regenerate rather than revisit, not knowing "My Plans" already holds it. |
| I3 | "My Plans" is the only route to a past plan, and the label does not say "history". | `Navbar.tsx` | Task 4 will show whether this reads as history or as something else. |

## After the sessions

Update the findings table, fix at least one thing, and record honestly what was
left unfixed and why. "We saw this twice and chose not to fix it yet" is a
legitimate entry; quietly dropping it is not.
