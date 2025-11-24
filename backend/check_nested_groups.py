"""Check for nested groups with connection_type but no threshold."""

from api.services.cache import get_requirements
from courses.requirements.parser import parse_requirement
from courses.requirements.types import RequirementGroup

def find_groups_with_connection_no_threshold(node, path="root"):
    """Recursively find groups with connection_type but no threshold."""
    issues = []
    
    if isinstance(node, RequirementGroup):
        if node.connection_type and not node.threshold:
            issues.append(f"{path}: connection_type={node.connection_type}, no threshold, title={node.title}")
        
        for i, child in enumerate(node.items):
            issues.extend(find_groups_with_connection_no_threshold(child, f"{path}.{i}"))
    
    return issues

reqs_data = get_requirements(('major6-3new',))
req_data = reqs_data['major6-3new']
parsed = parse_requirement({'reqs': req_data.get('reqs', []), 'title': 'major6-3new'})

issues = find_groups_with_connection_no_threshold(parsed)
if issues:
    print(f"Found {len(issues)} groups with connection_type but NO threshold:")
    for issue in issues[:20]:  # Show first 20
        print(f"  - {issue}")
else:
    print("No groups found with connection_type but no threshold")
