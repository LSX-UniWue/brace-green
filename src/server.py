import argparse
import sys
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

# Support running as script or module
if __name__ == '__main__' and __package__ is None:
    # Running as script (uv run src/server.py)
    sys.path.insert(0, str(__file__.rsplit('/', 2)[0]))
    from .executor import Executor
else:
    # Running as module
    from .executor import Executor


def main():
    parser = argparse.ArgumentParser(description="Run the BraceGreen Evaluator A2A server.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind the server")
    parser.add_argument("--port", type=int, default=9001, help="Port to bind the server")
    parser.add_argument("--card-url", type=str, help="URL to advertise in the agent card")
    parser.add_argument("--writeups-path", type=str, default="./data", help="Path to writeups directory")
    args = parser.parse_args()
    
    # Import here to use the utils function
    from .evaluator.utils import discover_all_challenges
    
    # Debug: Print discovered challenges
    print("=" * 60)
    print("🔍 BraceGreen Server Startup - Challenge Discovery")
    print("=" * 60)
    print(f"📂 Writeups path: {args.writeups_path}")
    
    import os
    abs_path = os.path.abspath(args.writeups_path)
    print(f"📂 Absolute path: {abs_path}")
    print(f"📂 Path exists: {os.path.exists(abs_path)}")
    
    if os.path.exists(abs_path):
        print(f"📂 Contents of directory:")
        try:
            for item in os.listdir(abs_path):
                item_path = os.path.join(abs_path, item)
                if os.path.isdir(item_path):
                    print(f"   📁 {item}/")
                    # Check if it has steps_enriched.json
                    steps_file = os.path.join(item_path, "steps_enriched.json")
                    if os.path.exists(steps_file):
                        print(f"      ✅ has steps_enriched.json")
                    else:
                        print(f"      ⚠️  missing steps_enriched.json")
                else:
                    print(f"   📄 {item}")
        except Exception as e:
            print(f"   ❌ Error listing directory: {e}")
    
    discovered = discover_all_challenges(args.writeups_path)
    print(f"\n🎯 Challenges discovered: {len(discovered)}")
    if discovered:
        for challenge in discovered:
            print(f"   ✓ {challenge}")
    else:
        print("   ⚠️  No challenges found!")
        print(f"   💡 Make sure challenge directories with steps_enriched.json exist in {abs_path}")
    print("=" * 60)
    print()

    skill = AgentSkill(
        id="ctf-evaluator",
        name="CTF Challenge Evaluator",
        description="Evaluates agent performance on capture-the-flag challenges",
        tags=["security", "penetration-testing", "evaluation"],
        examples=[
            "Evaluate my agent on the Funbox challenge",
            "Run all CTF challenges and report scores"
        ]
    )

    agent_card = AgentCard(
        name="BraceGreen Evaluator",
        description="Evaluates penetration testing agents on CTF challenges",
        url=args.card_url or f"http://{args.host}:{args.port}/",
        version='1.0.0',
        default_input_modes=['text', 'text/plain'],
        default_output_modes=['text', 'text/plain'],
        capabilities=AgentCapabilities(
            streaming=True,
            push_notifications=True,
            state_transition_history=False
        ),
        skills=[skill]
    )

    request_handler = DefaultRequestHandler(
        agent_executor=Executor(writeups_path=args.writeups_path),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )
    uvicorn.run(
        server.build(), 
        host=args.host, 
        port=args.port,
        timeout_keep_alive=300,  # Keep connections alive during long evals
    )


if __name__ == '__main__':
    main()

