# Multi-Agent Deliberation · Architecture

Static architecture diagrams for the multi-agent optimization pipeline. These render natively on GitHub.

---

## 1. C2 Pipeline (the winner: 3 agents × 2 rounds)

```mermaid
flowchart TD
    P[/"**Problem**<br/>Service marketplace<br/>349 orders × 338 providers"/]:::problem

    C((Conductor)):::conductor

    A1[AmbiguityDetector]:::agent
    A2[ParameterExtractor]:::agent
    A3[ModelingReviewer]:::agent

    POOL[("Comment Pool<br/>shared context")]:::pool

    SUM[/"Summarizer<br/>80% token reduction"/]:::util
    COND{{Condenser<br/>plan ≈ 300 words}}:::util
    RED{{"Reducer · GPT-5.4 Mini<br/>plan → Python"}}:::reducer

    EVAL[/"**Evaluator**<br/>Composite score 0–100<br/>served + feasibility + travel + regressions"/]:::eval

    OUT[/"**Output**<br/>Score: 76.4 · GOOD<br/>343 served · 697 km · 0 violations"/]:::output

    P --> C
    C -->|"turn 1"| A1
    C -->|"turn 2"| A2
    C -->|"turn 3"| A3
    A1 --> POOL
    A2 --> POOL
    A3 --> POOL

    POOL -->|"end of round"| SUM
    SUM -.->|"round-2 context"| A1
    SUM -.-> A2
    SUM -.-> A3

    POOL -->|"after all rounds"| COND
    COND --> RED
    RED --> EVAL
    EVAL --> OUT

    classDef problem fill:#1F3A5F,stroke:#1F3A5F,color:#fff,stroke-width:1px
    classDef conductor fill:#22D3EE,stroke:#0891B2,color:#0B1220,stroke-width:2px
    classDef agent fill:#1E293B,stroke:#22D3EE,color:#E2E8F0,stroke-width:1.5px
    classDef pool fill:#334155,stroke:#94A3B8,color:#F1F5F9,stroke-width:1px
    classDef util fill:#B35A00,stroke:#7C2D12,color:#fff,stroke-width:1px
    classDef reducer fill:#B35A00,stroke:#7C2D12,color:#fff,stroke-width:2px
    classDef eval fill:#065F46,stroke:#10B981,color:#fff,stroke-width:1.5px
    classDef output fill:#10B981,stroke:#065F46,color:#052E16,stroke-width:2px
```

### Reading the diagram

- **Solid arrows** = data flow in the forward pass
- **Dashed arrows** = the round-2 feedback loop (agents re-read the summarized round-1 discussion before speaking again)
- **Colored nodes** = role types (cyan agents, orange utilities, green output)

---

## 2. Two-Round Iteration (sequence view)

```mermaid
sequenceDiagram
    autonumber
    participant C as Conductor
    participant AD as AmbiguityDetector
    participant PE as ParameterExtractor
    participant MR as ModelingReviewer
    participant P as Comment Pool
    participant S as Summarizer
    participant R as Reducer

    Note over C,R: Round 1 — loose on radius
    C->>AD: your turn
    AD->>P: "radius_cap_km may be hard"
    C->>PE: your turn
    PE->>P: "6 fields extracted"
    C->>MR: your turn
    MR->>P: "greedy + score by distance"

    Note over P,S: Summarize round 1
    P->>S: condense 14 KB → 0.5 KB

    Note over C,R: Round 2 — agents see round-1 summary
    S-->>AD: round-1 summary
    S-->>PE: round-1 summary
    S-->>MR: round-1 summary
    C->>AD: your turn
    AD->>P: "CONFIRMED radius is HARD"
    C->>PE: your turn
    PE->>P: "+10% window tolerance"
    C->>MR: your turn
    MR->>P: "strict radius filter BEFORE scoring"

    Note over P,R: Synthesize
    P->>R: full plan
    R->>R: generate Python (< 100 lines)
```

---

## 3. Config Grid & Results

```mermaid
flowchart LR
    subgraph "1 round"
      C1[C1 · 3 agents<br/>58.1 ACCEPTABLE<br/>38 radius violations]:::ok
      C3[C3 · 6 agents<br/>65.1 GOOD<br/>31 radius violations]:::ok
      C5[C5 · 10 agents<br/>68.0 GOOD<br/>11 radius violations]:::good
    end

    subgraph "2 rounds"
      C2[**C2 · 3 agents**<br/>**76.4 GOOD**<br/>**0 violations** · 9 calls]:::winner
      C4[C4 · 6 agents<br/>45.6 ACCEPTABLE<br/>served only 5 of 349]:::bad
      C6[C6 · 10 agents + Opus<br/>77.9 GOOD<br/>0 violations · 23 calls]:::good
    end

    C1 -->|"+18.3"| C2
    C3 -->|"−19.5"| C4
    C5 -->|"+9.9"| C6

    classDef ok fill:#334155,stroke:#94A3B8,color:#F1F5F9
    classDef good fill:#065F46,stroke:#10B981,color:#fff
    classDef winner fill:#10B981,stroke:#065F46,color:#052E16,stroke-width:3px
    classDef bad fill:#991B1B,stroke:#7F1D1D,color:#fff
```

**Read it like this:** Round 2 helps at 3 agents (+18), destroys quality at 6 mini agents (−20), helps again at 10 with Opus (+10). Iteration is dose-dependent on agent count and model quality.

---

## 4. Score Composition (how the 76.4 is built)

```mermaid
pie showData
    title "C2 score breakdown (out of 100)"
    "Served (40 max, got 39.3)" : 39.3
    "Feasibility (25 max, got 25)" : 25
    "Travel efficiency (20 max, got 12.4)" : 12.4
    "Regressions avoided (15 max, got 14.7)" : 14.7
    "Points lost" : 8.6
```

---

## Notes

- The C2 pipeline (section 1) shows the winning configuration
- The Config Grid (section 3) shows how iteration interacts with agent count
- The sequence diagram (section 2) illustrates the round-2 feedback mechanism
