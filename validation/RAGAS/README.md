# RAGAS Evaluation for RAG System

This directory contains the evaluation framework and results for our Retrieval-Augmented Generation (RAG) system using the [RAGAS](https://docs.ragas.io/) benchmark.

## Dataset

**FinQABench** - A financial question-answering benchmark from Hugging Face.
- **Source**: [`lighthouzai/finqabench`](https://huggingface.co/datasets/lighthouzai/finqabench)
- **Samples Used**: N=100 (AAPL 10-K questions)
- **Domain**: Apple Inc. financial filings (10-K reports)

This is a publicly available benchmark dataset - no custom dataset was created.

## Knowledge Corpus

Our RAG system uses a knowledge base built from:
- **Source**: Apple Inc. SEC 10-K filings
- **Format**: JSON chunks with contextual metadata
- **Location**: `/knowledge_base/AAPL/jsons/`
- **Vector Store**: Pathway DocumentStore with `text-embedding-3-small` embeddings

## Experiment Configurations

| # | Method | Reranking | Adaptive RAG | Contextual Enrichment |
|---|--------|-----------|--------------|----------------------|
| 1 | Baseline (Naive RAG) | ❌ | ❌ | ❌ |
| 2 | Adaptive RAG | ❌ | ✅ | ❌ |
| 3 | Baseline + Reranking | ✅ | ❌ | ❌ |
| 4 | **Ours (Reranking + Context)** | ✅ | ❌ | ✅ |

### Configuration Details

- **Reranking**: Cohere `rerank-v3.5` - over-retrieves 2x documents, then reranks to top-k
- **Adaptive RAG**: Pathway's `AdaptiveRAGQuestionAnswerer` with geometric strategy (2→4→8→16 docs)
- **Contextual Enrichment**: OpenRouter `gemini-2.0-flash-lite-001` adds document-level context to chunks

## Results Summary

| Method | Precision | Recall | Faithfulness | Relevancy | Factuality |
|--------|-----------|--------|--------------|-----------|------------|
| Baseline (Naive RAG) | 0.722 | 0.827 | 0.777 | 0.791 | 0.399 |
| Adaptive RAG | 0.789 | 0.626 | 0.835 | 0.743 | **0.525** |
| Baseline + Reranking | 0.836 | 0.847 | 0.801 | 0.773 | 0.412 |
| **Ours (Reranking + Context)** | **0.875** | **0.896** | **0.846** | **0.844** | 0.455 |

**Best Overall**: Reranking + Contextual Enrichment achieves highest scores in 4/5 metrics.

## RAGAS Metrics

| Metric | Description |
|--------|-------------|
| **Context Precision** | Are retrieved documents relevant to the question? |
| **Context Recall** | Does retrieved context cover the ground truth? |
| **Faithfulness** | Is the answer grounded in the retrieved context? |
| **Answer Relevancy** | Does the answer address the question directly? |
| **Factual Correctness** | Does the answer match the reference answer? |

## Replicating Results

### Prerequisites

1. **Start RAG API** (with desired configuration):
   ```bash
   cd pathway
   
   # For Experiment 1 (Naive RAG):
   RERANK_ENABLED=false CONTEXTUAL_ENRICHMENT=false python -m api.rag_api
   
   # For Experiment 3 (Reranking):
   RERANK_ENABLED=true CONTEXTUAL_ENRICHMENT=false python -m api.rag_api
   
   # For Experiment 4 (Ours - Best):
   RERANK_ENABLED=true CONTEXTUAL_ENRICHMENT=true python -m api.rag_api
   ```

2. **Environment Variables** (in `.env`):
   ```env
   OPENAI_API_KEY=sk-...          # Required for RAGAS evaluation
   COHERE_API_KEY=...             # Required for reranking
   OPENROUTER_API_KEY=...         # Required for contextual enrichment
   ```

### Running Evaluation

```bash
cd validation/RAGAS

# Install dependencies
pip install -r requirements.txt

# Run evaluation (set EXPERIMENT 1-4)
EXPERIMENT=1 python ragas_evaluation.py   # Naive RAG
EXPERIMENT=2 python ragas_evaluation.py   # Adaptive RAG
EXPERIMENT=3 python ragas_evaluation.py   # + Reranking
EXPERIMENT=4 python ragas_evaluation.py   # Ours (Reranking + Context)
```

### Output

Results are saved to `results/` directory as JSON files with metrics and configuration details.

## Files

```
RAGAS/
├── README.md                           # This file
├── requirements.txt                    # Python dependencies
├── ragas_evaluation.py                 # Evaluation script
└── results/
    ├── 1_baseline_naive_rag.json       # Experiment 1 results
    ├── 2_adaptive_rag.json             # Experiment 2 results
    ├── 3_baseline_reranking.json       # Experiment 3 results
    └── 4_ours_reranking_contextual.json # Experiment 4 results (best)
```

## Hardware Used

- **Evaluation**: MacOS (Apple Silicon)
- **LLM**: GPT-4o-mini (via OpenAI API)
- **Embeddings**: text-embedding-3-small (via OpenAI API)
- **Reranker**: Cohere rerank-v3.5
