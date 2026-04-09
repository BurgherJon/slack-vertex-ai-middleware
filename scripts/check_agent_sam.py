"""Check Sam agent configuration in Firestore."""
from google.cloud import firestore
import json

def check_agent(agent_id: str):
    """Check agent configuration."""
    db = firestore.Client(project="vertex-ai-middleware-prod")
    agent_ref = db.collection('agents').document(agent_id)

    agent_doc = agent_ref.get()
    if not agent_doc.exists:
        print(f"Agent {agent_id} not found!")
        return

    agent_data = agent_doc.to_dict()
    print(f"\nAgent: {agent_data.get('display_name')}")
    print(f"ID: {agent_id}")
    print(f"\nFull data:")
    print(json.dumps(agent_data, indent=2, default=str))

if __name__ == '__main__':
    # Check Sam agent
    check_agent("hynoYrK8SLdiroWvhe1M")
