"""Settings shared by all boards: timeouts, retries, fetch counts and output directories. 

Per-interface settings live in src/interfaces.py and credentials in src/credentials.py; the three files do not overlap. 
"""

REQUEST_TIMEOUT = 90
FULLTEXT_TIMEOUT = 60
PMC_BATCH_TIMEOUT = 180
ARCHIVE_TIMEOUT = 60
ARCHIVE_RETRY_WAIT = 20

RETRY_TIMES = 3
RETRY_WAIT_SECONDS = 5

TOP_N = 20
FULLTEXT_TOP_N = 10

ALL_RESULT_DIR = "ALL_result"
ALL_RESULT_OUTPUT_DIR = "output"
RUN_LOG_NAME = "run_log.json"
COMPETITOR_DIR_NAME = "competitors"

USER_AGENT_BASE = "pharma-literature-api-benchmark/1.0"
NCBI_TOOL = "pharma-literature-api-benchmark"


def user_agent(board: str) -> str:
    return f"{USER_AGENT_BASE} ({board} retrieval test)"
