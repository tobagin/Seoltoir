Contributing to Seoltóir

We welcome and appreciate contributions to Seoltóir! Whether it's bug reports, feature suggestions, code contributions, or improvements to documentation, your help is invaluable.
How to Contribute
1. Reporting Issues

If you encounter a bug, have a feature request, or notice any unexpected behavior, please open an issue on our GitHub repository:

    Seoltóir Issues Page (Replace with actual repo URL if different)

When reporting an issue, please include:

    A clear and concise description of the problem or feature.

    Steps to reproduce the bug (if applicable).

    Expected behavior vs. actual behavior.

    Screenshots or videos (if helpful).

    Your operating system and Seoltóir version (e.g., from flatpak info io.github.tobagin.Seoltoir or python --version).

2. Suggesting Features

If you have an idea for a new feature or improvement, feel free to open an issue or start a discussion on the repository. Describe your idea thoroughly and explain why you think it would be a valuable addition to Seoltóir.
3. Code Contributions

If you're interested in contributing code, please follow these steps:
A. Set up Your Development Environment

Refer to the Getting Started section for instructions on how to build Seoltóir from source. Ensure you can successfully build and run the application.
B. Fork the Repository

    Go to the Seoltóir GitHub repository (replace with actual repo URL).

    Click the "Fork" button in the top right corner.

C. Clone Your Fork

git clone [https://github.com/YOUR_USERNAME/seoltoir.git](https://github.com/YOUR_USERNAME/seoltoir.git)
cd seoltoir

D. Create a New Branch

Create a new branch for your feature or bug fix. Use a descriptive name (e.g., feature/add-dark-mode or fix/crash-on-startup).

git checkout -b feature/your-awesome-feature

E. Make Your Changes

    Write clean, well-commented Python code.

    Follow existing code style (e.g., using black for formatting).

    Ensure your changes adhere to Seoltóir's core principles of privacy and user control.

    If you're adding new settings, remember to update data/io.github.tobagin.Seoltoir.gschema.xml.

    If you're adding new files, remember to update meson.build.

F. Test Your Changes

Before submitting, thoroughly test your changes to ensure they work as expected and don't introduce new bugs.

# Build and run your changes
meson compile -C build
meson run -C build seoltoir

G. Commit Your Changes

Write clear and concise commit messages.

git add .
git commit -m "feat: Add a concise description of your feature or fix"

H. Push Your Branch

git push origin feature/your-awesome-feature

I. Create a Pull Request

    Go to your forked repository on GitHub.

    You should see a "Compare & pull request" button or similar. Click it.

    Provide a clear title and description for your pull request, explaining your changes and why they are valuable.

    Reference any related issues (e.g., Closes #123).

4. Documentation Contributions

If you'd like to improve the documentation:

    Fork the repository and make your changes in the docs/ directory.

    You can preview your changes locally:

    mkdocs serve

    Then open your browser to http://127.0.0.1:8000.

    Submit a pull request.

Thank you for helping make Seoltóir a better browser!