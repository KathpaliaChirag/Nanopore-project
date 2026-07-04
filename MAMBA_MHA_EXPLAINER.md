# Mamba as MHA — A Study Guide From Zero

**Who this is for:** you have no ML background. Every term is defined the first time it's used. Nothing here assumes you've seen a neural network before.

**What this is for:** the project has pivoted from profiling Dorado/Kraken2 (see `dorado-kraken-research/`) to a new direction — reformulating **Mamba** (a newer sequence-model architecture) so it computes things in the same *shape* as **MHA** (multi-head attention, the operation inside every Transformer), because chips are built to run that shape fast. This document builds up the knowledge to understand *why* that's a meaningful thing to do, and *how* it's actually proven to be possible — not just asserted.

**How to use this document:** read top to bottom, in order — each chapter needs the one before it. Every code block is real, runnable Python (`pip install numpy` is the only dependency for Chapters 1–5; Chapter 6 mentions PyTorch as an optional next step). Copy them into a file or a Jupyter/Colab cell and actually run them — the point of embedding code isn't decoration, it's so you can watch the concept work with real numbers instead of taking it on faith.

**The 6-chapter arc** (this is the "researcher's path" — each chapter is one layer of understanding, building on the last):

| # | Chapter | What you'll be able to say afterward |
|---|---|---|
| 1 | Foundations | "I know what a tensor, a layer, and a forward pass are." |
| 2 | RNN vs. Attention | "I know the two classic ways to process a sequence, and why one parallelizes and the other doesn't." |
| 3 | MHA in depth | "I know exactly what Q/K/V are, why chips are fast at attention, and what FlashAttention does." |
| 4 | State Space Models & Mamba | "I know what Mamba actually computes, and why it's fast in theory but not always in practice." |
| 5 | **The Duality Proof** | "I can show, with running code, that a Mamba-style recurrence and an attention-shaped matrix multiply produce *the exact same numbers*." |
| 6 | From proof to practice | "I know the concrete next steps, the open decisions, and what to read next." |

Chapter 5 is the centerpiece — it's the actual mathematical justification for "Mamba as MHA," demonstrated numerically, not just described in prose.

---

## Chapter 1 — Foundations: what is a neural network doing to a sequence?

### 1.1 Vectors, matrices, and "shape"

A **vector** is just a list of numbers. A **matrix** is a grid of numbers (rows × columns). In ML code you'll see the word **tensor** used generically for "a grid of numbers with some number of dimensions" — a vector is a 1-D tensor, a matrix is a 2-D tensor, and stacks of matrices are 3-D+ tensors. When people say a tensor has "shape `(5, 4)`," they mean 5 rows and 4 columns — nothing more mystical than that.

### 1.2 What is a "sequence" here?

Nanopore sequencing produces a long stream of electrical signal measurements over time. The basecaller's job is: given this stream, output a sequence of predicted bases (A/C/G/T). That's a **sequence-to-sequence** problem — the input is an ordered list of things, the output is an ordered list of things, and *order matters* (shuffling the signal would produce garbage).

The exact same mathematical shape shows up in text (a sentence is a sequence of words) and in almost every other domain (video = sequence of frames, audio = sequence of samples). This is why "how do you process a sequence efficiently and well" is one of the central questions in modern ML, and why the answer matters just as much for nanopore signal as it does for language models.

### 1.3 A "layer" is just a function with learned numbers in it

The simplest possible layer is a **linear layer**: it takes an input vector and produces an output vector by multiplying by a matrix of numbers (called **weights**, usually written `W`) and adding a vector of numbers (called a **bias**, `b`). Those weight/bias numbers are what "training" tunes — but we are not going to train anything in this document. We only care about the *shape of the computation* (how many multiplications, in what pattern, on what hardware), because that's what determines speed. So every code example below only needs a **forward pass** (run the computation once with made-up numbers) — never training.

```python
import numpy as np
np.random.seed(0)

# A "token" here is just a vector of numbers (an embedding).
# Say each token is represented by 4 numbers, and we have a sequence of 5 tokens.
seq_len, dim = 5, 4
x = np.random.randn(seq_len, dim)   # shape (5, 4): our toy input sequence

# A linear layer: output = x @ W + b   ("@" is matrix multiplication in numpy/Python)
W = np.random.randn(dim, dim) * 0.1  # learned weights (random here, since we're not training)
b = np.zeros(dim)                    # learned bias

def linear(x, W, b):
    return x @ W + b

y = linear(x, W, b)
print("input shape: ", x.shape)   # (5, 4)
print("output shape:", y.shape)   # (5, 4)
```

Run this. You now have the smallest possible neural-network layer, applied to a toy 5-token sequence. Everything from here is: *what do you do between layers to let information flow between the 5 positions?* That question is the entire subject of this document.

---

## Chapter 2 — Two classical answers: RNN and Attention

If every layer only looked at one position at a time (like the linear layer above, applied independently to each row), position 3 could never know anything about position 1. Something has to let information flow *across* positions. Historically there have been two dominant answers.

### 2.1 RNN (recurrent neural network) — carry a running summary forward

An RNN keeps a **hidden state** (a running summary vector) and updates it one step at a time:

```python
def simple_rnn(x, Wx, Wh, h0=None):
    """
    x:  (T, dim_in)      input sequence
    Wx: (dim_in, dim_hidden)
    Wh: (dim_hidden, dim_hidden)
    Returns hs: (T, dim_hidden) — the hidden state at every time step
    """
    T = x.shape[0]
    dim_hidden = Wh.shape[0]
    h = np.zeros(dim_hidden) if h0 is None else h0
    hs = []
    for t in range(T):
        h = np.tanh(x[t] @ Wx + h @ Wh)   # <-- needs the PREVIOUS h. Cannot be skipped or reordered.
        hs.append(h)
    return np.stack(hs)

T, dim_in, dim_hidden = 6, 4, 8
x = np.random.randn(T, dim_in)
Wx = np.random.randn(dim_in, dim_hidden) * 0.1
Wh = np.random.randn(dim_hidden, dim_hidden) * 0.1

hs = simple_rnn(x, Wx, Wh)
print(hs.shape)  # (6, 8)
```

Notice the `for t in range(T)` loop. Step `t` needs the result of step `t-1`. **This is the important part**: no matter how many parallel processors you throw at this, you cannot compute step 500 before step 499 finishes — the computation is *inherently sequential in time*. This is exactly the property that makes RNNs (and, as you'll see in Chapter 4, Mamba) hard to run fast on hardware that wants to do thousands of things at once.

### 2.2 Attention — every position looks at every other position, all at once

**Self-attention** takes a completely different approach: for each position, compute how much it should "pay attention to" every other position, and produce a weighted combination. Concretely, each token produces three vectors via three learned projections:

- **Query (Q)** — "what am I looking for?"
- **Key (K)** — "what do I contain, for others to match against?"
- **Value (V)** — "what do I actually offer, if I get picked?"

```python
def self_attention(x, Wq, Wk, Wv, causal=True):
    """
    x: (T, dim)
    Wq, Wk, Wv: (dim, dim) projection matrices
    """
    T, dim = x.shape
    Q = x @ Wq   # (T, dim) — "what am I looking for"
    K = x @ Wk   # (T, dim) — "what do I contain"
    V = x @ Wv   # (T, dim) — "what do I offer if picked"

    scores = Q @ K.T / np.sqrt(dim)   # (T, T): raw similarity between EVERY pair of positions, all at once

    if causal:
        # In autoregressive tasks (predicting the next thing), position t must not see the future (t+1, t+2, ...).
        # This mask forces those scores to -infinity so they vanish after softmax below.
        mask = np.triu(np.ones((T, T)), k=1).astype(bool)
        scores = np.where(mask, -np.inf, scores)

    # softmax: turn each row of raw scores into weights that are positive and sum to 1
    scores = scores - scores.max(axis=-1, keepdims=True)   # for numerical stability, doesn't change the result
    weights = np.exp(scores)
    weights = weights / weights.sum(axis=-1, keepdims=True)

    out = weights @ V   # (T, dim): each position's output is a weighted blend of ALL Values
    return out, weights

T, dim = 6, 8
x = np.random.randn(T, dim)
Wq = np.random.randn(dim, dim) * 0.1
Wk = np.random.randn(dim, dim) * 0.1
Wv = np.random.randn(dim, dim) * 0.1

out, weights = self_attention(x, Wq, Wk, Wv)
print(out.shape)      # (6, 8)
print(weights.shape)  # (6, 6) — the attention matrix: weights[t, s] = how much position t attends to position s
```

There is **no `for t in range(T)` loop** in the actual computation (`Q @ K.T`, the mask, and `weights @ V` are each one shot, all positions at once). Every position's relationship to every other position is computed in one matrix multiply. This is the crucial difference from the RNN.

### 2.3 The fundamental trade-off

| | RNN | Attention |
|---|---|---|
| Cost per sequence | O(T) — grows linearly with length | O(T²) — grows quadratically (the `(T,T)` scores matrix) |
| Sequential steps required | O(T) — must do them one after another | O(1) — the whole thing is one parallel operation |
| Hardware fit | Poor — GPUs want thousands of parallel operations, not a loop of T dependent steps | Excellent — the whole thing is matrix multiplication, which is exactly what GPUs are built for |

This is the whole story in miniature: **attention costs more arithmetic (O(T²)) but that arithmetic is trivially parallel and hardware-friendly; RNNs cost less arithmetic (O(T)) but that arithmetic is stubbornly sequential.** Mamba (Chapter 4) is a modern attempt to get RNN-like O(T) cost with attention-like modeling quality — and the subject of this whole document (Chapter 5) is a proof that, under the right conditions, you can compute *that same O(T) result* using the *O(T²) attention-shaped arithmetic* instead — trading some extra arithmetic for a hardware-friendly shape, exactly when that trade is worth it.

---

## Chapter 3 — Multi-Head Attention (MHA) in depth, and why chips are built for it

### 3.1 "Multi-head" — why more than one attention pattern?

A single attention computation (Chapter 2) produces one weighting pattern per position. **Multi-head attention** splits the embedding dimension into several smaller chunks ("heads") and runs independent attention computations on each chunk in parallel, then concatenates the results. Intuitively: one head might learn to track "which earlier position had a similar signal shape," another might track "distance from the previous position," etc. — different heads can specialize in different kinds of relationships, computed side by side.

```python
def multi_head_attention(x, num_heads, Wq, Wk, Wv, Wo, causal=True):
    T, dim = x.shape
    head_dim = dim // num_heads
    Q = (x @ Wq).reshape(T, num_heads, head_dim)
    K = (x @ Wk).reshape(T, num_heads, head_dim)
    V = (x @ Wv).reshape(T, num_heads, head_dim)

    outputs = []
    for h in range(num_heads):   # this loop is only over a SMALL, FIXED number of heads (e.g. 8) — not over T
        scores = Q[:, h] @ K[:, h].T / np.sqrt(head_dim)
        if causal:
            mask = np.triu(np.ones((T, T)), k=1).astype(bool)
            scores = np.where(mask, -np.inf, scores)
        scores = scores - scores.max(axis=-1, keepdims=True)
        weights = np.exp(scores)
        weights = weights / weights.sum(axis=-1, keepdims=True)
        outputs.append(weights @ V[:, h])

    concat = np.concatenate(outputs, axis=-1)  # (T, dim) — heads stitched back together
    return concat @ Wo                          # final learned mixing of the heads' outputs

T, dim, num_heads = 6, 8, 2
x = np.random.randn(T, dim)
Wq = np.random.randn(dim, dim) * 0.1
Wk = np.random.randn(dim, dim) * 0.1
Wv = np.random.randn(dim, dim) * 0.1
Wo = np.random.randn(dim, dim) * 0.1

out = multi_head_attention(x, num_heads, Wq, Wk, Wv, Wo)
print(out.shape)  # (6, 8)
```

**Important:** the loop over heads is over a small, *fixed* number (commonly 8, 16, 32 — a hyperparameter chosen by the model designer), never over the sequence length `T`. So it doesn't reintroduce the "must wait for the previous step" problem — all heads, and all positions within each head, are independent of each other and can run in parallel.

### 3.2 Why chips are fast at this: it's all matrix multiplication (GEMM)

Every expensive step above — `Q @ K.T`, `weights @ V`, and the input projections `x @ Wq` etc. — is a **GEMM** (General Matrix Multiply). This is the single most optimized operation in computing:

- GPUs contain dedicated **tensor cores** (since NVIDIA's Volta generation) — specialized circuits whose entire job is multiply-accumulate operations at the heart of GEMM.
- Decades of vendor libraries (cuBLAS, CUTLASS on NVIDIA; equivalents elsewhere) exist purely to make GEMM as fast as physically possible on a given chip.
- Because MHA reduces to GEMM, it gets all of this for free — no custom kernel required, just calls into infrastructure that already exists and is already fast.

**FlashAttention** (Dao et al., 2022) is worth knowing about here: naively, the `(T, T)` scores matrix has to be written out to the GPU's slow main memory (VRAM) and read back for the softmax and the next matmul — for long sequences this memory traffic, not the arithmetic, becomes the bottleneck. FlashAttention restructures the computation to process small tiles of the sequence at a time, keeping everything inside the GPU's small but very fast on-chip memory (SRAM), and never materializing the full `(T,T)` matrix in slow memory. Same math, same output — just organized to respect the chip's memory hierarchy. This "reorganize the computation to fit the chip's memory hierarchy, without changing the math" idea will come back in Chapter 6 as exactly the trick that makes Mamba-2 fast.

### 3.3 Closing the loop on Kolin sir's original question

Back in an earlier meeting (see `dorado-kraken-research/docs/meeting_minutes.md`, Meeting 5), the assigned research question was: *"is NVIDIA GPU hardware designed to accelerate MHA, or does MHA happen to map well to existing GEMM units?"*

Having gone through §3.2: the honest answer is **mostly the latter, increasingly also the former.** Attention was not originally designed with dedicated hardware in mind — it happened to reduce to GEMM, and GEMM already had a decade of hardware and software investment behind it from other domains (graphics, scientific computing, other neural nets). But the causality has started running the other way in the newest chip generations: NVIDIA's Hopper and Blackwell GPUs include "transformer engine" features and FP8 numeric formats specifically tuned for the kinds of workloads Transformer/attention models produce. So the field went: *attention happened to be fast on existing hardware* → *attention proved dominant* → *hardware vendors then started co-designing for it specifically.* This is precisely the pattern this project wants to replicate for Mamba: if Mamba's computation can be reshaped into that same GEMM-friendly form, it gets to ride the same wave of hardware investment.

---

## Chapter 4 — State Space Models (SSMs) and Mamba

### 4.1 A 30-second detour into control theory

Long before neural networks, engineers modeling physical systems (circuits, mechanical systems) used **state space models**: a continuous equation describing how an internal "state" evolves over time and produces an output.

```
dx/dt = A x(t) + B u(t)      <- how the internal state x changes over time, given input u
y(t)  = C x(t)                <- how the state produces an observable output y
```

`A`, `B`, `C` are matrices. This has nothing to do with ML originally — it's classical control/systems theory. The insight that revived it for ML (in a line of work called S4, then Mamba) is: **discretize** this continuous equation (turn it into steps, the way you'd numerically simulate any differential equation) and you get:

```
h_t = Ā h_{t-1} + B̄ x_t
y_t = C h_t
```

**This is exactly the RNN recurrence from Chapter 2**, just derived from a different (control-theoretic) starting point, with a particular, carefully-chosen structure for the matrices. So an SSM, once discretized, *is* a specific kind of linear RNN.

### 4.2 Why bother — long-range memory

Plain RNNs (Chapter 2) suffer from the **vanishing gradient problem**: information from far in the past gets diluted/lost as it's repeatedly multiplied through the recurrence, especially over long sequences (like a 700 MB nanopore signal file). The S4 line of work found a specific, carefully derived initialization for the `A` matrix (based on something called **HiPPO** — High-order Polynomial Projection Operators, a technique for compressing history into a fixed-size state so as to lose as little information as mathematically possible) that lets these SSMs remember information over very long sequences much better than a naively-initialized RNN. But the original S4 model has one big limitation: `A`, `B`, `C` are **fixed** — the same for every input, learned once during training and then frozen. It cannot decide, on the fly, "this part of the input is unimportant, forget it faster" or "this part matters a lot, remember it."

### 4.3 Mamba's innovation: make it *selective*

**Mamba** (Gu & Dao, 2023) is exactly the S4 idea, with one key change: it makes the discretization parameters — critically, the "how much to forget" behavior (via a parameter usually called `Δ`, delta) — **depend on the current input**, not fixed. This is called a "selective" SSM (sometimes labeled "S6" in the literature). Concretely, `B_t`, `C_t`, and `Δ_t` (and therefore the effective `Ā_t`) are computed from the current input token itself, rather than being the same constants at every position.

This closes much of the modeling-quality gap with attention (the model can now behave differently depending on content, the same way attention's Q/K/V comparisons are content-dependent) while keeping the O(T) linear-time recurrence structure. That's the promise of Mamba: attention-like modeling quality, RNN-like linear cost.

```python
def selective_ssm_recurrence(x, a, b, c):
    """
    A minimal, single-channel (scalar-state) selective SSM, computed the native/sequential way.

    x: (T,) input sequence (one scalar channel, for simplicity — real Mamba runs many channels in parallel)
    a, b, c: (T,) TIME-VARYING parameters. In real Mamba these are themselves computed from x
             (that's what "selective" means) — here we just supply them directly to keep the demo simple.
        a_t in (0, 1): how much of the previous state to KEEP     ("forget gate"-like)
        b_t:           how much of the new input to WRITE into the state
        c_t:           how much of the state to READ OUT as output
    """
    T = x.shape[0]
    h = 0.0
    hs, ys = [], []
    for t in range(T):
        h = a[t] * h + b[t] * x[t]   # <-- update the running summary. Sequential: needs h from step t-1.
        y = c[t] * h                  # <-- produce this step's output from the current summary
        hs.append(h)
        ys.append(y)
    return np.array(ys), np.array(hs)

T = 8
x = np.random.randn(T)
a = np.random.uniform(0.5, 0.9, size=T)   # kept between 0 and 1 so the state doesn't blow up or vanish immediately
b = np.random.randn(T)
c = np.random.randn(T)

y, h = selective_ssm_recurrence(x, a, b, c)
print(y)
```

(Real Mamba uses a *vector*-valued state per channel — typically 16–64 numbers, not a single scalar — and dozens to thousands of independent channels running in parallel, each with its own `a, b, c`. We use a single scalar here purely so the arithmetic is simple enough to see clearly. Chapter 6 has an exercise to extend this.)

### 4.4 Why Mamba is still often not as fast as its O(T) suggests

Look at the `for t in range(T)` loop above again — it's the same sequential dependency problem as the plain RNN in Chapter 2. Mamba's original paper solves this with a clever trick called a **parallel scan** (or "associative scan"): because the recurrence has a specific mathematical structure (it's what's called an *associative* operation), you can restructure the sequential computation into a tree of parallel operations, similar in spirit to how parallel prefix-sum algorithms work. This is a genuine, real speedup over the naive loop — but:

- It's a **bespoke, custom kernel**. It doesn't reduce to GEMM. It requires writing and maintaining dedicated CUDA code (or equivalent) per chip family.
- It has not received anywhere near the decades of vendor tuning that GEMM has.
- Every new chip generation needs someone to re-tune or rewrite this scan kernel; GEMM-based code, by contrast, benefits automatically from vendor library improvements.

This is the entire motivation for this project: **if you could compute the same result Mamba wants, but expressed as GEMM (the way attention already does), you'd inherit all of that hardware investment for free — no custom scan kernel needed.** Chapter 5 shows this is not wishful thinking; it's provably possible, under specific conditions.

---

## Chapter 5 — THE PROOF: Mamba and Attention are the same computation

This is the mathematical heart of "implement Mamba as MHA." The result is called **State Space Duality (SSD)**, from the paper *"Transformers are SSMs"* (Dao & Gu, 2024 — the "Mamba-2" paper). We'll derive a simplified version of it by hand, then verify it with running code.

### 5.1 The restriction we need

The exact duality proof in the Mamba-2 paper applies to a **structured** SSM where the state-transition at each step is a scalar times the identity matrix (`A_t = a_t · I`), rather than the fully general per-channel matrix that the original Mamba (S6) allows. This is a real, honest trade-off — Mamba-2 gives up a bit of per-channel expressiveness (in exchange, it typically uses many more, smaller "heads," similar in spirit to MHA's heads) in order to make this exact duality hold and be exploitable. Our scalar-state toy SSM from §4.3 is already exactly this restricted form, which is why we can derive the duality directly from it.

### 5.2 Unrolling the recurrence by hand

Recall the recurrence (0-indexed, `h` starts at 0 before the first step):

```
h_t = a_t h_{t-1} + b_t x_t
y_t = c_t h_t
```

Unroll it for the first few steps:

```
h_0 = b_0 x_0
h_1 = a_1 h_0 + b_1 x_1              = a_1 b_0 x_0 + b_1 x_1
h_2 = a_2 h_1 + b_2 x_2              = a_2 a_1 b_0 x_0 + a_2 b_1 x_1 + b_2 x_2
```

The pattern: `h_t = Σ_{s=0}^{t} (a_{s+1} a_{s+2} ... a_t) · b_s · x_s` (the product of `a`'s is empty, i.e. equal to 1, when `s = t`). So:

```
y_t = c_t h_t = Σ_{s=0}^{t} [ c_t · (a_{s+1}...a_t) · b_s ] · x_s
```

**Stop and look at this shape.** This says: `y_t` is a weighted sum over *all earlier positions* `s ≤ t`, where the weight depends on both `t` and `s`. That is *exactly* the shape of masked (causal) attention from Chapter 2 (`y = weights @ V`, with `weights[t,s] = 0` for `s > t`) — just with a different formula for the weights than "softmax of Q·K". Define a matrix `L` where:

```
L[t, s] = c_t · (a_{s+1} · a_{s+2} · ... · a_t) · b_s     for s ≤ t
L[t, s] = 0                                                for s > t
```

Then `y = L @ x` — a single matrix-vector multiply, exactly the GEMM-shaped computation Chapter 3 discussed.

### 5.3 A trick to compute the products efficiently

Computing `a_{s+1} · ... · a_t` freshly for every `(t, s)` pair would itself cost O(T²) work just for the products. There's a standard trick: define the **cumulative product** `P_t = a_0 · a_1 · ... · a_t`. Then:

```
a_{s+1} · a_{s+2} · ... · a_t = P_t / P_s
```

(You can check this: `P_t / P_s = (a_0...a_t) / (a_0...a_s) = a_{s+1}...a_t`. It even works cleanly at `s = t`, giving `P_t/P_t = 1`, matching the "empty product" case.) So:

```
L[t, s] = c_t · b_s · (P_t / P_s)     for s ≤ t
```

### 5.4 The code: three forms, same numbers

Here is the complete, runnable demonstration — the actual numerical proof, not just a description of one.

```python
import numpy as np
np.random.seed(42)

T = 8
x = np.random.randn(T)
raw = np.random.randn(T)
a = 1 / (1 + np.exp(-raw)) * 0.5 + 0.4   # squash into roughly (0.4, 0.9): keeps 'a' comfortably away from 0 or 1
b = np.random.randn(T)
c = np.random.randn(T)

# ---- Form 1: sequential recurrence — what Mamba computes NATIVELY ----
def recurrence_form(x, a, b, c):
    T = len(x)
    h = 0.0
    y = np.zeros(T)
    for t in range(T):
        h = a[t] * h + b[t] * x[t]
        y[t] = c[t] * h
    return y

# ---- Form 2: cumulative-sum rearrangement — same math, still O(T), no explicit matrix ----
def cumsum_form(x, a, b, c):
    P = np.cumprod(a)          # P[t] = a[0] * a[1] * ... * a[t]
    w = b * x / P               # rescale each input by how much it will have "decayed" by the end
    running = np.cumsum(w)      # running total up to each position
    y = c * P * running
    return y

# ---- Form 3: explicit masked matrix — the MHA-SHAPED form (this is the "attention" version) ----
def attention_form(x, a, b, c):
    T = len(x)
    P = np.cumprod(a)
    L = np.zeros((T, T))
    for t in range(T):
        for s in range(t + 1):          # causal: only s <= t contributes
            L[t, s] = c[t] * b[s] * (P[t] / P[s])
    y = L @ x                            # <-- ONE matrix-vector multiply. This is the GEMM-shaped computation.
    return y, L

y_rec        = recurrence_form(x, a, b, c)
y_cum        = cumsum_form(x, a, b, c)
y_att, L     = attention_form(x, a, b, c)

print("recurrence output:         ", np.round(y_rec, 4))
print("cumsum-form output:        ", np.round(y_cum, 4))
print("attention-form output:     ", np.round(y_att, 4))
print()
print("recurrence == cumsum?      ", np.allclose(y_rec, y_cum))
print("recurrence == attention?   ", np.allclose(y_rec, y_att))
print()
print("the implicit 'attention matrix' L (lower-triangular = causal):")
print(np.round(L, 3))
```

Run this. All three `y` outputs will be numerically identical (`np.allclose` will print `True` for both comparisons). **This is the whole point, demonstrated rather than asserted**: the same Mamba-style selective SSM can be computed as a sequential recurrence (what Mamba does today), or as one matrix multiply against an implicit causal attention-like matrix `L` (the MHA-shaped form this project wants to exploit).

### 5.5 What `L` actually is, and an honest caveat

`L` has a special structure mathematically called **1-semiseparable** — every entry below the diagonal is expressible as a product of a "row factor" (`c_t · P_t`) and a "column factor" (`b_s / P_s`), rather than being T² independent free numbers. This structure is *why* the matrix can be built and multiplied efficiently, and it's the same structural fact the Mamba-2 paper exploits for its practical chunked algorithm (Chapter 6).

**Important honest caveat:** `L` is *not* the same kind of object as the softmax attention matrix from Chapter 2. Transformer attention weights are normalized (softmax makes each row sum to 1, and all weights are non-negative). `L` here has no such normalization — its entries can be any sign or magnitude, driven by the products of `a`, `b`, `c`. It is "attention-shaped" (causal, weighted sum over earlier positions, computable as one matmul) but not "softmax attention." A separate, related paper — *"The Hidden Attention of Mamba Models"* (Ali et al., 2024) — does something similar for the fully general (non-restricted) original Mamba and is aimed mainly at *interpretability* (letting you visualize what a Mamba layer is "attending to," analogous to attention-map visualizations for Transformers) rather than at the efficiency goal this project cares about. Worth reading, but Mamba-2's SSD is the right target for the hardware-efficiency angle.

---

## Chapter 6 — From proof to practice

### 6.1 Mamba-2's real algorithm: chunking, the best of both worlds

Chapter 5's Form 3 costs O(T²) — fine for a toy `T=8` example, bad for a real nanopore signal with hundreds of thousands of samples. Mamba-2's actual implementation doesn't pick purely Form 1 (cheap but sequential) or purely Form 3 (parallel but quadratic) — it **chunks** the sequence into blocks (e.g. 64–256 positions each):

- **Within a chunk:** use the attention-shaped matmul form (Form 3) — small enough that O(chunk²) is cheap, and it's pure GEMM, so it's fast on tensor cores.
- **Between chunks:** carry forward a small summary state using the cheap recurrence (Form 1/2) — since there are only `T / chunk_size` chunks, this part stays linear in `T`.

This hybrid is why Mamba-2 is reported to run meaningfully faster than the original Mamba on the same GPU, despite computing (approximately) the same kind of model. It is literally "mostly GEMM, with a thin recurrent connector between blocks" — which is exactly the "implement Mamba as MHA" idea this project set out to explore, now made concrete.

### 6.2 Why chunking is also a numerical necessity, not just a speed trick

Look again at `w = b * x / P` in the cumsum/attention code (§5.4). `P` is a cumulative *product* of numbers less than 1 — it shrinks toward zero as `T` grows (for `T` in the thousands, `P` can underflow toward zero in floating point). Dividing by a near-zero `P` then blows the numbers back up — mathematically the huge multiply and huge divide cancel out, but floating-point arithmetic done in this order can lose precision or overflow well before they get the chance to cancel. Chunking keeps each chunk short enough that `P` never gets too extreme within it, resetting the cumulative product at each chunk boundary. So the chunked algorithm isn't just faster — it's also the numerically stable way to do this at real sequence lengths.

### 6.3 Where to go for real code

The `mamba-ssm` reference implementation (the authors' own library) contains a file usually called something like `ssd_minimal.py` — the Mamba-2 paper states the minimal SSD algorithm is expressible in about 25 lines of code. Reading that file, now that you have the derivation in §5.2–5.4 under your belt, is the natural "Phase 2" step: real-scale implementation, rather than the toy scalar example here.

### 6.4 The open decisions (not yet made — flagging so nothing gets assumed silently)

- **Target chip for benchmarking:** Luna (L40S GPU — same machine used for the old Dorado profiling, has tensor cores, `nsys`/`perf` tooling already set up) vs. Orion (Jetson edge, ARM64 — matches the earlier "NanoMambaNet" edge-inference framing Kolin sir mentioned in `dorado-kraken-research/docs/knowledge_base.md`) vs. both. Explicitly still unexplored as of 2026-07-04.
- **Whether this connects to "NanoMambaNet"** (the edge inference pipeline Kolin sir separately mentioned) or is a standalone benchmarking exercise.
- **Whether/when the old `dorado-kraken-research/CLAUDE.md` and its profiling work resume** — paused, not abandoned.

### 6.5 Suggested reading order (roughly the order a researcher would tackle these)

1. **Original Mamba paper** — Gu & Dao, *"Mamba: Linear-Time Sequence Modeling with Selective State Spaces"* (2023). [arXiv:2312.00752](https://arxiv.org/abs/2312.00752)
2. **Mamba-2 / State Space Duality** — Dao & Gu, *"Transformers are SSMs"* (2024). [arXiv:2405.21060](https://arxiv.org/abs/2405.21060) — and Tri Dao's own blog series, which explains it more gently than the paper: [tridao.me/blog/2024/mamba2-part1-model](https://tridao.me/blog/2024/mamba2-part1-model/)
3. **The Hidden Attention of Mamba Models** — Ali et al. (2024). [arXiv:2403.01590](https://arxiv.org/abs/2403.01590) — the interpretability-flavored sibling result mentioned in §5.5.
4. **FlashAttention** — Dao et al. (2022) — for the "reorganize computation around the memory hierarchy, don't change the math" mindset that Mamba's own efficient kernels borrow directly from. Relevant search term: "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness."

### 6.6 Exercises (do these before moving to Phase 2 — they're the fastest way to confirm the concepts actually stuck)

1. **Vector state.** Modify §5.4's code so `h` is a small vector (say, 4 numbers) instead of a scalar, with `a` a vector of the same size (element-wise, still no cross-channel mixing — this is still "scalar-times-identity" per channel, just several channels at once). Confirm the recurrence and attention forms still match per channel.
2. **Add softmax.** Take the `L` matrix from §5.4, apply the causal-masked softmax from Chapter 2's `self_attention` to it instead of using its raw values, and compare the output to the un-normalized version. This is the concrete difference between "Mamba's implicit attention" and "real Transformer attention" — seeing both on the same numbers makes the distinction from §5.5 tangible.
3. **Time it.** Increase `T` in §5.4 (try 100, 1,000, 10,000) and time `recurrence_form` vs. `attention_form` in plain Python. Even on CPU, without any GPU involved, you should see the O(T) vs. O(T²) gap start to show up as `T` grows — and you should also start to see the numerical stability issue from §6.2 appear as `np.allclose` starts failing at large `T`, which is itself an instructive failure.

---

## Sources

- [Mamba: Linear-Time Sequence Modeling with Selective State Spaces](https://arxiv.org/abs/2312.00752) — Gu & Dao, 2023
- [Transformers are SSMs: Generalized Models and Efficient Algorithms Through Structured State Space Duality (Mamba-2)](https://arxiv.org/abs/2405.21060) — Dao & Gu, 2024
- [State Space Duality (Mamba-2) Part I — The Model](https://tridao.me/blog/2024/mamba2-part1-model/) — Tri Dao's plain-language blog writeup
- [The Hidden Attention of Mamba Models](https://arxiv.org/abs/2403.01590) — Ali et al., 2024
- FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness — Dao, Fu, Ermon, Rudra, Ré, 2022
