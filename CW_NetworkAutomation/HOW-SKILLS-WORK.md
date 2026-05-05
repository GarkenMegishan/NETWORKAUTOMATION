# How Skills Work — A Tutorial Built From What We Just Did

This document teaches you how Claude skills work using the `network-automation` skill we just built as the running example. The goal is to leave you with a clear mental model of every piece: what a skill *is* on disk, how Claude *finds* and *uses* one, what happens when you *install* one, and how to *improve* one.

I'll define every technical term inline. If something looks like jargon, the next sentence will tell you what it means.

---

## 1. What Claude is, in one paragraph

Claude is a **language model** — a program that takes text in and produces text out. The text going in is called the **context** (everything Claude can "see" right now: your messages, prior responses, system instructions, tool definitions, tool outputs). The text coming out is Claude's reply. The context has a maximum size measured in **tokens** — a token is a chunk of text, roughly the size of half a word in English. A typical Claude session has a context window of around 200,000 tokens. That's a lot, but it isn't infinite, and everything you put into it costs space.

The reason the token limit matters for skills: a skill is a body of text that *might* get added to Claude's context. The whole point of skills is letting Claude have a lot of specialized knowledge available *without* loading all of it every single conversation.

---

## 2. What a skill is, on disk

A skill is a **folder** with a specific structure. Yours looks like this:

```
network-automation/
├── SKILL.md              <- the only required file
├── references/
│   ├── cisco.md
│   ├── juniper.md
│   ├── arista.md
│   ├── paloalto.md
│   └── fortinet.md
├── assets/
│   ├── runbook-template.md
│   ├── playbook-template.yml
│   └── jinja-template-example.j2
├── scripts/
│   ├── render_template.py
│   └── config_diff.py
└── evals/
    └── evals.json
```

That's it. There's no compiled binary, no database, no service. A skill is **just a folder of text files**. When you "install" a skill, you're putting that folder somewhere Cowork can find it.

---

## 3. SKILL.md — the heart of a skill

`SKILL.md` is a **Markdown** file (a plain-text format with simple syntax for headings, lists, code blocks). It has two parts:

**Part A: YAML frontmatter.** YAML is a key-value text format. "Frontmatter" means it sits at the top of the file, between two `---` lines. Yours looks like:

```yaml
---
name: network-automation
description: Multi-vendor network automation for enterprise engineers...
---
```

Two fields matter: `name` (the skill's identifier — must match the folder name) and `description` (a blurb that Claude reads to decide whether to use the skill). The description is rate-limiting: too vague and Claude won't trigger the skill when it should; too narrow and it'll miss adjacent cases. We'll come back to this.

**Part B: The Markdown body.** Everything after the closing `---`. This is the actual instructions Claude follows when the skill is active. In your case it's the operating principles ("idempotence beats cleverness"), the table of "request shapes", the workflow templates, and pointers to the per-vendor reference files.

That's the whole structure. Frontmatter for the metadata, body for the instructions.

---

## 4. What "installing" a skill actually does

When you drag your `network-automation.skill` file into Cowork, here's what happens, step by step:

1. Cowork sees the `.skill` extension and recognizes it.
2. It opens the file as a **ZIP archive** (a compressed bundle of files — the `.skill` is literally a renamed `.zip`).
3. It reads the `SKILL.md` inside, parses the YAML frontmatter, and **validates** it. This is where you hit the "description must be at most 1024 characters" error — that's a rule the validator enforces.
4. It extracts the folder contents to a directory on your disk that Cowork manages — typically somewhere under `C:\Users\garry\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\...`.
5. It registers the skill so Claude becomes aware of it. "Aware of" is concrete: it adds the skill's `name` and `description` to a list that gets injected into Claude's system prompt the next time you start a conversation.

The skill is now "installed". Nothing has happened in Claude's brain yet — Claude doesn't *know* anything about your skill until a new conversation starts.

---

## 5. The "available skills" list — progressive disclosure level 1

When you start a new chat in Cowork, Claude receives a **system prompt** — a chunk of text that tells it who it is, what tools it has, what skills are available, and so on. The system prompt is invisible to you but it's the first thing Claude reads.

Inside that system prompt is a section that looks roughly like:

```
<available_skills>
<skill>
<name>network-automation</name>
<description>Multi-vendor network automation for enterprise engineers
(Cisco IOS/IOS-XE/NX-OS, Juniper Junos, ...)</description>
</skill>
... other skills ...
</available_skills>
```

This is called **progressive disclosure level 1**: only the *name and description* of each skill is loaded by default. Not the body, not the references, none of the bundled scripts. Just the advertisement.

Why? Because if you have 20 skills installed and Claude loaded the full body of every one into context, that's tens of thousands of tokens spent on instructions you'll never need this conversation. Progressive disclosure is the trick that lets you have a lot of skills without paying for all of them every turn.

---

## 6. The triggering decision — when does Claude actually use a skill?

Imagine you type: *"I need to add VLAN 75 to two Catalyst 9300 switches."*

Claude reads your message, looks at the available skills list, and asks itself: *which of these descriptions matches what the user is asking?* For each skill, it's basically a fuzzy text match — does the description mention things relevant to the query?

For your network-automation skill, the description includes phrases like *"add a VLAN"* and *"Cisco IOS-XE"*. Those phrases match the query strongly. So Claude decides: *yes, I should consult this skill*.

What "consult" means concretely: Claude calls a built-in tool called the **Skill tool**, passing it the skill's name. The Skill tool reads the file `SKILL.md` and returns its body. That body now becomes part of Claude's context for this turn — it's been promoted from "I know it exists" to "I'm reading it right now".

This is **progressive disclosure level 2**: the body of one specific skill is loaded into Claude's context only when needed.

A few important nuances:

- Claude only triggers skills for tasks where the skill seems likely to *help*. For trivial questions ("what does VLAN stand for?") even a perfect description match won't trigger the skill, because Claude can answer without it.
- If two skills both seem relevant, Claude might consult both. Their bodies stack in context.
- If no description matches, no skill triggers. Claude answers from its general knowledge, which is what we used as the "without_skill" baseline in our evaluation.

This is why we made the description "pushy" — phrases that read like real user requests rather than abstract topics. *"add a VLAN"* triggers more reliably than *"VLAN management"*.

---

## 7. What happens once the skill body is loaded

Now the `SKILL.md` body is in Claude's context. Concretely, that means Claude is now reading text like:

> *Idempotence beats cleverness. A change that can be re-applied safely is worth more than a one-shot script. When generating Ansible/Nornir code, prefer declarative modules...*

Claude treats this exactly like a user instruction. The operating principles, the request-shape table, the workflow templates — all of it becomes guidance Claude follows when constructing the answer.

Notice the body contains pointers like *"Read `references/cisco.md`"*. Those aren't followed automatically. They're a hint to Claude: *"if the request is Cisco-specific, go read that file."* Claude uses its **Read tool** (a tool it has by default in Cowork) to fetch just that file. The contents of `cisco.md` then get appended to context.

That's **progressive disclosure level 3**: bundled files are loaded only when the body of the skill tells Claude to load them.

Why this matters for your skill: if I had stuffed all 5 vendors' syntax into one giant SKILL.md, every Cisco-only question would force Claude to also read 4 unrelated vendor sections. By splitting into per-vendor reference files and pointing to them by name, each query loads only what's needed.

---

## 8. What `assets/` and `scripts/` are for

These are the other two folders in your skill. They serve different purposes:

**Assets** are **templates** the skill expects to *include in its output*. Your `assets/runbook-template.md` is a markdown scaffold for change runbooks. When the skill produces a runbook, it follows this scaffold. Claude doesn't necessarily *read* the asset file every time — sometimes the body of SKILL.md just describes the structure inline. But having the canonical version in `assets/` means there's a single source of truth.

**Scripts** are **executable code** the skill bundles for deterministic tasks. Your `scripts/render_template.py` takes a Jinja2 template and a YAML inventory and produces device configs. Your `scripts/config_diff.py` produces a structural diff between two device configs. The idea: rather than have Claude regenerate this logic from scratch every time, you bundle a Python script and tell Claude to run it. This is more reliable (the script is the same every time), faster (running code is cheaper than generating equivalent output token-by-token), and saves context (the script can run without its source being loaded into context).

In your skill, the SKILL.md body mentions these scripts under "Templates and helpers" — that's the pointer that tells Claude they exist.

---

## 9. The two control flows: with-skill vs without-skill

This is the model you should hold when reasoning about whether your skill is *worth it*:

**Without the skill loaded.** User asks "how do I add VLAN 75 to Cisco?" Claude answers from its trained-in knowledge. Generally competent — Claude has read a lot of Cisco docs during training — but un-opinionated and inconsistent: rollback advice might be `no vlan 75`, or `copy backup running-config`, or `configure replace`, depending on what the model happens to surface.

**With the skill loaded.** Same query, but now Claude has read your operating principles ("changes are reviewed before they're pushed", "rollback artifact must be referenced in the runbook"), your Cisco reference file (which says use `configure replace` or `reload in` for safe rollback), and the runbook template. Output is more focused, more consistent, and avoids the unsafe `no vlan` style rollback.

That delta — what changes when the skill is in context — is what you're testing for in the evaluation step.

---

## 10. Why we ran an evaluation, and what it actually was

The eval loop compares the *with-skill* output to the *without-skill* output on the same prompts, so you can see whether the skill is actually pulling its weight or just adding noise.

Concretely, what we did:

1. **Wrote 4 test prompts** in `evals/evals.json`. Each prompt is a realistic question: "add VLAN 75 to two Catalyst 9300 switches", "eBGP won't establish between MX480 and ASR1001-X", etc.

2. **Wrote assertions** alongside each prompt. An **assertion** is a checkable statement about the expected output — "Output uses `switchport trunk allowed vlan add` (additive form)", "Address object uses IP-MASK form, not CIDR notation". Assertions are pass/fail, so you can produce a numerical pass-rate.

3. **Ran each test prompt twice**: once with Claude having access to the skill, once without. The without-skill run is the baseline — the comparison point.

4. **Graded each output** against its assertions. With the skill, all 25 assertions across 4 evals passed. Without, 22/25 passed. The 3 failures are concrete, real differences — places where the skill actively prevented a bug (FortiOS CIDR vs IP-MASK was a real one — that config wouldn't apply on a real FortiGate).

5. **Built an HTML viewer** so you could read each output side by side, see the assertion grades, and leave feedback. The feedback would have informed iteration 2 if you weren't satisfied.

The viewer used a feature called `localStorage` (per-browser persistent storage) so your feedback auto-saved as you typed.

---

## 11. The iteration loop — how skills get better

We didn't actually iterate (you said "all good"), but here's what would have happened:

1. You'd leave feedback in the textareas — "the BGP one is too long", "the rollback section in eval-1 misses the `reload cancel` step", whatever.
2. Click "Submit all reviews", which downloads `feedback.json`.
3. You drop that JSON back in the chat.
4. I read your specific complaints, **generalize** them into changes to the skill (not just patches to make those exact prompts pass), and rewrite SKILL.md or the references.
5. Re-run the same 4 prompts in `iteration-2/`.
6. Build a new viewer with `--previous-workspace` pointing at `iteration-1/` so you can see the diff in outputs.
7. Repeat until you're happy or the changes stop helping.

The key word in step 4 is **generalize**. The trap with iteration is to overfit: tweak the skill so the test prompts pass perfectly, but the skill becomes brittle on new prompts. The right move is to read the feedback as a *symptom* of a deeper issue and fix the deeper issue.

For example: if the user says "the rollback section forgot `reload cancel`", the bad fix is to hardcode `reload cancel` in the runbook template. The good fix is to update the operating principle around safety conventions to explain *why* `reload cancel` matters (it stops the dead-man timer), so Claude includes it whenever the situation calls for it — including on prompts that aren't in your test set.

---

## 12. Packaging — turning the folder into a `.skill` file

Cowork installs skills from a single file with the `.skill` extension. Inside, that file is a **ZIP archive**. ZIP is a 1989 file format that bundles multiple files into one, with optional compression. The ZIP file format spec defines a number of rules; two of them bit us:

- **Forward-slash path separators.** Inside a ZIP file, each entry has a path. The spec says paths must use `/` (forward slash). Windows uses `\` (backslash) for filesystem paths, and PowerShell's built-in `Compress-Archive` cmdlet writes paths with backslashes — which violates the spec. Some tools tolerate this, but the Cowork installer doesn't, which is why your first install attempt produced *"Zip file contains path with invalid characters"*. We fixed it by switching to .NET's `System.IO.Compression.ZipFile` API, which lets us specify the entry name explicitly with forward slashes.

- **No funny extensions.** `Compress-Archive` refuses to write to a file ending in anything other than `.zip`. The `.skill` extension is, again, just a renamed `.zip` — there's no different format. Our PowerShell script writes the zip with `.skill` as the extension by going around `Compress-Archive` and using the lower-level API directly.

The packaging script also **excludes** the `evals/` folder. You don't ship evals to end users — those were for your own development.

The structure of your `.skill` file, viewed as a zip, is:

```
network-automation/SKILL.md
network-automation/references/cisco.md
network-automation/references/juniper.md
... etc ...
```

Notice every entry starts with `network-automation/`. That's the convention: the zip contains a top-level folder named after the skill, and everything lives under it.

---

## 13. What happens during an install — the full sequence

When you drag `network-automation.skill` into Cowork, the install validator runs a series of checks. We hit two:

1. **Forward-slash paths** (the zip-spec compliance check).
2. **Description ≤ 1024 characters** (a rule on the YAML frontmatter, presumably to keep the available-skills list size manageable when you have many skills).

Other checks the validator likely runs (you can read `quick_validate.py` in the skill-creator scripts folder if curious): SKILL.md exists; YAML frontmatter parses; `name` field exists and matches the folder name; no path traversal in the zip (no `../etc/passwd` shenanigans).

If all checks pass, the validator extracts the contents to its managed skills directory, writes a record so Cowork knows the skill exists, and the next conversation you start will have it available.

---

## 14. End-to-end: a real query, traced step by step

Let's trace what happens when you type *"add VLAN 50 named Storage to my Catalyst 9300s, trunk to Po2"* into a Cowork chat *after* the skill is installed.

1. **You type the message.** Cowork sends it to Claude along with the system prompt (which includes your `network-automation` skill in the available skills list).

2. **Claude reads the message and the skill list.** It sees a description that mentions "add a VLAN" and "Cisco IOS-XE". It decides this is a query worth consulting the skill for.

3. **Claude calls the Skill tool with `name=network-automation`.** Cowork executes the tool, which reads `SKILL.md` from disk and returns the body.

4. **The body lands in Claude's context.** Now Claude is "reading" your operating principles, the request-shape table, the safety conventions, and the pointer to per-vendor references.

5. **Claude classifies the request.** Looking at the request-shape table, it identifies "single-device config snippet" / "multi-device template". Cisco-specific. The body says: read `references/cisco.md`.

6. **Claude calls its Read tool on `references/cisco.md`.** That file is loaded into context. Now Claude has Cisco syntax, the additive trunk pattern, the rollback affordances, and the gotchas list.

7. **Claude composes the answer.** It produces a config block for Cat 9300 with VLAN 50, names it Storage, modifies Po2 with `switchport trunk allowed vlan add 50`, includes verification commands (`show vlan brief`, `show interface Po2 trunk`), and a rollback recommendation using `configure replace` or `reload in`.

8. **You see the answer.** It's vendor-correct, safe, and structured the way the skill intended.

The skill never *executes* anything — it doesn't push config to your switches or talk to Cisco devices. It only shapes what Claude *says*. Execution is your job, by hand, with the output of the skill as a guide.

---

## 15. The two skill-creator scripts you should know about

The skill-creator plugin (which is what builds skills) ships with two scripts you might run later:

**`package_skill.py`** — does what your `package-skill.bat` does, but in Python: validate the skill, build the `.skill` zip, exclude development-only files. We replicated its logic in PowerShell because the Linux sandbox where Python runs wasn't available in our session.

**`run_loop.py` (the description optimizer)** — given a set of "should trigger" and "should not trigger" example queries, it iteratively rewrites your skill's description, tests how often Claude triggers the skill on each query, and converges on a description with the best trigger accuracy. This is useful once your skill body is solid and the only remaining question is *"is the description pulling Claude in at the right times?"* It needs the `claude` CLI to run, which means it doesn't work in Cowork-only setups today.

We didn't run the description optimizer because you accepted the skill as-is. If you ever want to: install Claude Code (the CLI), point the script at your skill folder and a JSON of example queries, and it'll churn for a while and produce a tuned description.

---

## 16. What can go wrong, and what we hit

A representative tour of pitfalls:

- **Description too long.** YAML frontmatter `description` >1024 chars → install rejects. Fix: tighten the prose, keep all the trigger phrases.

- **Description too vague or too narrow.** Claude doesn't trigger when it should (vague), or triggers only on exact phrasings (narrow). Fix: include realistic user phrases, list multiple synonyms, name vendor products. The "pushy" description language (*"even when they don't say automation"*) is for this.

- **Backslash zip paths.** PowerShell's default zipper produces non-spec zips. Fix: use `System.IO.Compression.ZipFile` directly with `entryName` containing forward slashes.

- **SKILL.md too long.** The body gets loaded into context every time the skill triggers. If it's 1000 lines of preamble, every trigger costs a lot of tokens. Fix: keep the body under ~500 lines, push detail into per-vendor / per-domain references that Claude reads on demand.

- **Reference files too large with no table of contents.** Claude reads them top-to-bottom and may stop before finding what it needs. Fix: front-matter table of contents, clear section headings.

- **Overfitting to test prompts during iteration.** You make eval-1 perfect by adding rules specific to eval-1's exact wording. The skill becomes brittle. Fix: read each piece of feedback as a *generalization opportunity*. Update operating principles, not specific patches.

- **Surprises in the bundle.** The skill installs and runs malicious or misleading content. Don't do this. The skill validation system isn't going to catch every bad pattern; the trust model assumes you're honest about what your skill does.

---

## 17. The mental model, finally

Strip everything else away and what you've got is:

A **skill** is a **folder of text files** (with a few helper scripts maybe). The folder gets packaged into a zip with a `.skill` extension. Cowork unzips it into a known location. From then on, Claude sees `(name, description)` for that skill in its system prompt, and on every user query decides whether to load the SKILL.md body — and from there, whether to load any per-domain reference files. The skill never executes anything; it just shapes Claude's text output.

You build a skill by writing the body in markdown the way you'd write a really good colleague-onboarding doc: state the principles, walk through the workflow, link out to the per-domain detail, define safety conventions. Then you measure whether the skill is actually changing Claude's behavior on realistic queries (the eval loop). Then you iterate based on feedback, generalizing each fix to apply beyond just the test prompts you happened to pick.

That's it. There's no fancier abstraction underneath.

---

## 18. What you have, concretely, after our session

In `C:\NETWORKAUTOMATION\CW_NetworkAutomation\`:

- `network-automation/` — the skill source folder (SKILL.md + references + assets + scripts + evals)
- `network-automation.skill` — the packaged installable file
- `package-skill.ps1` and `package-skill.bat` — the rebuild tools, double-clickable
- `network-automation-workspace/iteration-1/` — the test results: 4 evals × 2 conditions = 8 response files, plus `review.html` showing them side by side with assertion grades

To rebuild the `.skill` after editing the source: double-click `package-skill.bat`. That runs the PowerShell script, stages a clean copy in `%TEMP%`, zips it with proper forward-slash paths, and writes the new `.skill` next to the script.

To install: drag the `.skill` file into Cowork or use Settings → Skills → Install from file.

To verify it's working in a real chat after install: start a new conversation and ask something like *"document the failover for our edge firewalls"*. The skill should trigger and produce a runbook-shaped output.

---

## 19. If you're going to make more skills

Five rules of thumb from what we did:

1. **Pick the audience first.** "Network engineer at an enterprise" is a useful constraint — it tells you what acronyms not to expand, what level of vendor specificity to use, what assumptions about safety practices to make. A skill with no clear audience produces flabby instructions.

2. **Write the body before the description.** The description is an advertisement for the body. You can't write a good ad until you know what you're advertising.

3. **Push detail into references.** Anything that's vendor-specific, domain-specific, or only relevant in 20% of queries belongs in `references/<name>.md`, not in the main body.

4. **Run the eval loop before shipping.** Even a quick 3-prompt with-skill / without-skill comparison usually reveals at least one place where the skill isn't doing what you thought.

5. **Generalize feedback, don't patch test cases.** Every iteration should leave the skill more useful on prompts you *haven't* tried yet, not just on the prompts you have tried.

That's the whole craft.
