# I Let an AI Write 88% of My Code. Here's What Happened.

A few months ago I set out to build a fully autonomous AI-driven town simulation. Not as a job. Not for a startup. As a proof — to myself and anyone who looks at my GitHub — that I can ship a complex, real system. And I wanted to do it with an AI developer writing most of the code.

The result is **Qtown v1**: a 50x50 isometric town where NPCs eat, sleep, work, trade, commit crimes, vote in elections, and gossip — all without a single human writing their behavior. 1,451 commits. 550 stories shipped. 88% of the code written by an AI named Ralph.

Here's the full story.

---

## Why I Built This

I've been building software for a long time. I know what I'm capable of. But the industry doesn't take your word for it — they want to see it. A portfolio isn't a resume. A portfolio is running code.

I also wanted to answer a question I kept seeing debated online: *can an AI actually be a developer?* Not an autocomplete tool. Not a pair programmer you have to hand-hold through every decision. A developer. Someone (something) you hand a spec to and come back later to review a PR.

Qtown was the test environment. Ralph was the experiment.

---

## What Qtown Actually Is

Qtown v1 is a Python monolith: FastAPI for the API layer, SQLAlchemy as the ORM, a single Postgres database, and a PixiJS frontend rendering everything in an isometric grid.

Every 30 seconds, the tick loop fires. Every NPC in the simulation processes their state: are they hungry? Do they need sleep? Do they have a job shift? Is there someone nearby they want to gossip with? Do they have a grudge to settle? The tick loop is the heartbeat of the town. Everything flows through it.

The NPCs aren't scripted. They operate on a needs/goals/actions framework — each character has a set of needs (hunger, energy, social, money), and a decision engine that figures out what action best addresses their current state. They walk to the bakery, buy a loaf of bread, go home and eat it. They clock into their job at the lumber mill, earn wages, then spend those wages at the market. A character with low social stats might wander to the tavern. One with a criminal disposition and empty pockets might pick a pocket instead.

Elections happen. Factions form. Rumors spread across the social graph. An NPC who witnesses a crime will tell their friends, who tell their friends. The town has emergent politics.

None of this behavior was hand-coded action by action. It was designed at the systems level and implemented story by story.

---

## Ralph: The AI Developer

Ralph is the agent I built to actually write Qtown. He runs on Qwen 3.5:27b via Ollama — a local LLM, nothing cloud-based. The loop is simple by design:

1. **Read the spec.** Ralph gets a user story: *"As a town resident, I can purchase food from a vendor so that my hunger need is satisfied."*
2. **Generate the code.** He writes the implementation — models, routes, service logic, whatever the story requires.
3. **Run the tests.** If they fail, he reads the error, revises, and reruns. He keeps iterating until green or until he hits a loop limit.
4. **Commit.** Clean commit with a message referencing the story ID.
5. **Move to the next story.**

That's it. No magic. No complex planning system. No memory architecture. A tight loop with a clear success condition.

Ralph averaged **2.5 stories per day**, working autonomously. At peak he was shipping 4-5 stories in a session without me touching anything. Over the life of v1, he closed out the entire backlog: **550 of 550 stories**. The last forty took longer than the rest combined — they were the ones I'd deferred for being too architecturally tangled to delegate cleanly. Ralph eventually got them too, with more scaffold help on each one.

---

## The Numbers

Let me be concrete about the scale:

- **1,451 total commits**
- **88% of code written by Ralph**
- **550 of 550 stories completed**
- **30-second tick loop**
- **50x50 grid, fully simulated town**
- **One Postgres database, one Python monolith**
- **Zero cloud LLM costs** — fully local via Ollama

The 12% I wrote myself was mostly: the agent scaffold itself, the initial data model design, complex multi-system integrations where Ralph would hit a wall, and the isometric renderer setup with PixiJS. The architectural decisions were mine. The execution was largely Ralph's.

---

## What I Actually Learned

This is the part that matters. Not the demo. The lessons.

### The scaffold matters more than the model

Everyone obsesses over which LLM is best. GPT-4 vs. Claude vs. Gemini. I ran Ralph on a local 27B parameter model that you can run on a decent GPU. It's not GPT-4. It doesn't matter.

What matters is the scaffold — the loop, the context, the success condition. Ralph works because the loop is tight and the feedback is immediate. He writes code, runs tests, sees the output, fixes it. That's it. A smarter model in a bad scaffold produces worse results than a mediocre model in a clean loop.

If you're building AI dev tooling and you're spending 80% of your time on model selection, you're optimizing the wrong thing.

### Context window is king

The single biggest limiter for Ralph wasn't intelligence — it was context. When a story required touching five different modules, Ralph would sometimes lose track of earlier decisions by the time he got to the fifth file. The fix wasn't a bigger model. The fix was better context management: feeding Ralph exactly the files he needed, not the entire codebase.

A focused 4k-token context with the right information beats a bloated 100k-token context with everything dumped in. Relevance over volume.

### Simple loops beat complex agents

I see a lot of agentic frameworks that try to give AI developers long-horizon planning, memory systems, tool orchestration layers. Maybe that works at scale. For Qtown, the simple loop won every time.

Every time I added complexity to Ralph's scaffold — multi-step planning, reflection passes, self-critique loops — performance got worse, not better. More steps meant more ways to go off the rails. The tight read-write-test-commit loop with a single clear success criterion was the most reliable thing I built.

The lesson: if your AI agent loop is hard to explain, it's probably wrong.

### You still need to be the architect

Ralph can implement. He cannot design. He doesn't understand that the decision he made in story 47 will create debt in story 203. He doesn't think about what the data model implies for future features. He doesn't make judgment calls about what to cut.

That's the human job. I wrote the stories. I sequenced them. I caught the bad patterns before they spread. I made the calls about what Qtown actually needed to be versus what would have been fun to build.

AI-assisted development doesn't mean abdicating architectural responsibility. It means you get to spend more of your time on the problems that actually require judgment.

---

## What Broke

Not everything went smoothly. A few things Ralph genuinely struggled with:

**Long dependency chains.** If story B depended on a subtle design decision from story A that happened 200 commits ago, Ralph would sometimes re-implement the thing slightly differently, creating two approaches to the same problem in the codebase. I'd catch it in review and add a cleanup story.

**Stateful bugs.** The tick loop is stateful by nature. Bugs that only manifested after several ticks — race conditions, accumulating state problems, NPCs in impossible states — were hard for Ralph to reproduce and diagnose without significant context about the simulation's history.

**Novel system design.** The gossip/social graph system was one of the last features added, and it touched nearly every other system. Ralph could implement pieces of it, but the overall design required me sitting down and thinking through the data model carefully before handing anything off.

None of these are dealbreakers. They're just the edges of what the current scaffold handles well.

---

## What's Next: Qtown v2

Qtown v1 proved the concept. One developer, one AI agent, one monolith, one town.

v2 is a different kind of ambition.

I evolved Qtown into a polyglot microservices architecture where each neighborhood runs on a different tech stack — Go for the Market District, Rust for the Fortress, Python for the Academy's AI agents. 194 stories so far, 420 files, 12 languages. Kafka for event streaming. gRPC between services. GraphQL for the client API. Redis. Elasticsearch. 9 neighborhoods, each its own bounded context, each its own engineering philosophy. Ralph v2 runs five Ollama models now, routed by story type — heavy reasoning for architecture, fast coder for everyday work, debug specialist for race conditions.

v1 still runs at **[v1.qtown.ai](https://v1.qtown.ai)** as a live archive. You can watch the original simulation tick along — Helen the mayor, Garrett the merchant, the lumber mill, the bakery, the elections, the rumors. It's the proof that the whole thing was real.

**[qtown.ai](https://qtown.ai)** is the v2 home. While v2 is being finished, it's a coming-soon page that pulls live data from v1.qtown.ai so you can still see the simulation breathe. When v2 is ready, qtown.ai becomes the new front door.

But all of that's a story for the next post.

---

## Go Look at the Code

If you want to see what 1,451 commits of AI-assisted development actually looks like, the repo is open:

**[github.com/kbadinger/qtown](https://github.com/kbadinger/qtown)**

Read the commit history. Look at the story IDs in the commit messages. Check out the tick loop in `v1/engine/`. The v2 polyglot rewrite lives at the repo root in `services/`. If you're building something similar — an agent scaffold, a simulation, anything autonomous — I'm happy to talk through it.

Qtown v1 is done. It runs. It works. An AI wrote most of it.

That's the proof.
