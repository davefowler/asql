# BIRD-bench check-in, 2026-10-21

Scope: what changed on [bird-bench.github.io](https://bird-bench.github.io/)
and in the research around it since we last looked. Leaderboard numbers are
read from the site's source repo (`bird-bench/bird-bench.github.io` at
`d456580`, 2026-10-18), so they are the official tables, not press figures.
Paper details come from abstracts and secondary coverage; exact figures from
those are marked as such.

**Short version.** The official BIRD leaderboard has moved about one point in
a year. The action is in three other places: the single-model track (Google's
Gemini-SQL2), a credible argument that BIRD's labels are too noisy to rank
systems with, and the BIRD team's own pivot to agentic, contamination-free
successors (LiveSQLBench, BIRD-Interact, BIRD-Critic, BIRD 2.0).

## Leaderboard

Overall track (pipelines allowed), execution accuracy on the hidden test set,
oracle evidence on:

| Date | System | Org | Dev | Test | R-VES |
|---|---|---|---|---|---|
| | Human baseline (data engineers + DB students) | | | 92.96 | 83.26 |
| 2026-09-26 | GrainSQL | Sarim Chaudhry, Purdue | 77.77 | 82.95 | 84.10 |
| 2026-09-07 | DataGallery-Text2SQL | Huawei 2012 Labs | 78.10 | 82.39 | 77.64 |
| 2026-08-22 | SiriusAI-SQL | Tencent Data Computing Platform | 77.77 | 82.28 | 74.76 |
| 2025-12-16 | AskData + GPT-4o | AT&T CDO | 77.64 | 81.95 | 76.31 |
| 2025-09-25 | Agentar-Scale-SQL | Ant Group | 74.90 | 81.67 | 77.00 |
| 2026-06-19 | Sber Text2SQL | SberData Research | 75.74 | 81.33 | 73.75 |
| 2026-05-27 | Xiaomi Text2SQL | Xiaomi | 73.66 | 80.83 | 73.93 |

Single Trained Model track (one model, self-consistency allowed, no
pipeline; the team added this to compare training recipes fairly):

| Date | System | Size | Dev | Test |
|---|---|---|---|---|
| 2026-06-03 | Gemini-SQL2 (Google Research & Cloud) | ? | 74.12 | 80.04 |
| 2026-09-29 | ReToolSQL (JPMorganChase) | 31B | 74.77 | 78.14 |
| 2026-10-10 | SiriusAI-SQL-27B (Tencent) | 27B | 75.00 | 77.70 |
| 2026-03-12 | Gemini-SQL (multitask SFT on Gemini 2.5 Pro) | ? | 73.27 | 77.14 |
| 2026-10-10 | SiriusAI-SQL-9B (Tencent) | 9B | 74.90 | 77.08 |
| 2026-09-05 | Native mini | 4B | | 76.86 |
| 2025-12-04 | Q-SQL (AWS) | 30B-3B MoE | 72.99 | 76.47 |
| 2026-09-29 | flash-sqlite: Qwen3.5-2B + self-judge | 2B | 67.49 | 73.73 |
| 2026-04-28 | GPT-5.5-xhigh (baseline) | ? | | 72.55 |
| 2026-02-21 | Claude Opus 4.6 (baseline) | ? | 68.77 | 70.15 |
| 2026-02-21 | Qwen3-Coder-480B-A35B (baseline) | 480B | 66.17 | 68.14 |
| 2026-02-21 | Claude 4.5 Sonnet (baseline) | ? | 67.34 | 66.85 |

Mini-Dev (500 questions, three dialects) is mostly quiet; the only 2026
entries are small vendor submissions, the best being Jitto Build at 75.60 on
SQLite (2026-09-22) and Ontology2SQL at 70.20 SQLite / 65.80 PostgreSQL.

## What is new

### 1. The overall board has plateaued

Top score went from 81.67 (Sep 2025) to 82.95 (Sep 2026). The top five are
unpublished industrial pipelines (Huawei, Tencent, AT&T, Ant) plus GrainSQL,
which per its submission PR is one Purdue student calling Claude Opus 5
through the API with no fine-tuning. GrainSQL also tops the efficiency score
(R-VES 84.10, above the human 83.26). Nothing at the top is reproducible from
a paper. Huawei describes DataGallery as a semantic layer plus data agent with
multi-path schema linking (column and value retrieval, graph join-path
discovery, LLM coarse filtering, trial-and-error reverse extraction), then
multi-path generation, execution verification and confidence-based selection.

### 2. Gemini-SQL2 is the one real jump on the official site

80.04 on the single-model track, about 3.5 points over Q-SQL and 7 to 10
points over the raw GPT-5.5 and Claude Opus 4.6 baselines. Google published a
social post and nothing else: no paper, model card or API, so it cannot be
audited. The earlier Gemini-SQL was described in a Google Cloud blog as
multitask SFT on Gemini 2.5 Pro with aggressive training-data filtering.

### 3. The published recipe: RL with verifiable rewards plus DB tools on ~30B open models

ReToolSQL (JPMorgan, arXiv 2608.27796) is the clearest write-up: SFT warm-up
on rejection-sampled reasoning traces, then multi-turn agentic RL where the
model calls a sandboxed SQL executor, a column profiler and BM25 value
search, with schema-linking terms in a composite execution-anchored reward.
A dense 31B Gemma 4 reaches 78.14 test. Tencent's 9B/27B, Kuaishou's
14B/32B, Alibaba Security's 27B and a 2B Qwen3.5 self-judge entry follow
similar lines. A 2B model at 73.73 beating GPT-5.5 at 72.55 on this track
says how much task-specific training matters on BIRD.

### 4. The labels are broken (the biggest research story)

"Text-to-SQL Benchmarks are Broken: An In-Depth Analysis of Annotation
Errors" (Jin, Choi, Zhu, Kang; UIUC; CIDR 2026) audited BIRD Mini-Dev and
found annotation errors in 52.8% of examples: wrong gold SQL, question/schema
mismatch, missing or wrong external knowledge, ambiguous questions. Spider
2.0-Snow came in at 62 to 66% depending on the paper version. Re-scoring
leaderboard systems on corrected labels changes relative scores by up to 31%
and shifts ranks by several positions; the extended arXiv version
(2601.08778) re-scores 16 agents and reports rank changes from -9 to +9.
Rankings on the uncorrected subset track the full dev set; rankings on the
corrected subset only weakly do.

The BIRD team's response: `bird-sql-dev-1106`, a cleaned dev split (rows
using it are tagged "New Dev" on the board), and a planned interactive track
that removes Oracle Evidence entirely to handle ambiguity the way
BIRD-Interact does.

### 5. "Human-level" has been claimed, on corrected labels

ReViSQL (UIUC with Thinking Machines and Bridgewater AIA Labs; arXiv
2603.20004, "Human-Level Text-to-SQL via Reinforcement Learning on Verified
Data, Without Pipeline Engineering") argues data quality beats pipeline
engineering:

- BIRD-Platinum: ~2.5k expert-verified training examples. Training on it
  instead of raw BIRD Train gave 11 to 16 point gains on corrected BIRD and
  Spider 2.
- Execution-result rewards alone have a 32.8% false-positive rate, so they
  add SQL-equivalence verification and a process reward for actually using
  the external knowledge (models tend to ignore it).
- ReViSQL-K2.6, a LoRA fine-tune of Kimi K2.6 trained on Tinker, reports
  88.55 greedy and above the 92.96 human proxy with 16-sample
  self-consistency on Arcwise-Plat-SQL (Mini-Dev with corrected gold SQL,
  498 questions). Other write-ups quote 91.4 greedy / 93.0 SC; the versions
  disagree.

Caveats: it is not an official leaderboard number, the eval set is small, and
the human figure is from the original test set, not the corrected one. The
direction is consistent across sources even if the exact numbers are not.

### 6. The BIRD team has moved on from BIRD

Their news feed and roadmap (site updated 2026-10-09) are all about the
successor family:

- **LiveSQLBench**: contamination-free PostgreSQL, periodic releases.
  Large-v1 (2026-03-03) has ~1K columns and ~54 tables per DB, 480 tasks,
  ~84K-token prompts, and "business rule drift" where external knowledge
  changes between releases. Top of the board is C3 AI's Data Intelligence
  Agents at 48.0 success rate, then Claude Opus 5.5 setups around 41. A
  Harbor-based CLI harness (2026-04-04) evaluates terminal agents directly.
  1.5 is "coming soon" (new task formats, document-based knowledge); 2.0 is
  under development and explicitly targets semantic modeling: extracting
  business knowledge from documents, wikis and historical queries, grounding
  it in schemas, and building reusable semantic models.
- **BIRD-Interact**: ICLR 2026 oral. At paper time GPT-5 scored 8.67%
  success on conversational (c-Interact) and 17.00% on agentic (a-Interact)
  over the full task set. AtScale claims 56.6% on a semantic-layer setup
  (unverified, different protocol).
- **BIRD-Critic-SQLite** (2026-03-23): 500 real SQLite user issues plus
  RL-trained BIRD-Talon-14B/7B and BIRD-Zeno-7B. **Effi-SQL** (June 2026):
  300 slow/fast pairs scoring query efficiency.
- **Data Intelligence Index** (2026-03-06, v0.3 May 2026): aggregate score
  across querying, BI, debugging, interaction and multimodal tasks, with Base
  Mode vs Agent Mode. v1.0 in Harbor format is in progress.
- **BIRD 2.0**: "under development" to evaluate agents across broader
  industrial data scenarios. No details yet.

Spider 2.0 for context: the Snow track tops out above 96 (Genloop, Native),
and its labels have the same audit problem.

## Takeaways for asql

- Single-shot text-to-SQL on BIRD is treated as solved-enough on a noisy
  target. The frontier is large schemas, interaction, debugging, efficiency,
  and semantic-layer grounding. LiveSQLBench 2.0's semantic-modeling focus
  and Huawei's semantic-layer architecture are the closest to what asql
  is for.
- Expect the official human baseline to fall within a year, most likely on
  corrected dev sets first, and the claims to be contested on label quality.
- If we ever benchmark asql-assisted generation, use the corrected sets
  (Arcwise-Plat-SQL in the ReViSQL repo, or `bird-sql-dev-1106`), and report
  R-VES alongside EX since efficiency is now on the board.
- The two systems with real method write-ups and code are ReToolSQL and
  ReViSQL. Everything above them on the board is a black box.

## Sources

- Leaderboard source: https://github.com/bird-bench/bird-bench.github.io
  (GrainSQL PR #237, SiriusAI-SQL PR #244)
- Gemini-SQL2: Google Research post
  https://x.com/GoogleResearch/status/2065475343205740911; coverage at
  https://the-decoder.com/google-researchs-gemini-sql2-tops-text-to-sql-benchmarks-by-a-wide-margin/;
  earlier recipe at
  https://cloud.google.com/blog/products/databases/techniques-for-improving-text-to-sql
- ReToolSQL: https://arxiv.org/abs/2608.27796
- Annotation errors: https://www.vldb.org/cidrdb/papers/2026/p5-jin.pdf and
  https://arxiv.org/abs/2601.08778
- ReViSQL: https://arxiv.org/abs/2603.20004, code and Arcwise-Plat sets at
  https://github.com/uiuc-kang-lab/ReViSQL, write-up at
  https://thinkingmachines.ai/news/putting-task-expertise-into-rl/
- LiveSQLBench: https://livesqlbench.ai/, https://github.com/bird-bench/livesqlbench
- Data Intelligence Index: https://livesqlbench.ai/data-intelligence-index/
- BIRD-Interact: https://arxiv.org/abs/2510.05318
- BIRD-Critic: https://bird-critic.github.io/
- Data Intelligence Agents (C3 AI): https://arxiv.org/abs/2606.19319
- Agentar-Scale-SQL: https://arxiv.org/abs/2509.24403
- DataGallery coverage:
  https://technologymagazine.com/news/huawei-datagallery-tops-benchmark-for-enterprise-text2sql-ai
