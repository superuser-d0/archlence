import json
with open('/home/cem/.gemini/antigravity-ide/brain/649a10c7-036b-425a-ba41-35d82c3fb837/.system_generated/logs/transcript.jsonl') as f:
    for line in f:
        data = json.loads(line)
        if data.get('type') == 'PLANNER_RESPONSE':
            for call in data.get('tool_calls', []):
                if call['name'] == 'multi_replace_file_content' and 'dashboard.kv' in str(call):
                    print("="*40)
                    print("Target Content:")
                    print(call['args']['ReplacementChunks'])
