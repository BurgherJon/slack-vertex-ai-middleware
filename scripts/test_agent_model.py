"""Test Agent model parsing."""
import sys
sys.path.insert(0, 'c:/Users/Jonat/projects/slack-vertex-ai-middleware')

from app.models.agent import Agent
import json

# Simulated Firestore data
firestore_data = {
  "updated_at": "2026-04-06 22:43:27.936487+00:00",
  "platforms": [
    {
      "google_chat_service_account_secret": "sommelier-credentials",
      "platform": "google_chat",
      "enabled": True,
      "google_chat_project_id": "sam-sommelier-chat-prod"
    },
    {
      "slack_bot_token_secret": "sam-sommelier-slack-token",
      "platform": "slack",
      "slack_bot_token_project_id": "sam-sommelier-chat-prod",
      "enabled": True,
      "slack_bot_id": "U0ALNDQ6EUE"
    }
  ],
  "display_name": "Sam the Som",
  "slack_bot_token": "xoxb-REDACTED-LEGACY-TOKEN",
  "vertex_ai_agent_id": "projects/404939446326/locations/us-central1/reasoningEngines/4968016296512847872",
  "slack_bot_id": "U0ALNDQ6EUE",
  "created_at": "2026-03-15 20:30:04.733865+00:00"
}

print("Testing Agent model parsing...")
try:
    agent = Agent(**firestore_data, id="hynoYrK8SLdiroWvhe1M")
    print(f"\nAgent created successfully!")
    print(f"Display name: {agent.display_name}")
    print(f"ID: {agent.id}")
    print(f"\nPlatforms: {agent.platforms}")
    print(f"Number of platforms: {len(agent.platforms) if agent.platforms else 0}")

    slack_config = agent.get_slack_config()
    print(f"\nSlack config: {slack_config}")

    if slack_config:
        print(f"Slack platform: {slack_config.platform}")
        print(f"Slack enabled: {slack_config.enabled}")
        print(f"Slack bot_id: {slack_config.slack_bot_id}")
        print(f"Slack token secret: {slack_config.slack_bot_token_secret}")
        print(f"Slack token project: {slack_config.slack_bot_token_project_id}")
    else:
        print("ERROR: No Slack config found!")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
