#!/usr/bin/env python3
"""Fix missing required fields in agents collection."""
import os
from google.cloud import firestore

os.environ['GCP_PROJECT_ID'] = 'vertex-ai-middleware-prod'

def main():
    db = firestore.Client(project='vertex-ai-middleware-prod', database='(default)')
    agents_ref = db.collection('agents')

    # Agent resource names from your deployment
    agent_mappings = {
        'growth-coach': {
            'vertex_ai_agent_id': 'projects/vertex-ai-middleware-prod/locations/us-central1/agents/3c15e7ce-c026-4eeb-8dbb-5edc8fa562da',
            'display_name': 'Growth Coach'
        },
        'sam-the-sommelier': {
            'vertex_ai_agent_id': 'projects/vertex-ai-middleware-prod/locations/us-central1/agents/fd738f6d-0c3d-4c4f-ba1f-ef85d1ca2f02',
            'display_name': 'Sam the Sommelier'
        }
    }

    # Get all agents
    agents = list(agents_ref.stream())

    print(f"Found {len(agents)} agents:")
    for agent in agents:
        data = agent.to_dict()
        print(f"\nAgent ID: {agent.id}")
        print(f"Current fields: {list(data.keys())}")

        # Check if agent matches one of our known agents
        if agent.id in agent_mappings:
            mapping = agent_mappings[agent.id]

            # Add missing fields
            updates = {}
            if 'vertex_ai_agent_id' not in data or data.get('vertex_ai_agent_id') == '_placeholder':
                updates['vertex_ai_agent_id'] = mapping['vertex_ai_agent_id']
                print(f"  Adding vertex_ai_agent_id: {mapping['vertex_ai_agent_id']}")

            if 'display_name' not in data or data.get('display_name') == '_placeholder':
                updates['display_name'] = mapping['display_name']
                print(f"  Adding display_name: {mapping['display_name']}")

            if updates:
                agents_ref.document(agent.id).update(updates)
                print(f"  ✓ Updated agent {agent.id}")
            else:
                print(f"  No updates needed for {agent.id}")
        else:
            print(f"  WARNING: Unknown agent {agent.id}, skipping")

    print("\n✓ Agent field fixes complete")

if __name__ == '__main__':
    main()
