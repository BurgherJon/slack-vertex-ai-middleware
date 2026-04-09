#!/usr/bin/env python3
"""Update Sam's Google Chat configuration to use the new dedicated project."""
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
    print("Current Sam config:")
    print(f"  Platforms: {data.get('platforms', [])}")

    # Update platforms array with correct Google Chat configuration
    platforms = data.get('platforms', [])

    # Check if Google Chat platform already exists
    google_chat_exists = False
    for i, platform in enumerate(platforms):
        if platform.get('platform') == 'google_chat':
            # Update to use new service account from dedicated project
            platforms[i] = {
                'platform': 'google_chat',
                'enabled': True,
                'google_chat_service_account_secret': 'sommelier-credentials',
                'google_chat_project_id': 'sam-sommelier-chat-prod'
            }
            google_chat_exists = True
            print("\nUpdated existing Google Chat platform config")
            break

    # If Google Chat platform doesn't exist, add it
    if not google_chat_exists:
        platforms.append({
            'platform': 'google_chat',
            'enabled': True,
            'google_chat_service_account_secret': 'sommelier-credentials',
            'google_chat_project_id': 'sam-sommelier-chat-prod'
        })
        print("\nAdded new Google Chat platform config")

    # Update the agent
    sam_ref.update({'platforms': platforms})

    print("\n✓ Successfully updated Google Chat config for Sam the Sommelier")
    print(f"  Project ID: sam-sommelier-chat-prod")
    print(f"  Secret: sommelier-credentials (contains sam-sommelier@sam-sommelier-chat-prod.iam.gserviceaccount.com)")
    print(f"  Service Account: sam-sommelier@sam-sommelier-chat-prod.iam.gserviceaccount.com")
    print(f"\nUpdated platforms: {platforms}")

if __name__ == '__main__':
    main()
