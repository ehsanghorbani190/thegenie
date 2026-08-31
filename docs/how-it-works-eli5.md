# How TheGenie works (explained like you're 5)

## The problem

Imagine your AI writing assistant is helping you write a research paper. It's
really smart, but it has a bad habit: when it's not sure about a fact, it
sometimes just... makes one up. It sounds confident either way, so you can't
tell the difference between "this is from a real paper" and "the AI guessed."
That's called *hallucination*, and it's dangerous in academic writing.

TheGenie's whole job is to stop that from happening, by giving the AI a
librarian it has to actually ask.

## The librarian analogy

Think of TheGenie as a very literal, very honest librarian who lives on your
own computer:

- You hand the librarian your PDFs. The librarian reads every page and
  memorizes exactly where every sentence lives — which file, which page,
  which paragraph.
- When the AI wants to say something like "trust in AI increases over time,"
  it has to ask the librarian first: *"Do you have anything about that?"*
- The librarian never makes anything up. It only ever hands back **exact
  sentences it actually has**, plus exactly where they came from. If it
  doesn't have anything, it says so — it never guesses to be helpful.
- The AI then writes its sentence and sticks a little tag on it, like a
  receipt: `[[REF:some-id]]`. That receipt proves *which* library book that
  sentence came from.
- Later, a separate checker walks through the whole essay and asks, for
  every receipt: "Does this book actually say what the essay claims it
  says?" If not, it flags it — loudly.

That's the entire system. Everything else is just details of how each of
those steps actually works.

## Step by step, in order

### 1. Reading the PDFs (`thegenie ingest`)

TheGenie opens each PDF and pulls out the text, page by page, keeping track
of exactly which page each sentence was on. It also tries to spot headings
(like "Introduction" or "Results") by noticing which text is bigger or
bolder than the rest — the same way you'd spot a heading by eye.

It then chops the text into bite-sized chunks (a paragraph or so each) — not
too big, not too small — sort of like tearing a book into index cards, one
topic per card. Each card remembers its exact wording, its page number, and
gets a permanent ID tag.

### 2. Turning sentences into "meaning fingerprints" (embeddings)

Computers can't compare "meaning" directly, so TheGenie uses a small AI model
to turn every card into a list of numbers — a kind of fingerprint of what
that sentence *means*. Two sentences about similar things end up with similar
fingerprints, even if they use completely different words. These
fingerprints get stored in a little local database called Qdrant (like a
filing cabinet, but for fingerprints).

### 3. Searching (`search_references`, the tool the AI uses)

When the AI asks a question, TheGenie:

1. Turns the question into a fingerprint too, and finds the ~20 index cards
   with the most similar fingerprints (fast, but rough — like a librarian
   quickly scanning the shelf).
2. Then a *second*, slower, much more careful AI model reads the question
   side-by-side with each of those 20 cards, one at a time, and re-scores how
   relevant each one really is (slow, but accurate — like actually reading
   each page before handing it over).
3. Picks the best few, making sure they don't all say the exact same thing
   twice, and — where possible — come from more than one source.
4. Hands the AI back the exact wording, the page number, and a receipt ID.
   Never a summary, never a guess — always the literal words from the PDF.

### 4. Writing with receipts

The AI writes its sentence and glues a receipt onto it:
`[[REF:citation-id]]`. This receipt is invisible in a sense — it's not
something a reader normally sees — but it's how *everything downstream*
knows exactly which card that sentence is supposed to match.

### 5. Checking the receipts (`thegenie verify`)

This is the strict part, and it happens in two layers:

**Layer 1 — "does this receipt even exist?"** (`thegenie citations`)
Does the ID actually point to a real card? Does that PDF still exist on disk
and still have the same content it had when it was indexed? Is the page
number real? This catches broken or fake citation IDs immediately — cheap
and instant, no AI needed for this part.

**Layer 2 — "does the card actually say that?"** (semantic verification)
This is the harder question. TheGenie pulls up the exact sentence(s) the
receipt points to, and a third AI model (trained specifically to judge
"does sentence A support sentence B?") compares the claim to the source.
It comes back with one of:

- **SUPPORTED** — yes, the source really says this.
- **CONTRADICTED** — the source says the *opposite*.
- **UNSUPPORTED** / **UNVERIFIABLE** — not enough evidence either way.
- **QUOTE_MISMATCH** — the essay put something in quotation marks that
  isn't the source's exact wording (a fabricated or altered "quote").

Some of the checking is done with simple, deterministic rules before the AI
model even gets involved — for example, checking that any *number* in the
claim (like "45 participants") is the exact number the source uses, not a
rounded or made-up one. Rules don't get confused or hallucinate, so wherever
a rule can answer the question, TheGenie prefers the rule over the AI guess.

### 6. Suggesting fixes, never making them (`thegenie revise`)

If something fails verification, TheGenie writes up a to-do list: "this claim
wasn't supported, here's the evidence we actually found, here's a similar
passage that might fit better instead." It never edits your essay itself,
and it never asks another AI to "fix the wording for you" — a human has to
look at the actual evidence and decide. TheGenie's job stops at "here's the
problem," not "here's my rewrite."

## Why it's careful about *how* claims are phrased

The AI model that checks "does the source support this claim" is a little
literal-minded. If you write "**In this study**, trust increases over time,"
the checking model can get confused about *whose* study you mean, and
under-scores something that's actually true. So the sentence is judged on
its *bare claim* — "trust increases over time" — while the `[[REF:...]]`
receipt tag is what actually carries the "who said this" part. That's why
TheGenie encourages writing claims plainly and letting the receipt do the
attribution job, instead of writing "X et al. found that Y."

## Why everything stays on your computer

None of your PDFs, none of the extracted text, and none of the search
queries are ever sent to any AI company over the internet. Every model used
here — for search, for re-checking relevance, and for the fact-checking
step — runs entirely on your own machine. The only thing that leaves your
computer is the handful of specific sentences the AI writing assistant
actually asks for and gets shown, exactly the same as if you'd copy-pasted
them yourself.

## What TheGenie is *not*

- It's not a second AI that answers your questions — it never generates
  prose, arguments, or opinions. It only ever hands back real, exact
  sentences from your own PDFs.
- It's not proof that nothing is wrong. It's a very good, very literal
  fact-checker — not a guarantee. A human still needs to read the actual
  sources for anything that matters.
- It doesn't "understand" your essay's argument — it checks one claim
  against one citation at a time, narrowly and mechanically. That's a
  feature: mechanical and narrow is much harder to fool than "sounds smart."
