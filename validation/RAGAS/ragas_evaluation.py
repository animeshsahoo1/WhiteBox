#!/usr/bin/env python3
"""
RAGAS Evaluation Script for RAG System

Evaluates RAG performance using FinQABench dataset with various configurations.

Configurations (set EXPERIMENT env var):
  1 = Baseline (Naive RAG):      RERANK=false, ADAPTIVE=false, CONTEXTUAL=false
  2 = Adaptive RAG:              RERANK=false, ADAPTIVE=true,  CONTEXTUAL=false
  3 = Baseline + Reranking:      RERANK=true,  ADAPTIVE=false, CONTEXTUAL=false
  4 = Ours (Reranking+Context):  RERANK=true,  ADAPTIVE=false, CONTEXTUAL=true

Usage:
  EXPERIMENT=1 python ragas_evaluation.py
  EXPERIMENT=2 python ragas_evaluation.py
  EXPERIMENT=3 python ragas_evaluation.py
  EXPERIMENT=4 python ragas_evaluation.py
"""

import os
import sys
import json
import asyncio
import time
from pathlib import Path
from datetime import datetime

import httpx
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# RAGAS imports
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.metrics import (
    Faithfulness,
    ResponseRelevancy,
    LLMContextPrecisionWithoutReference,
    LLMContextRecall,
    FactualCorrectness,
)
from ragas import EvaluationDataset, SingleTurnSample
from datasets import load_dataset
from langchain_openai import ChatOpenAI, OpenAIEmbeddings


# === CONFIG ===
RAG_API_URL = "http://localhost:8000"
NUM_SAMPLES = 100  # FinQABench samples to evaluate
OPENAI_MODEL = "gpt-4o-mini"

# Experiment configuration
EXPERIMENT = int(os.getenv("EXPERIMENT", "4"))
EXPERIMENT_CONFIGS = {
    1: {"name": "baseline_naive_rag",         "rerank": False, "adaptive": False, "contextual": False},
    2: {"name": "adaptive_rag",               "rerank": False, "adaptive": True,  "contextual": False},
    3: {"name": "baseline_reranking",         "rerank": True,  "adaptive": False, "contextual": False},
    4: {"name": "ours_reranking_contextual",  "rerank": True,  "adaptive": False, "contextual": True},
}

CONFIG = EXPERIMENT_CONFIGS.get(EXPERIMENT, EXPERIMENT_CONFIGS[5])
USE_RERANK = CONFIG["rerank"]
USE_ADAPTIVE = CONFIG["adaptive"]
USE_CONTEXTUAL = CONFIG["contextual"]


def load_finqabench(max_samples: int):
    """Load FinQABench AAPL questions from Hugging Face"""
    print(f"\n📥 Loading FinQABench dataset (max {max_samples} samples)...")
    ds = load_dataset("lighthouzai/finqabench", split="train")
    
    samples = []
    for i, item in enumerate(ds):
        if i >= max_samples:
            break
        samples.append({
            "query": item["Query"],
            "reference_answer": item["Response"],
            "ground_truth_context": item["Context"],
            "category": item["Category"],
        })
    
    print(f"✓ Loaded {len(samples)} samples")
    for i, s in enumerate(samples[:3]):
        print(f"  Q{i+1}: {s['query'][:60]}...")
    return samples


async def query_rag_adaptive(client: httpx.AsyncClient, query: str, use_rerank: bool = False, timeout: float = 120.0) -> tuple:
    """
    Query RAG using Adaptive RAG (geometric strategy).
    Pathway progressively retrieves more docs until answer found: 2 → 4 → 8 → 16
    """
    try:
        resp = await client.get(
            f"{RAG_API_URL}/debug/adaptive",
            params={"q": query, "rerank": use_rerank},
            timeout=timeout
        )
        
        if resp.status_code != 200:
            return "Adaptive RAG failed", [], 0
        
        result = resp.json()
        answer = result.get("response", "No answer")
        context_docs = result.get("context_docs", [])
        
        # Extract text from context docs
        contexts = [doc.get("text", "") for doc in context_docs if doc.get("text")]
        
        return answer, contexts, len(contexts)
        
    except Exception as e:
        print(f"  ✗ Adaptive RAG Error: {e}")
        return str(e), [], 0


async def query_rag_standard(client: httpx.AsyncClient, query: str, answer_llm, timeout: float = 120.0) -> tuple:
    """Query RAG: retrieve docs + generate answer (standard approach)"""
    try:
        # Step 1: Retrieve from Pathway (with optional reranking)
        resp = await client.get(
            f"{RAG_API_URL}/debug/retrieve",
            params={"q": query, "k": 7, "rerank": USE_RERANK},
            timeout=timeout
        )
        
        if resp.status_code != 200:
            return "Retrieval failed", [], 0
        
        results = resp.json().get("results", [])
        if not results:
            return "No documents found", [], 0
        
        # Step 2: Extract contexts
        contexts = [r.get("text", "") for r in results if r.get("text")]
        context_str = "\n\n".join([f"[Document {i+1}]:\n{c}" for i, c in enumerate(contexts)])
        
        # Step 3: Generate answer
        prompt = f"""You are a financial analyst. Answer the question directly and concisely based ONLY on the context provided.

Instructions:
1. Start with a direct answer to the question in the first sentence
2. Include specific numbers with units (e.g., "$394.3 billion", "23%")
3. Keep the answer focused - avoid unnecessary elaboration
4. If not found in context, say "Not available in the provided documents."

<context>
{context_str}
</context>

Question: {query}

Answer:"""
        
        response = answer_llm.invoke(prompt)
        return response.content, contexts, len(contexts)
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return str(e), [], 0


async def run_evaluation():
    """Main evaluation loop"""
    print("=" * 60)
    print(f"RAGAS EVALUATION - Experiment {EXPERIMENT}: {CONFIG['name']}")
    print("=" * 60)
    print(f"  Reranking: {USE_RERANK}")
    print(f"  Adaptive RAG: {USE_ADAPTIVE}")
    print(f"  Contextual Enrichment: {USE_CONTEXTUAL}")
    
    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("✗ OPENAI_API_KEY not found!")
        sys.exit(1)
    
    # Check RAG API
    print(f"\n🔌 Checking RAG API at {RAG_API_URL}...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{RAG_API_URL}/health", timeout=15.0)
            if resp.status_code == 200:
                print("✓ RAG API is healthy")
            else:
                print(f"✗ RAG API returned {resp.status_code}")
                sys.exit(1)
        except Exception as e:
            print(f"✗ Cannot connect: {e}")
            print("\n⚠️  Start RAG first: cd pathway && python -m api.rag_api")
            sys.exit(1)
    
    # Warmup query
    print("\n🔥 Warming up RAG (first query triggers indexing, may take ~60-90s)...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{RAG_API_URL}/debug/retrieve",
                params={"q": "Apple revenue", "k": 1, "rerank": False},
                timeout=180.0
            )
            if resp.status_code == 200:
                print("✓ RAG warmed up and ready")
            else:
                print(f"⚠️ Warmup returned {resp.status_code}, continuing anyway...")
        except Exception as e:
            print(f"⚠️ Warmup timeout/error: {e}")
            print("  Continuing anyway - first query may be slow...")
    
    # Initialize LLM
    print(f"\n🤖 Initializing {OPENAI_MODEL}...")
    answer_llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0, api_key=api_key)
    eval_llm = LangchainLLMWrapper(answer_llm)
    embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(api_key=api_key))
    
    # Load dataset
    samples = load_finqabench(NUM_SAMPLES)
    
    # Query RAG for each sample
    print(f"\n🔍 Querying RAG for {len(samples)} questions...")
    ragas_samples = []
    
    async with httpx.AsyncClient() as client:
        for i, sample in enumerate(samples):
            print(f"  [{i+1}/{len(samples)}] {sample['query'][:50]}...")
            
            if USE_ADAPTIVE:
                answer, contexts, num_docs = await query_rag_adaptive(client, sample["query"], use_rerank=USE_RERANK)
            else:
                answer, contexts, num_docs = await query_rag_standard(client, sample["query"], answer_llm)
            
            ragas_samples.append(SingleTurnSample(
                user_input=sample["query"],
                response=answer,
                retrieved_contexts=contexts if contexts else ["No context"],
                reference=sample["reference_answer"],
                reference_contexts=[sample["ground_truth_context"]] if sample["ground_truth_context"] else []
            ))
    
    # Run RAGAS evaluation
    print(f"\n📊 Running RAGAS evaluation...")
    
    metrics = [
        Faithfulness(llm=eval_llm),
        ResponseRelevancy(llm=eval_llm, embeddings=embeddings),
        LLMContextPrecisionWithoutReference(llm=eval_llm),
        LLMContextRecall(llm=eval_llm),
        FactualCorrectness(llm=eval_llm),
    ]
    
    eval_dataset = EvaluationDataset(samples=ragas_samples)
    
    results = evaluate(
        dataset=eval_dataset,
        metrics=metrics,
        llm=eval_llm,
        embeddings=embeddings,
        show_progress=True
    )
    
    # Extract results
    print("\n" + "=" * 60)
    print("📈 RAGAS RESULTS (0-1 scale, higher = better)")
    print("=" * 60)
    
    df = results.to_pandas()
    
    skip_cols = ['user_input', 'response', 'retrieved_contexts', 'reference', 'reference_contexts']
    metric_cols = [c for c in df.columns if c not in skip_cols]
    
    for col in metric_cols:
        val = df[col].mean()
        if pd.notna(val):
            bar = "█" * int(val * 20) + "░" * (20 - int(val * 20))
            print(f"  {col:40s} {val:.4f} [{bar}]")
    
    # Overall average
    numeric_vals = [df[c].mean() for c in metric_cols if pd.notna(df[c].mean())]
    if numeric_vals:
        avg = sum(numeric_vals) / len(numeric_vals)
        print(f"\n  {'OVERALL AVERAGE':40s} {avg:.4f}")
    
    # Save results
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    
    output_file = results_dir / f"{EXPERIMENT}_{CONFIG['name']}.json"
    
    save_data = {
        "experiment": EXPERIMENT,
        "name": CONFIG["name"],
        "config": {
            "reranking": USE_RERANK,
            "adaptive_rag": USE_ADAPTIVE,
            "contextual_enrichment": USE_CONTEXTUAL,
        },
        "dataset": {
            "name": "FinQABench",
            "source": "lighthouzai/finqabench",
            "num_samples": NUM_SAMPLES,
        },
        "metrics": {
            "context_precision": float(df["context_precision"].mean()) if "context_precision" in df.columns else None,
            "context_recall": float(df["context_recall"].mean()) if "context_recall" in df.columns else None,
            "faithfulness": float(df["faithfulness"].mean()) if "faithfulness" in df.columns else None,
            "answer_relevancy": float(df["answer_relevancy"].mean()) if "answer_relevancy" in df.columns else None,
            "factual_correctness": float(df["factual_correctness"].mean()) if "factual_correctness" in df.columns else None,
        },
        "timestamp": datetime.now().isoformat(),
    }
    
    with open(output_file, "w") as f:
        json.dump(save_data, f, indent=2)
    
    print(f"\n✓ Results saved to: {output_file}")
    print("=" * 60)
    
    return save_data


if __name__ == "__main__":
    asyncio.run(run_evaluation())
