from .project import Project, Change
from .codingagent import CodingAgent


def apply_code_change(project: Project, change: Change):
    coding_agent = CodingAgent(project, change)
    coding_agent.start()
