#!/bin/bash
# Start all screen sessions for Haute Banque

# Kill any existing sessions first
for s in claude-invest gemini-invest dev; do
    screen -S $s -X quit 2>/dev/null
done

sleep 1

# Start fresh sessions
screen -dmS claude-invest bash -c "cd /home/investmentology && source .venv/bin/activate && exec claude"
screen -dmS gemini-invest bash -c "cd /home/investmentology && source .venv/bin/activate && exec gemini"
screen -dmS dev bash -c "cd /home/investmentology && source .venv/bin/activate && exec bash"

echo "Started: claude-invest, gemini-invest, dev"
screen -ls
