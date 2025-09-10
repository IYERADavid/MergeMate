from dotenv import load_dotenv
import os

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
REPLICON_BASE_URL = os.getenv("REPLICON_BASE_URL")
REPLICON_TOKEN = os.getenv("REPLICON_TOKEN")
REPLICON_USER_URI = os.getenv("REPLICON_USER_URI")

PROJECT_TO_SLACK = {
    os.getenv("PROJECT_100"): [ os.getenv("MY_SLACK_USER_ID"), os.getenv("PROJECT_100_SUPERVISOR_SLACK_USER_ID") ],
    os.getenv("PROJECT_101"): [ os.getenv("MY_SLACK_USER_ID"), os.getenv("PROJECT_101_SUPERVISOR_SLACK_USER_ID") ],
}
