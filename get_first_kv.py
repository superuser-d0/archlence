import json

with open('/home/cem/.gemini/antigravity-ide/brain/649a10c7-036b-425a-ba41-35d82c3fb837/.system_generated/logs/transcript.jsonl') as f:
    for line in f:
        data = json.loads(line)
        if 'dashboard.kv' in line and data.get('type') == 'VIEW_FILE':
            content = data.get('content', '')
            if 'VARLIKLARIM' in content:
                lines = content.split('\n')
                for i, l in enumerate(lines):
                    if 'VARLIKLARIM' in l:
                        print('\n'.join(lines[i+30:i+100]))
                        exit(0)
