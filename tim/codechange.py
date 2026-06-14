import logging
from tim import Project, Change
from .codingagent import CodingAgent, PassFailAgent

logger = logging.getLogger(__name__)


class MaxAttemptsExceeded(Exception): ...


def apply_code_change(project: Project, change: Change, attempts: int = 20):
    logger.info(f"Starting code change for: {change.title}")
    coding_agent = CodingAgent(project, change)
    for attempt in range(attempts):
        response = coding_agent.start()
        logger.debug(f"[{attempt=}] Coding agent finished for: {change.title}")

        must_answers = [PassFailAgent(project, must).answer() for must in change.musts]
        for result in must_answers:
            logger.debug(f"[{attempt=}] question={result.rule} answer={result.answer} reason={result.reason}")

        failures = [result for result in must_answers if not result.answer]
        if len(failures) == 0:
            logger.info(f"[{attempt=}] No change.musts failed, done.")
            return response

        coding_agent = CodingAgent(project, change)
        logger.info(f"[{attempt=}] Requesting coding agent fix {len(failures)} problem(s)")

        message = ["This implementation is already in progress.", "The following code issues were identified:"]
        for failure in failures:
            message.append(f"<issue><rule>{failure.rule}</rule><reason>{failure.reason}</reason></issue>")
        message.append("")
        message.append("Please fix all issues.")

        coding_agent.add_user_message("\n".join(message))

    raise MaxAttemptsExceeded(f"Exhausted {attempts=}")
