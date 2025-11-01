# app.py
import asyncio
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# your existing agent imports
from agents.IngestAgent.agent import IngestAgent
from agents.KbAgent.agent import KbAgent
from agents.TestCaseAgent.agent import TestCaseAgent
from agents.EdgeCaseAgent.agent import EdgeCaseAgent
from agents.ComplianceAgent.agent import ComplianceAgent
from agents.TraceabilityAgent.agent import TraceabilityAgent
from agents.IntegrationAgent.agent import IntegrationAgent

from google.adk.agents import SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

AGENT_NAME = "SequentialRequirementWorkflowAPI"

# Build agents exactly like in your CLI script
ingest_agent = IngestAgent().get_agent()
kb_agent = KbAgent().get_agent()
test_case_agent = TestCaseAgent().get_agent()
edge_case_agent = EdgeCaseAgent().get_agent()
compliance_agent = ComplianceAgent().get_agent()
traceability_agent = TraceabilityAgent().get_agent()
integration_agent = IntegrationAgent().get_agent()

def build_workflow_agent():
    workflow = SequentialAgent(
        name=AGENT_NAME,
        description="Run ingestion first, then run compliance lookup using ingestion output.",
        sub_agents=[
            ingest_agent,
            kb_agent,
            test_case_agent,
            edge_case_agent,
            compliance_agent,
            traceability_agent,
            integration_agent,
        ],
    )
    return workflow

# Pydantic models for request / response
class RunRequest(BaseModel):
    requirement_text: str
    user_id: Optional[str] = "user1"
    session_id: Optional[str] = "session1"
    timeout_seconds: Optional[int] = 60  # total time budget for running the workflow

class AgentOutput(BaseModel):
    agent_name: str
    outputs: List[str]

class RunResponse(BaseModel):
    aggregated: Optional[str]
    per_agent: List[AgentOutput]

# Create FastAPI app and prepare runner/session service
app = FastAPI(title="Sequential Requirement Workflow API")

workflow_agent = build_workflow_agent()
session_service = InMemorySessionService()
runner = Runner(agent=workflow_agent, app_name=AGENT_NAME, session_service=session_service)

# helper to create session (idempotent)
async def ensure_session(user_id: str, session_id: str):
    try:
        await session_service.create_session(app_name=AGENT_NAME, user_id=user_id, session_id=session_id)
    except Exception:
        # session may already exist or create_session may raise; ignore and continue
        pass

# Run the workflow and collect events per agent
async def run_workflow_and_collect(user_id: str, session_id: str, content: types.Content, timeout_seconds: int):
    per_agent_outputs: Dict[str, List[str]] = {}
    aggregated_final: Optional[str] = None

    # run the async event stream with a timeout
    async def _run():
        nonlocal aggregated_final
        async for ev in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            # ev.author often contains agent name
            agent_name = getattr(ev, "author", None) or "UnknownAgent"

            # collect content parts if present
            if ev.content and ev.content.parts:
                parts_text = [p.text for p in ev.content.parts if getattr(p, "text", None)]
                if parts_text:
                    text = "".join(parts_text)
                    per_agent_outputs.setdefault(agent_name, []).append(text)

                    # if it's a final response event, capture for aggregated output
                    if ev.is_final_response():
                        # accumulate final text - may be last agent final answer
                        if aggregated_final:
                            aggregated_final += "\n" + text
                        else:
                            aggregated_final = text

    # ensure runner has a session
    await ensure_session(user_id, session_id)

    try:
        await asyncio.wait_for(_run(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        # partial results might exist
        raise asyncio.TimeoutError(f"Workflow exceeded timeout of {timeout_seconds} seconds.")
    except Exception as e:
        # bubble up for API layer to handle
        raise e

    return aggregated_final, per_agent_outputs

@app.post("/run", response_model=RunResponse)
async def run_requirement(req: RunRequest):
    if not req.requirement_text.strip():
        raise HTTPException(status_code=400, detail="requirement_text must be non-empty")

    # Build types.Content as you did in CLI
    content = types.Content(role="user", parts=[types.Part(text=req.requirement_text)])

    try:
        aggregated, per_agent_map = await run_workflow_and_collect(
            user_id=req.user_id,
            session_id=req.session_id,
            content=content,
            timeout_seconds=req.timeout_seconds,
        )
    except asyncio.TimeoutError as te:
        # Return partial output with 202 Accepted style semantics
        per_agent_list = [AgentOutput(agent_name=k, outputs=v) for k, v in per_agent_map.items()]
        return RunResponse(aggregated=aggregated, per_agent=per_agent_list)
    except Exception as e:
        # surface error
        raise HTTPException(status_code=500, detail=f"Error running workflow: {e}")

    per_agent_list = [AgentOutput(agent_name=k, outputs=v) for k, v in per_agent_map.items()]
    return RunResponse(aggregated=aggregated, per_agent=per_agent_list)


# Simple health check
@app.get("/health")
async def health():
    return {"status": "ok", "agent": AGENT_NAME}

if __name__ == "__main__":
    uvicorn.run("rest_api:app", host="0.0.0.0", port=8080, log_level="info")
