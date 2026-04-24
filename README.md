# gen-ai-fsms

AI-Assisted generation of bespoke food safety management systems for restaurants.


## Collaboration

Use the remote Git repository as the central source of truth. Do not manually copy project folders between machines, and do not work directly on the main branch.

### Quick start
```bash
git clone https://github.com/JoseWongg/gen-ai-fsms
cd gen-ai-fsms
```
Create a local virtual environment and activate it using the command appropriate for your operating system and shell.
```bash
python -m venv .venv
```
Install the project in editable mode with development dependencies (includes pytest, httpx, and all production dependencies):
```bash
python -m pip install -e ".[dev]"
```
**For production or CI environments** (no tests needed):
Install only production dependencies with:

```bash
 python -m pip install -e .
```

The file requirements.txt is an automatically generated lock file for reproducibility. You can ignore it for local development; pyproject.toml is the source of truth.

### Required branch workflow

Before making any changes, create and switch to a feature branch. Do not develop directly on main.

```bash
git checkout -b feature/short-description
git push -u origin feature/short-description
```
All work in progress must be done on a feature branch.



## Contact / Support
Developed by Jose Wong for the University of Salford.

For setup, usage, or technical issues: [Issues](https://github.com/JoseWongg/gen-ai-fsms/issues) 

Intellectual property and software ownership belong to the University of Salford.

For permissions or licensing enquiries, contact the University of Salford.

## License
Proprietary software. All rights reserved.
See the [LICENSE](LICENSE) file for details.