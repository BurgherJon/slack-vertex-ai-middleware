#!/usr/bin/env python3
"""Enable Google Chat for Sam the Sommelier agent."""
import os
from google.cloud import firestore

os.environ['GCP_PROJECT_ID'] = 'vertex-ai-middleware-prod'

def main():
    db = firestore.Client(project='vertex-ai-middleware-prod', database='(default)')

    # Get Sam the Sommelier agent
    sam_ref = db.collection('agents').document('hynoYrK8SLdiroWvhe1M')
    sam = sam_ref.get()

    if not sam.exists:
        print("ERROR: Sam the Sommelier agent not found")
        return

    data = sam.to_dict()
    print(f"Current Sam config: {data}")

    # Add or update platforms array with Google Chat
    platforms = data.get('platforms', [])

    # Check if Google Chat platform already exists
    google_chat_exists = False
    for i, platform in enumerate(platforms):
        if platform.get('platform') == 'google_chat':
            platforms[i]['enabled'] = True
            platforms[i]['google_chat_service_account_secret'] = 'sommelier-credentials'
            google_chat_exists = True
            print("Updated existing Google Chat platform config")
            break

    # If Google Chat platform doesn't exist, add it
    if not google_chat_exists:
        platforms.append({
            'platform': 'google_chat',
            'enabled': True,
            'google_chat_service_account_secret': 'sommelier-credentials'
        })
        print("Added new Google Chat platform config")

    # Update the agent
    sam_ref.update({'platforms': platforms})

    print("\n✓ Successfully enabled Google Chat for Sam the Sommelier")
    print(f"  Secret: sommelier-credentials")
    print(f"  Platforms: {platforms}")

if __name__ == '__main__':
    main()
