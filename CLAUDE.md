# code style
- Only document when it actually adds stuff. Documenting a function called analyze_requirement_structure and adding a docstring that says "Analyzes the structure of the requirements" is not helpful. In such cases do not add a docstring. However, if the function is complex or has non-obvious behavior, a docstring can be helpful to explain its purpose and usage. Always aim for clarity and usefulness in documentation.
- Maps should use the naming convention key2value. For example, if you have a map that maps course IDs to course names, it should be named courseId2courseName.
- Don't write any README files. Do not touch my README files. They are sacred and should not be modified by anyone other than me. If you want to add documentation, add it to the appropriate code files as docstrings or comments.

# python specific
- Run python with uv, and use uv for dependency management.
- Don't add __init__ files please. If you need to import something from a subdirectory, just use the full path. For example, if you have a file called utils.py in a subdirectory called helpers, you can import it with from helpers.utils import function_name. This way you don't have to worry about __init__ files and it keeps the code cleaner.
- Check types with basedpyright
- In constructors, please use type annotations for all parameters and assigments to local variables. This helps with readability and allows for better type checking.

# web specific
- For simple, configuration-like JSX components with static props (especially UI library components like Handle, Icon, Button, etc.), format them on a single line when:
  - The component has no children or self-closes
  - Props are mostly static values or simple expressions
  - The total line length stays under ~120 characters
