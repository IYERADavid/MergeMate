from fastapi import FastAPI
import uvicorn
import httpx
import os
from models import GitlabWebhookPayload
from config import PROJECT_TO_SLACK, SLACK_BOT_TOKEN, REPLICON_BASE_URL, REPLICON_TOKEN, REPLICON_USER_URI
from datetime import date

app = FastAPI()

@app.post("/webhook/gitlab")
async def gitlab_webhook(payload: GitlabWebhookPayload):

    if payload.object_kind == "merge_request":
        project_name = payload.project.name
        mr = payload.object_attributes
        commits = payload.commits or []

        slack_users = PROJECT_TO_SLACK.get(project_name)
        if slack_users:
            # Create a bullet list of commit messages
            commit_messages = "\n".join([f"• {c.message}" for c in (payload.commits or [])])

            msg = (
                f"*New Merge Request Alert*\n"
                f"*Project:* {payload.project.name or payload.project.id}\n"
                f"*Title:* {payload.object_attributes.title}\n"
                f"*URL:* <{payload.object_attributes.url}|Click to open>\n"
                f"*Commits:* {len(payload.commits)}\n"
                f"*Commit Messages:*\n{commit_messages if commit_messages else 'No commits'}"
            )

            for user in slack_users:

                async with httpx.AsyncClient() as client:

                    # Opening a conversation with the user
                    response = await client.post(
                        "https://slack.com/api/conversations.open",
                        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                        json={ "users": user }
                    )
                    channel_id = response.json()["channel"]["id"]

                    # Send the message
                    response = await client.post(
                        "https://slack.com/api/chat.postMessage",
                        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                        json={"channel": channel_id, "text": msg}
                    )

                    data = response.json()
                    if not data.get("ok"):
                        return {"status": "failed", "error": data.get("error")}

        # Log time in Replicon

        # Get or create timesheet for today
        today = date.today()
        timesheet_payload = {
            "userUri": REPLICON_USER_URI,
            "date": {"year": today.year, "month": today.month, "day": today.day},
            "timesheetGetOptionUri": "urn:replicon:timesheet-get-option:create-timesheet-if-necessary"
        }

        async with httpx.AsyncClient() as client:
            ts_resp = await client.post(
                f"{REPLICON_BASE_URL}/timesheet/get-timesheet",
                headers={"Authorization": f"Bearer {REPLICON_TOKEN}"},
                json=timesheet_payload
            )

            if not ts_resp.is_success:
                raise Exception(f"Failed to get or create timesheet: {ts_resp.text}")

            ts_data = ts_resp.json()
            timesheet_uri = ts_data.get("timesheet", {}).get("uri")
            if not timesheet_uri:
                raise Exception("Failed to retrieve or create timesheet")

            # Distribute hours across commits
            if not commits:
                return

            total_hours = 8.0  # Total hours to log per MR in replicon
            hours_per_commit = total_hours / len(commits)

            # Fill timesheet
            for commit in commits:
                entry_payload = {
                    "timesheetUri": timesheet_uri,
                    "timeEntry": {
                        "date": {"year": today.year, "month": today.month, "day": today.day},
                        "hours": hours_per_commit,
                        "comments": commit.message
                    }
                }
                entry_resp = await client.post(
                    f"{REPLICON_BASE_URL}/timesheet/save-time-entry",
                    headers={"Authorization": f"Bearer {REPLICON_TOKEN}"},
                    json=entry_payload
                )

                if not entry_resp.is_success:
                    raise Exception(f"Failed to save time entry: {entry_resp.text}")

                print(entry_resp.json())

    return {"status": "ok"}


if __name__ == "__main__":
    # To run the app: uvicorn main:app --reload
    uvicorn.run(app, host="0.0.0.0", port=8000)
