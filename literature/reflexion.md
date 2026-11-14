# Reflexion: Language Agents with Verbal Reinforcement Learning

2023 (author list not checked in this session). arXiv 2303.11366. Read from local LaTeX (main.tex).

- Mechanism: after each trial a self-reflection model turns the trajectory and a success or fail signal into a short verbal lesson, appended to an episodic memory buffer used as context next trial. The buffer is bounded to Omega stored experiences, usually 1 to 3, because of context limits. Trajectory history is short-term memory; reflections are long-term memory. No weight updates.
- Results (as stated in the text): 91 percent pass@1 on HumanEval; an absolute 22 percent improvement over strong baselines on ALFWorld in 12 iterative learning steps.
- Limitations section exists (line 745); the practical limits it names concern test-driven code generation (unreliable tests, non-determinism); I did not read it fully.

Relevance to us: a bounded verbal lessons file (last 1 to 3 per hypothesis family) is the simplest carry-over mechanism; pair it with the external gate because reflection alone has no guard against self-confirming lessons.
