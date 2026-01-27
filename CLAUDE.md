# general
- If the user asks you to write unit tests, you write unit tests, run the unit tests, and then the unit tests fail, the most likely situation is not that the unit tests have a bug, but that the original code has a bug. If this occurs immediately ask the user for feedback and do not continue.

# code style
- Only document when it actually adds stuff. Documenting a function called analyze_requirement_structure and adding a docstring that says "Analyzes the structure of the requirements" is not helpful. In such cases do not add a docstring. However, if the function is complex or has non-obvious behavior, a docstring can be helpful to explain its purpose and usage. Always aim for clarity and usefulness in documentation.
- Maps should use the naming convention key2value. For example, if you have a map that maps course IDs to course names, it should be named courseId2courseName.
- Don't write any README files. Do not touch my README files. They are sacred and should not be modified by anyone other than me. If you want to add documentation, add it to the appropriate code files as docstrings or comments.

# python specific
- Run python with uv, and use uv for dependency management.
- In constructors, please use type annotations for all parameters and assigments to local variables. This helps with readability and allows for better type checking.
- All imports go at the top of the file, unless explicitly lazy-loading

# web specific
- For simple, configuration-like JSX components with static props (especially UI library components like Handle, Icon, Button, etc.), format them on a single line when:
  - The component has no children or self-closes
  - Props are mostly static values or simple expressions
  - The total line length stays under ~120 characters
