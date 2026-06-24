# Examples

Interactive front-ends for assembling a `SpecConfig` (the authoritative input to
processing — see `docs/spec-config-inventory.md`). Both are thin shells over
`cstar_forge.spec_config_resolve.build_spec_config`; all resolution/validation lives
in the resolver.

## In a Jupyter notebook

- **`spec-config-wizard.ipynb`** — run the wizard inline, then inspect `wiz.config`.
  Good for exploring / scripting.

```python
from cstar_forge.spec_config_wizard import SpecConfigWizard
wiz = SpecConfigWizard()
wiz.display()
# ... build & review ...  then:  cfg = wiz.config
```

## As a standalone web app (Voilà)

- **`spec-config-wizard-app.ipynb`** — a code-free "form" view, served by
  [Voilà](https://voila.readthedocs.io/) (pure Python, `pip install voila`, no admin).

```bash
./examples/run-wizard-app.sh        # opens http://localhost:8866
```

On an HPC **login node** (no browser there), bind locally and SSH-forward from your
laptop:

```bash
# on the login node:
./examples/run-wizard-app.sh --no-browser
# on your laptop:
ssh -N -L 8866:localhost:8866 <user>@<login-node>
# then open http://localhost:8866 locally
```

Use the **Download** link to save `spec_config.yml` to your machine (works in the
browser without server file access), or **Save to disk** to write it on the host
running Voilà. Take the file to the machine of your choice to run the processing
step.

> Portability note: the builder needs only `pydantic` + `pyyaml` (and `ipywidgets`/
> `voila` for the UI) — no ROMS / C-Star / roms_tools. The one exception is the
> optional **Compute dt (CFL)** button, which builds a grid via `roms_tools`; leave
> it and enter `dt` directly to stay fully lightweight.
