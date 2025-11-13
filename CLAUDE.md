# code style
- Only document when it actually adds stuff. Documenting a function called analyze_requirement_structure and adding a docstring that says "Analyzes the structure of the requirements" is not helpful. In such cases do not add a docstring. However, if the function is complex or has non-obvious behavior, a docstring can be helpful to explain its purpose and usage. Always aim for clarity and usefulness in documentation.

# debugging and tooling
- run python with uv, and use uv for dependency management.
- check types with basedpyright

# python specific
- don't add __init__ files please
