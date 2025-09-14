from fastapi import FastAPI, HTTPException
import uvicorn
import httpx
import logging
from datetime import date
from typing import Any, Dict, List

from models import GitlabWebhookPayload, APIResponse
from config import (
    PROJECT_TO_SLACK,
    SLACK_BOT_TOKEN,
    REPLICON_BASE_URL,
    REPLICON_TOKEN,
    REPLICON_USER_URI,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Constants
TOTAL_HOURS_PER_MR = 8.0
SLACK_API_BASE = "https://slack.com/api"


# Slack Helper Function
async def send_slack_notifications(project_name: str, mr: Any, commits: List[Any], slack_users: List[str]) -> None:
    """Send merge request alerts to Slack users."""
    commit_messages = "\n".join([f"• {c.message}" for c in commits])
    msg = (
        f"*New Merge Request Alert*\n"
        f"*Project:* {project_name}\n"
        f"*Title:* {mr.title}\n"
        f"*URL:* <{mr.url}|Click to open>\n"
        f"*Commits:* {len(commits)}\n"
        f"*Commit Messages:*\n{commit_messages if commit_messages else 'No commits'}"
    )

    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}

    async with httpx.AsyncClient() as client:
        for user in slack_users:
            try:
                response = await client.post(
                    f"{SLACK_API_BASE}/conversations.open",
                    headers=headers,
                    json={"users": user},
                )
                channel_id = response.json().get("channel", {}).get("id")
                if not channel_id:
                    logger.error("Failed to open Slack conversation: %s", response.text)
                    continue

                response = await client.post(
                    f"{SLACK_API_BASE}/chat.postMessage",
                    headers=headers,
                    json={"channel": channel_id, "text": msg},
                )
                data = response.json()
                if not data.get("ok"):
                    logger.error("Slack error: %s", data.get("error"))
            except Exception:
                logger.exception("Slack notification failed")


# Replicon Helper Function
async def log_time_in_replicon(commits: List[Any]) -> None:
    """Log commit work into Replicon timesheet."""
    today = date.today()
    timesheet_payload = {
        "userUri": REPLICON_USER_URI,
        "date": {"year": today.year, "month": today.month, "day": today.day},
        "timesheetGetOptionUri": "urn:replicon:timesheet-get-option:create-timesheet-if-necessary",
    }

    async with httpx.AsyncClient() as client:
        ts_resp = await client.post(
            f"{REPLICON_BASE_URL}/timesheet/get-timesheet",
            headers={"Authorization": f"Bearer {REPLICON_TOKEN}"},
            json=timesheet_payload,
        )

        if not ts_resp.is_success:
            logger.error("Failed to get/create timesheet: %s", ts_resp.text)
            raise HTTPException(status_code=500, detail="Timesheet creation failed")

        ts_data = ts_resp.json()
        timesheet_uri = ts_data.get("timesheet", {}).get("uri")
        if not timesheet_uri:
            raise HTTPException(status_code=500, detail="Missing timesheet URI")

        if commits:
            hours_per_commit = TOTAL_HOURS_PER_MR / len(commits)
            for commit in commits:
                entry_payload = {
                    "timesheetUri": timesheet_uri,
                    "timeEntry": {
                        "date": {"year": today.year, "month": today.month, "day": today.day},
                        "hours": hours_per_commit,
                        "comments": commit.message,
                    },
                }
                entry_resp = await client.post(
                    f"{REPLICON_BASE_URL}/timesheet/save-time-entry",
                    headers={"Authorization": f"Bearer {REPLICON_TOKEN}"},
                    json=entry_payload,
                )

                if not entry_resp.is_success:
                    logger.error("Failed to save time entry: %s", entry_resp.text)
                    raise HTTPException(status_code=500, detail="Time entry save failed")

                logger.info("Time entry saved: %s", entry_resp.json())


# Main Endpoint
@app.post("/webhook/gitlab", response_model=APIResponse)
async def gitlab_webhook(payload: GitlabWebhookPayload) -> Dict[str, Any]:
    if payload.object_kind != "merge_request":
        return APIResponse(status="ignored", message="Not a merge_request")

    project_name = payload.project.name
    mr = payload.object_attributes
    commits = payload.commits or []

    slack_users = PROJECT_TO_SLACK.get(project_name)
    if slack_users:
        await send_slack_notifications(project_name, mr, commits, slack_users)

    await log_time_in_replicon(commits)

    return APIResponse(status="ok", message="Webhook processed successfully")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
