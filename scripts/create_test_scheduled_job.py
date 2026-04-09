#!/usr/bin/env python3
"""Create a test scheduled job for Growth Coach."""
import os
import sys
from datetime import datetime, timedelta
from google.cloud import firestore

# Set project
os.environ['GCP_PROJECT_ID'] = 'vertex-ai-middleware-prod'

def main():
    db = firestore.Client(project='vertex-ai-middleware-prod', database='(default)')

    # Get Growth Coach agent
    agents_ref = db.collection('agents')
    all_agents = list(agents_ref.stream())

    if not all_agents:
        print("ERROR: No agents found in Firestore")
        sys.exit(1)

    print(f"Found {len(all_agents)} agents:")
    for agent in all_agents:
        agent_data = agent.to_dict()
        print(f"  - {agent.id}: {agent_data}")

    # Find Growth Coach
    growth_coach = None
    for agent in all_agents:
        agent_data = agent.to_dict()
        if 'growth' in agent_data.get('name', '').lower():
            growth_coach = agent
            break

    if not growth_coach:
        print("\nERROR: Growth Coach agent not found")
        print("Using first agent as fallback")
        growth_coach = all_agents[0]

    growth_coach_data = growth_coach.to_dict()
    print(f"\nUsing agent: {growth_coach.id} ({growth_coach_data.get('name')})")

    # Get a user (first user in collection)
    users_ref = db.collection('users')
    users = list(users_ref.limit(1).stream())

    if not users:
        print("ERROR: No users found in Firestore")
        sys.exit(1)

    user = users[0]
    user_data = user.to_dict()
    print(f"Found user: {user.id} ({user_data.get('slack_user_id')})")

    # Calculate next minute
    now = datetime.utcnow()
    next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)

    # Create cron expression for next minute
    cron = f"{next_minute.minute} {next_minute.hour} {next_minute.day} {next_minute.month} *"

    print(f"\nCreating test scheduled job...")
    print(f"Current time (UTC): {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Scheduled for (UTC): {next_minute.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Cron expression: {cron}")

    # Create scheduled job
    job_data = {
        'name': 'Test Scheduled Job - Growth Coach',
        'prompt': 'This is a test of the scheduled jobs system. Please respond with a brief confirmation.',
        'agent_id': growth_coach.id,
        'user_id': user.id,
        'output_platform': 'slack',
        'schedule': cron,
        'timezone': 'UTC',
        'enabled': True,
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow(),
        'consecutive_failures': 0
    }

    # Add to Firestore
    jobs_ref = db.collection('scheduled_jobs')
    job_ref = jobs_ref.add(job_data)
    job_id = job_ref[1].id

    print(f"\n✓ Created test scheduled job: {job_id}")
    print(f"  Agent: Growth Coach")
    print(f"  User: {user_data.get('slack_user_id')} (Slack)")
    print(f"  Will run at: {next_minute.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"\nMonitor logs with:")
    print(f"  gcloud logging read 'resource.type=\"cloud_run_revision\" AND textPayload=~\"{job_id}\"' --limit=10 --project=vertex-ai-middleware-prod")

if __name__ == '__main__':
    main()
