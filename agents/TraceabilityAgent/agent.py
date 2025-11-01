# agent.py
import asyncio
import os
import json
from typing import Optional

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
# NEW imports for MCP toolset
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_toolset import SseConnectionParams

from google.genai import types
from dotenv import load_dotenv

# your existing prompt factory
from agents.TraceabilityAgent.prompt.prompt_factory import PromptFactory


load_dotenv()

AGENT_NAME = "TraceabilityAgent"


class TraceabilityAgent:
    @staticmethod
    def get_agent():
        """Create and return an ADK Agent ready to use."""
        print(f"Initializing [🤖] : {AGENT_NAME}")
        agent_prompt = PromptFactory().get_agent_prompt()

        # NEW: initialize MCPToolset for Jira MCP server
        big_query_mcp_url = os.getenv("BIGQUERY_MCP_SERVER_URL")
        mcp_toolset = McpToolset(
            connection_params=SseConnectionParams(url=big_query_mcp_url),
        )
        # Pass the wrapper functions into tools; ADK will auto-wrap them as FunctionTools.
        return Agent(
            name=AGENT_NAME,
            model=os.getenv("GEMINI_MODEL"),
            description="TraceabilityAgent (verifies/inserts requirement↔testcase links in BigQuery).",
            instruction=agent_prompt,
            tools=[mcp_toolset],
        )

    async def _run_once_and_return(self, runner: Runner, user_id: str, session_id: str, payload_text: str) -> Optional[str]:
        """
        Run runner.run_async in a dedicated consumer task and return the last final response text
        authored by AGENT_NAME, or None if none produced.
        This ensures iterator closing happens in the same task that iterated the generator.
        """
        content = types.Content(role="user", parts=[types.Part(text=payload_text)])
        gen = runner.run_async(user_id=user_id, session_id=session_id, new_message=content)

        # queue to receive the result from the consumer task
        result_q: asyncio.Queue = asyncio.Queue(maxsize=1)

        async def consumer():
            last_final_text = None
            try:
                async for ev in gen:
                    if ev.is_final_response() and getattr(ev, "author", None) == AGENT_NAME and ev.content and ev.content.parts:
                        parts_text = [p.text for p in ev.content.parts if getattr(p, "text", None)]
                        if parts_text:
                            last_final_text = "".join(parts_text)
                # generator exhausted normally -> put result
                await result_q.put(last_final_text)
            except asyncio.CancelledError:
                # If cancelled, close generator from THIS same task/context
                try:
                    aclose = getattr(gen, "aclose", None)
                    if aclose is not None:
                        await aclose()
                except Exception as e:
                    print("Warning: error while closing generator inside consumer after cancel:", e)
                # re-raise so outer code knows it was cancelled
                raise
            except Exception as exc:
                # Put None as a sentinel for failure and print error
                try:
                    await result_q.put(None)
                except Exception:
                    pass
                print("Error inside consumer:", exc)

        # start consumer task
        consumer_task = asyncio.create_task(consumer())

        try:
            # Wait for consumer to finish naturally (or propagate cancellation)
            await consumer_task
        except asyncio.CancelledError:
            # If outer task is cancelled, ensure consumer_task is cancelled too and awaited
            if not consumer_task.done():
                consumer_task.cancel()
                try:
                    await consumer_task
                except Exception:
                    pass
            raise
        except Exception:
            # On other exceptions, ensure consumer_task is cancelled and awaited
            if not consumer_task.done():
                consumer_task.cancel()
                try:
                    await consumer_task
                except Exception:
                    pass
        finally:
            # Last-ditch: ensure consumer task is finished
            if not consumer_task.done():
                consumer_task.cancel()
                try:
                    await consumer_task
                except Exception:
                    pass

        # retrieve and return result (or None)
        try:
            return result_q.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def run_agent(self, user_input: Optional[str] = None) -> Optional[str]:
        """
        If user_input is provided, runs the agent once with that input and returns the final text (or None).
        If user_input is None, falls back to the original interactive loop behavior.
        """
        USER_ID = "user1"
        SESSION_ID = "session1"

        agent = TraceabilityAgent().get_agent()
        session_service = InMemorySessionService()
        await session_service.create_session(
            app_name=AGENT_NAME,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )

        runner = Runner(agent=agent, app_name=AGENT_NAME, session_service=session_service)

        # Single-run path: return the result to the caller
        if user_input is not None:
            try:
                result = await self._run_once_and_return(runner, USER_ID, SESSION_ID, user_input)
                return result
            except Exception as e:
                print(f"Error while running agent (single-run): {e}")
                return None

        # Interactive fallback (unchanged behavior)
        print("Enter your payload JSON (empty to exit):")
        while True:
            user_input = await asyncio.to_thread(input, "> ")
            if not user_input.strip():
                print("Goodbye!")
                break

            try:
                last_final_text = await self._run_once_and_return(runner, USER_ID, SESSION_ID, user_input)
                if last_final_text:
                    print(last_final_text)
                else:
                    print("(no final response produced by the agent)")
            except Exception as e:
                print(f"Error while running agent: {e}")

            print("=" * 20)

        return None


if __name__ == "__main__":
    # interactive behavior (same as before)
    asyncio.run(TraceabilityAgent().run_agent())
