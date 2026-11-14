# Generalization in Adaptive Data Analysis and Holdout Reuse (Thresholdout)

Dwork, Feldman, Hardt, Pitassi, Reingold, Roth, 2015. arXiv 1506.02629 (companion: Science 2015 "The reusable holdout"; arXiv 1411.2664, not opened). Read via fetched PDF text, Section 4.1 and Figure 1.

- Thresholdout takes training set S_t, holdout S_h, threshold T, noise rate sigma, budget B. For each query phi in [0,1]: if |E_Sh[phi] - E_St[phi]| <= T_hat + eta, return the training value E_St[phi]; otherwise return E_Sh[phi] + xi and decrement B. When B < 1 it stops answering.
- Exact noise (Fig. 1): T_hat = T + gamma with gamma ~ Lap(2 sigma), resampled after each over-threshold event; eta ~ Lap(4 sigma); xi ~ Lap(sigma).
- Lemma 23: Thresholdout is (2B/(sigma n), 0)-differentially private, and (sqrt(32 B ln(2/delta))/(sigma n), delta)-DP. It is the sparse vector algorithm plus the Laplace mechanism, so the holdout leaks information only when the training and holdout answers disagree.
- Guarantee in words: the number of queries answerable is exponential in holdout size n provided the number that overfit is at most quadratic in n. The text uses T such as 0.01 as an example; defaults T = 4/sqrt(n), sigma = 1/sqrt(n) appear in the paper's supplementary code per R package docs (secondary source, not verified in the paper text).

Relevance to us: a simple holdout-reuse gate for many candidate hypotheses. Use phi = clipped, rescaled pinball-loss improvement; the budget B is the number of times a candidate is allowed to disagree with its training-origin score by more than T. Cheaper to implement than e-values but needs a holdout large enough that 1/sqrt(n) is small (n = number of origin-days).
