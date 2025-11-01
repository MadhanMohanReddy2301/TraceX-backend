# kb.py — MCP server exposing Vertex AI RAG as a tool

from __future__ import annotations
import os
from typing import Any, Dict
from dotenv import load_dotenv
import vertexai
from vertexai.preview import rag
from mcp.server.fastmcp import FastMCP

# -----------------------
# Load Environment
# -----------------------
load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-east4")
CORPUS_NAME = os.getenv("RAG_CORPUS_NAME")

NAME = "KbRagTool"
HOST = "0.0.0.0"
PORT = 8080

mcp = FastMCP(NAME, host=HOST, port=PORT)

# -----------------------
# Vertex AI Initialization
# -----------------------
def init_vertex():
    """Initialize Vertex AI with project and location."""
    if not PROJECT_ID:
        raise EnvironmentError("❌ GOOGLE_CLOUD_PROJECT not set in .env")
    if not LOCATION:
        raise EnvironmentError("❌ GOOGLE_CLOUD_LOCATION not set in .env")
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    print(f"✅ Vertex AI initialized for project={PROJECT_ID} | location={LOCATION}")

# -----------------------
# MCP Tool: RAG Query
# -----------------------

class KbRagPlugin:
    """
    MCP plugin exposing Vertex AI Retrieval-Augmented Generation (RAG) capabilities over SSE.

    Features:
      - Integrates with Vertex AI RAG API to query a configured corpus.
      - Retrieves the most relevant document contexts for a given question.
      - Runs as an MCP (Model Context Protocol) server accessible via SSE transport.

    Tools:
      - rag_query(question: str, top_k: int = 3):
          Executes a retrieval query against the RAG corpus and returns the top matching text contexts.
    """
    @mcp.tool()
    def rag_query(question: str, top_k: int = 3) -> Dict[str, Any]:
        """
        Query a Vertex AI RAG corpus and return top retrieved contexts.

        Args:
            question (str): The input query/question.
            top_k (int): Number of top documents to retrieve.

        Returns:
            dict: Retrieved text snippets or error message.
        """
        try:
            init_vertex()

            if not CORPUS_NAME:
                return {"ok": False, "error": "Missing RAG_CORPUS_NAME environment variable."}

            rag_retrieval_config = rag.RagRetrievalConfig(
                top_k=top_k,
                filter=rag.Filter(vector_distance_threshold=0.5),
            )

            response = rag.retrieval_query(
                rag_resources=[rag.RagResource(rag_corpus=CORPUS_NAME)],
                text=question,
                rag_retrieval_config=rag_retrieval_config,
            )

            # ✅ Safely access nested response structure
            if not response.contexts or not getattr(response.contexts, "contexts", None):
                return {"ok": True, "contexts": [], "message": "⚠️ No relevant documents found."}

            context_list = response.contexts.contexts
            context_texts = [c.text for c in context_list if getattr(c, "text", None)]
            top_contexts = context_texts[:top_k]

            return {
                "ok": True,
                "count": len(top_contexts),
                "contexts": top_contexts,
            }

        except Exception as e:
            return {"ok": False, "error": f"❌ Error querying RAG corpus: {e}"}


    # -----------------------
    # MCP Runtime Info
    # -----------------------
    @staticmethod
    def display_runtime_info():
        """Display server connection details."""
        print(f"{NAME} : Running on host={HOST}, port={PORT}")
        print(f"Project: {PROJECT_ID}, Location: {LOCATION}")
        return {"ok": True, "host": HOST, "port": PORT}

    def run(self, transport: str = "sse"):
        """Start the MCP server and print runtime info."""
        self.display_runtime_info()
        mcp.run(transport=transport)


if __name__ == "__main__":
    server = KbRagPlugin()
    server.run()