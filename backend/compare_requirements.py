"""Compare Course 1 vs Course 6-3 requirement structures."""

from api.services.cache import get_requirements
from courses.requirements.parser import parse_requirement
import json

reqs_data = get_requirements(('major1', 'major6-3new'))

for key in ['major1', 'major6-3new']:
    if key in reqs_data:
        print(f"\n{'='*60}")
        print(f"{key} ROOT STRUCTURE:")
        print(f"{'='*60}")
        req_data = reqs_data[key]
        
        # Show raw structure
        if 'reqs' in req_data:
            root_reqs = req_data['reqs']
            print(f"Root has {len(root_reqs)} items")
            print(f"Root title: {req_data.get('title', 'NO TITLE')}")
            print(f"Root connection-type: {req_data.get('connection-type', 'NONE')}")
            print(f"Root threshold: {req_data.get('threshold', 'NONE')}")
            
        # Parse and show structure
        parsed = parse_requirement({'reqs': req_data.get('reqs', []), 'title': key})
        print(f"\nParsed root:")
        print(f"  - Type: {type(parsed).__name__}")
        print(f"  - Connection type: {parsed.connection_type}")
        print(f"  - Has threshold: {parsed.threshold is not None}")
        if parsed.threshold:
            print(f"  - Threshold: {parsed.threshold.type} {parsed.threshold.cutoff} {parsed.threshold.criterion}")
        print(f"  - Num children: {len(parsed.items)}")

