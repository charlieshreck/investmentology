Start a Claude-Gemini collaboration workflow for an investmentology planning session.

Usage: /invest-collaborate <topic>

This launches the collaboration workflow targeting the Learning Investmentology collection in Outline.

Steps:
1. Take the topic from $ARGUMENTS or ask for it
2. Run: `python3 /home/investmentology/scripts/collaborate.py start "<topic>" --collection 4A1fLp8aqX --goal "<topic description>"`
3. Follow the workflow phases as prompted
4. Use `python3 /home/investmentology/scripts/collaborate.py run <checkpoint>` to advance

Available collaboration commands:
- `start` - Begin new workflow
- `status` - Check current workflow status
- `resume` - Resume latest workflow
- `run <checkpoint>` - Execute next phase
- `list` - List all workflows
