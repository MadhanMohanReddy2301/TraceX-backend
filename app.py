# app.py
import asyncio
import io
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
from dotenv import load_dotenv

# File processing libraries
import PyPDF2
from docx import Document

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


# Text extraction functions
def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF file"""
    try:
        pdf_file = io.BytesIO(file_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = []
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
        return "\n".join(text).strip()
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {str(e)}")


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX file"""
    try:
        docx_file = io.BytesIO(file_bytes)
        doc = Document(docx_file)
        text = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text.append(paragraph.text)
        return "\n".join(text).strip()
    except Exception as e:
        raise ValueError(f"Failed to extract text from DOCX: {str(e)}")


def extract_text_from_txt(file_bytes: bytes) -> str:
    """Extract text from TXT file"""
    try:
        # Try UTF-8 first, fallback to latin-1
        try:
            return file_bytes.decode('utf-8').strip()
        except UnicodeDecodeError:
            return file_bytes.decode('latin-1').strip()
    except Exception as e:
        raise ValueError(f"Failed to extract text from TXT: {str(e)}")


def extract_text_from_file(filename: str, file_bytes: bytes) -> str:
    """Extract text based on file extension"""
    filename_lower = filename.lower()

    if filename_lower.endswith('.pdf'):
        return extract_text_from_pdf(file_bytes)
    elif filename_lower.endswith('.docx'):
        return extract_text_from_docx(file_bytes)
    elif filename_lower.endswith('.txt'):
        return extract_text_from_txt(file_bytes)
    else:
        raise ValueError(f"Unsupported file type. Supported: .txt, .pdf, .docx")


# Pydantic models for request / response
class RunRequest(BaseModel):
    requirement_text: str
    user_id: Optional[str] = "user1"
    session_id: Optional[str] = "session1"
    timeout_seconds: Optional[int] = 60


class AgentOutput(BaseModel):
    agent_name: str
    outputs: List[str]


class RunResponse(BaseModel):
    aggregated: Optional[str]
    per_agent: List[AgentOutput]
    extracted_text_length: Optional[int] = None  # For file uploads


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
        pass


# Run the workflow and collect events per agent
async def run_workflow_and_collect(user_id: str, session_id: str, content: types.Content, timeout_seconds: int):
    per_agent_outputs: Dict[str, List[str]] = {}
    aggregated_final: Optional[str] = None

    async def _run():
        nonlocal aggregated_final
        async for ev in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            agent_name = getattr(ev, "author", None) or "UnknownAgent"

            if ev.content and ev.content.parts:
                parts_text = [p.text for p in ev.content.parts if getattr(p, "text", None)]
                if parts_text:
                    text = "".join(parts_text)
                    per_agent_outputs.setdefault(agent_name, []).append(text)

                    if ev.is_final_response():
                        if aggregated_final:
                            aggregated_final += "\n" + text
                        else:
                            aggregated_final = text

    await ensure_session(user_id, session_id)

    try:
        await asyncio.wait_for(_run(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise asyncio.TimeoutError(f"Workflow exceeded timeout of {timeout_seconds} seconds.")
    except Exception as e:
        raise e

    return aggregated_final, per_agent_outputs


@app.post("/run", response_model=RunResponse)
async def run_requirement(req: RunRequest):
    """Accept text input directly"""
    if not req.requirement_text.strip():
        raise HTTPException(status_code=400, detail="requirement_text must be non-empty")

    content = types.Content(role="user", parts=[types.Part(text=req.requirement_text)])

    try:
        aggregated, per_agent_map = await run_workflow_and_collect(
            user_id=req.user_id,
            session_id=req.session_id,
            content=content,
            timeout_seconds=req.timeout_seconds,
        )
    except asyncio.TimeoutError:
        per_agent_list = [AgentOutput(agent_name=k, outputs=v) for k, v in per_agent_map.items()]
        return RunResponse(aggregated=aggregated, per_agent=per_agent_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running workflow: {e}")

    per_agent_list = [AgentOutput(agent_name=k, outputs=v) for k, v in per_agent_map.items()]
    return RunResponse(aggregated=aggregated, per_agent=per_agent_list)


@app.post("/run/upload", response_model=RunResponse)
async def run_requirement_upload(
        file: UploadFile = File(...),
        user_id: Optional[str] = Form("user1"),
        session_id: Optional[str] = Form("session1"),
        timeout_seconds: Optional[int] = Form(600)
):
    """Accept file upload (txt, pdf, docx) and extract text"""

    # Validate file is provided
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    # Read file bytes
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    if not file_bytes:
        raise HTTPException(status_code=400, detail="File is empty")

    # Extract text from file
    try:
        requirement_text = extract_text_from_file(file.filename, file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting text: {str(e)}")

    if not requirement_text.strip():
        raise HTTPException(status_code=400, detail="No text could be extracted from file")

    # Build content and run workflow
    content = types.Content(role="user", parts=[types.Part(text=requirement_text)])

    try:
        aggregated, per_agent_map = await run_workflow_and_collect(
            user_id=user_id,
            session_id=session_id,
            content=content,
            timeout_seconds=timeout_seconds,
        )
    except asyncio.TimeoutError:
        per_agent_list = [AgentOutput(agent_name=k, outputs=v) for k, v in per_agent_map.items()]
        return RunResponse(
            aggregated=aggregated,
            per_agent=per_agent_list,
            extracted_text_length=len(requirement_text)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running workflow: {e}")

    per_agent_list = [AgentOutput(agent_name=k, outputs=v) for k, v in per_agent_map.items()]
    return RunResponse(
        aggregated=aggregated,
        per_agent=per_agent_list,
        extracted_text_length=len(requirement_text)
    )


# Simple health check
@app.get("/health")
async def health():
    return {"status": "ok", "agent": AGENT_NAME}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8080, log_level="info")