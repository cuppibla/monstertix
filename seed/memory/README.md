# Starting memory, per chapter

`use-solution.sh N` copies one of these over `memory/userx.md` so every chapter
begins from a known file instead of whatever the last three runs left behind.

    default.md      used by every chapter that has no file of its own
    step5.md        used by Chapter 5 only, if you create it
    step6.md        …and so on

The agent appends to `memory/userx.md` every time it calls `remember()`. Run
Chapter 5 four times and the Preferences list has four identical booking lines
in it, which changes what the model reads and makes the chapter behave
differently each time you rehearse it. That is the problem these files solve.

## Writing a chapter-specific file

Copy `default.md`, change what that chapter needs, and name it `step<N>.md`.
Two rules worth keeping:

**Memory is preference, never authorization.** `default.md` says the comfortable
spend is around $200 and $250 is the ceiling. That is what this person is like.
It is NOT permission to buy anything in this task — Chapter 5 asks for that
explicitly, in the session, and the code checks the session, not the file.
Keep the two apart or Chapter 5 teaches nothing.

**Facts here decide questions the agent would otherwise ask.** "Sam bails on
weeknights" is what lets the agent pick the Saturday show out of two Amsterdam
dates without stopping to ask you. Remove it and several chapters start with a
clarifying question instead of the thing you wanted to demonstrate.
