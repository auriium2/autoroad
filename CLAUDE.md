# code style
- Only document when it actually adds stuff. Documenting a function called analyze_requirement_structure and adding a docstring that says "Analyzes the structure of the requirements" is not helpful. In such cases do not add a docstring. However, if the function is complex or has non-obvious behavior, a docstring can be helpful to explain its purpose and usage. Always aim for clarity and usefulness in documentation.

# codestyle
- maps should use the naming convention key2value. For example, if you have a map that maps course IDs to course names, it should be named courseId2courseName.

# python specific
- run python with uv, and use uv for dependency management.
- don't add __init__ files please
- check types with basedpyright

# web specific
- when writing divs, if the div
