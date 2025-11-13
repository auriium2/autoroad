# code style
- Only document when it actually adds stuff. Documenting a function called analyze_requirement_structure and adding a docstring that says "Analyzes the structure of the requirements" is not helpful. In such cases do not add a docstring. However, if the function is complex or has non-obvious behavior, a docstring can be helpful to explain its purpose and usage. Always aim for clarity and usefulness in documentation.

# debugging and tooling
- run python with uv
- check types with basedpyright
- if you do analysis that would produce lots of data, consider writing it to the temp/ folder at the root of the project
- if you do an analysis that you feel should be iterated on, consider also writing it to the temp/ folder
