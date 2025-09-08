from fastapi import FastAPI
import uvicorn
import httpx
import os
from models import GitlabWebhookPayload
from dotenv import load_dotenv
load_dotenv() 

app = FastAPI()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

# TODO move to db or config file
PROJECT_TO_SLACK = {
    "murakoze_portal": os.getenv("MY_SLACK_USER_ID") # Currently using my slack ID cuz i don't have permission to send message to my supervisor.
}

@app.post("/webhook/gitlab")
async def gitlab_webhook(payload: GitlabWebhookPayload):

    if payload.object_kind == "merge_request":
        project_name = payload.project.name
        mr = payload.object_attributes
        commits = payload.commits or []

        slack_user = PROJECT_TO_SLACK.get(project_name)
        if slack_user:
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

            async with httpx.AsyncClient() as client:

                # Opening a conversation with the user
                response = await client.post(
                    "https://slack.com/api/conversations.open",
                    headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                    json={"users": slack_user}  # replace with actual Slack ID
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

        # TODO auto fillout replicon timesheet

    return {"status": "ok"}


if __name__ == "__main__":
    # To run the app: uvicorn main:app --reload
    uvicorn.run(app, host="0.0.0.0", port=8000)
