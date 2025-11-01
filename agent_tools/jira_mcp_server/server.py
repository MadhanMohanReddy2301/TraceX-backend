# server.py

import os
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from jira import JIRA
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP

load_dotenv()

NAME = "Jira MCP Tool"
HOST = "0.0.0.0"
PORT = 8080
DEFAULT_PROJECT = os.getenv("JIRA_DEFAULT_PROJECT")
JIRA_BASE = os.getenv("JIRA_BASE_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_TOKEN = os.getenv("JIRA_API_TOKEN")

mcp = FastMCP(NAME, host=HOST, port=PORT)


class JiraMCPServer:
    """Responsible to create jira's/tasks"""

    @staticmethod
    def _make_jira_client():
        if not (JIRA_BASE and JIRA_EMAIL and JIRA_TOKEN):
            raise RuntimeError("Set JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN in env")
        return JIRA(server=JIRA_BASE, basic_auth=(JIRA_EMAIL, JIRA_TOKEN))

    @staticmethod
    @mcp.tool()
    def create_issue(fields: Dict[str, Any]) -> str:
        """
        Create a Jira issue given a fully formed 'fields' dict.

        Expect format similar to your agent output, e.g.:
          fields = {
            "project": {"key": "TP"},
            "summary": "REQ-0001-TC-01: Successful user authentication...",
            "description": "Objective: Verify ...\nTest Items: User authentication, Audit logging\n...",
            "issuetype": {"name": "Task"},
            "priority": {"name": "P1"},
            "labels": ["authentication", "multi-factor-authentication", "audit-logging", "phi"],
            // You can map agent’s keys to Jira fields as needed:
            "customfield_testCaseId": "REQ-0001-TC-01",
            "customfield_requirementRef": "REQ-0001",
            "customfield_objective": "Verify that the system ...",
            // etc...
          }
        You control how to map agent fields to Jira fields.
        This tool passes the dict straight to jira.create_issue(fields=...).
        Returns the issue key (string) like "TP-123".
        """
        jira = JiraMCPServer._make_jira_client()
        if 'project' not in fields or not fields.get('project'):
            if project_key := os.getenv('PROJECT_KEY', 'SCRUM'):
                # prefer project key, but you can also set {'id': <id>}
                fields['project'] = {'key': project_key}
            else:
                raise ValueError("No project provided in fields and no project_key given.")

        new_issue = jira.create_issue(fields=fields)
        return new_issue.key

    @staticmethod
    def display_runtime_info():
        """Prints out the server’s host and port information to the console."""
        if HOST == "0.0.0.0":
            print(f"{NAME} : Server running on IP: localhost and Port: {PORT}")
            print(f"{NAME} : Server running on IP: 127.0.0.1 and Port: {PORT}")
        print(f"{NAME} : Server running on IP: {HOST} and Port: {PORT}")

    def run(self, transport: str = "sse"):
        """Starts the MCP server and displays the IP address and port."""
        self.display_runtime_info()
        mcp.run(transport=transport)


if __name__ == "__main__":
    server = JiraMCPServer()
    server.run()
