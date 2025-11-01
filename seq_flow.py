import json
import os
from agents.IngestAgent.agent import IngestAgent
from agents.KbAgent.agent import KbAgent
from agents.TestCaseAgent.agent import TestCaseAgent
from agents.EdgeCaseAgent.agent import EdgeCaseAgent
from agents.ComplianceAgent.agent import ComplianceAgent

import asyncio
from dotenv import load_dotenv

from google.adk.agents import SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from typing import Optional, List

# Load environment variables
load_dotenv()

AGENT_NAME = "SequentialRequirementWorkflow"
TEMP_FILE_PATH = os.path.join(os.getcwd(), "temp_output.txt")


def build_workflow_agent():
    """
    Compose a SequentialAgent from the already-created agents.
    The SequentialAgent runs sub_agents in order, sharing the same invocation/session context.
    """
    ingest_agent = IngestAgent().get_agent()
    kb_agent = KbAgent().get_agent()
    test_case_agent = TestCaseAgent().get_agent()
    edge_case_agent = EdgeCaseAgent().get_agent()
    compliance_agent = ComplianceAgent().get_agent()

    workflow = SequentialAgent(
        name=AGENT_NAME,
        description="Run ingestion first, then run compliance lookup using ingestion output until all subagents done in sequence",
        sub_agents=[
            ingest_agent,
            kb_agent,
            test_case_agent,
            edge_case_agent,
            compliance_agent,
        ],
    )
    return workflow


class SequentialWorkflowRunner:
    def __init__(self, workflow_agent):
        self.workflow = workflow_agent
        self.session_service = InMemorySessionService()
        self.user_id = "user1"
        self.session_id = "session1"
        self.runner = Runner(agent=self.workflow, app_name=AGENT_NAME, session_service=self.session_service)

    async def create_session(self):
        await self.session_service.create_session(
            app_name=AGENT_NAME,
            user_id=self.user_id,
            session_id=self.session_id,
        )

    async def run_loop(self, user_input: Optional[str] = None):
        """Run the sequential workflow.

        - If `user_input` is provided (a string), run the workflow once for that input
          and save the last sub-agent output to TEMP_FILE_PATH.
        - If `user_input` is None, fall back to the original interactive loop.
        """
        print(f"Initializing [🤖] : {AGENT_NAME}")
        await self.create_session()

        # If no explicit user_input provided, keep original interactive loop behavior
        if user_input is None:
            print("Enter your requirement text (empty to exit):")

            while True:
                user_input = await asyncio.to_thread(input, "> ")
                if not user_input.strip():
                    print("Goodbye!")
                    break

                await self._run_once_and_save(user_input)
                print("=" * 20)

            # final cleanup attempt before returning
            await self._final_cleanup()
            return

        # Single-run path
        await self._run_once_and_save(user_input)
        # final cleanup attempt before returning
        await self._final_cleanup()
        print("=" * 20)

    async def _run_once_and_save(self, user_input: str):
        """Internal helper: run the workflow once for the provided input and save last sub-agent output.

        This implementation:
          - runs the async generator in a dedicated consumer task
          - always attempts to call gen.aclose() from inside the consumer (same task)
          - posts the last_final_text via a small queue
        """
        content = types.Content(role="user", parts=[types.Part(text=user_input)])

        # create generator (do NOT aclose() it from outer task)
        gen = self.runner.run_async(
            user_id=self.user_id,
            session_id=self.session_id,
            new_message=content,
        )

        result_q: asyncio.Queue = asyncio.Queue(maxsize=1)

        async def consumer():
            last_final_text = None
            try:
                async for ev in gen:
                    if ev.is_final_response() and ev.content and ev.content.parts:
                        parts_text = [p.text for p in ev.content.parts if getattr(p, "text", None)]
                        final_text = "".join(parts_text)

                        agent_name = getattr(ev, "author", None) or "UnknownAgent"
                        print(f"------------------- {agent_name} IS RUNNING ----------------------")
                        print(final_text)

                        last_final_text = final_text
                # normal exhaustion -> put result
                try:
                    await result_q.put(last_final_text)
                except asyncio.CancelledError:
                    # if put was cancelled, ignore
                    pass
            except asyncio.CancelledError:
                # If cancelled while iterating, we'll still attempt to close gen in the finally below
                # re-raise after the finally
                raise
            except Exception as exc:
                # Put None as sentinel and log
                try:
                    await result_q.put(None)
                except Exception:
                    pass
                print("Error inside consumer:", exc)
            finally:
                # IMPORTANT: always call aclose() from the same task that iterated the generator.
                try:
                    aclose = getattr(gen, "aclose", None)
                    if aclose is not None:
                        await aclose()
                except Exception as e:
                    # Log but don't re-raise: we've already done best-effort cleanup
                    print("Warning: error while closing generator inside consumer finally:", e)

        # Launch consumer
        consumer_task = asyncio.create_task(consumer())

        try:
            # Wait for consumer to finish naturally; this will also handle any cancellations
            await consumer_task
        except asyncio.CancelledError:
            # If the outer task is cancelled, ensure consumer_task is cancelled and awaited
            if not consumer_task.done():
                consumer_task.cancel()
                try:
                    await consumer_task
                except Exception:
                    pass
            raise
        except Exception:
            # For any other error, ensure consumer finishes
            if not consumer_task.done():
                consumer_task.cancel()
                try:
                    await consumer_task
                except Exception:
                    pass
        finally:
            # Ensure consumer_task completed
            if not consumer_task.done():
                consumer_task.cancel()
                try:
                    await consumer_task
                except Exception:
                    pass

        # Fetch the result if available
        try:
            last_output = result_q.get_nowait()
        except asyncio.QueueEmpty:
            last_output = None

        # Save to file if available
        if last_output:
            try:
                with open(TEMP_FILE_PATH, "w", encoding="utf-8") as f:
                    f.write(last_output)
                print(f"✅ Saved last output to {TEMP_FILE_PATH}")
            except Exception as file_err:
                print("Error saving last output to file:", file_err)

    async def _final_cleanup(self, cancel_remaining_tasks: bool = True, wait_seconds: float = 0.05):
        """
        Attempt a final cleanup:
          - short sleep to let background cleanup proceed
          - optionally cancel any remaining pending tasks (best-effort)
        """
        # small delay to give libraries a moment to finish their internal cleanup
        try:
            await asyncio.sleep(wait_seconds)
        except Exception:
            pass

        if not cancel_remaining_tasks:
            return

        # Best-effort cancel of any leftover non-finished tasks (excluding this task).
        # This is aggressive but useful for short-lived scripts/orchestration to avoid leaving
        # library-created tasks that attempt to exit cancel scopes in other tasks.
        current = asyncio.current_task()
        pending: List[asyncio.Task] = [t for t in asyncio.all_tasks() if t is not current and not t.done()]

        if not pending:
            return

        # Cancel and await them
        for t in pending:
            try:
                t.cancel()
            except Exception:
                pass

        # Wait for them to finish, ignore exceptions
        try:
            await asyncio.gather(*pending, return_exceptions=True)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        workflow_agent = build_workflow_agent()
    except Exception as ex:
        print("[Orchestrator] Failed to build workflow agent:", ex)
        raise

    runner = SequentialWorkflowRunner(workflow_agent)
    # Example interactive behavior:
    asyncio.run(runner.run_loop("""REQ-0002 — API Throughput & Latency:
The system SHALL process a minimum of 500 concurrent FHIR read requests per second (RPS) with a 95th percentile latency ≤ 350 ms for successful responses under a steady-state load. Under peak load (burst up to 2x normal load for up to 5 minutes), the system SHALL degrade gracefully with no more than 1% error rate. Performance test results SHALL be reproducible and recorded in BigQuery.
"""))
