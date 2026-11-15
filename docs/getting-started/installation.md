# Installation

HSR Cards is an asynchronous Python library for Honkai: Star Rail images and provider data. It requires Python 3.10 or later. Install the package in your application's virtual environment:

```bash
python -m pip install hsr-cards
```

These docs describe the current repository code. A published PyPI release may contain fewer methods until the next package release. Install from source below to use the full documented API.

## Install from source

```bash
git clone https://github.com/MR-LORD-REX/hsr-cards.git
cd hsr-cards
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Use `from hsr_cards import ...` after an editable install. `src` is the source directory, rather than part of the installed package name. The repository's `main.py` resolves the local source directory itself.

## Optional browser collection

Prydwen's HTTP transport is the default. Install browser support only if you select `transport="browser"`:

```bash
python -m pip install "hsr-cards[browser]"
```

Browser collection launches the executable selected by `chrome=`; the default is the Windows Google Chrome path. Set an installed browser path explicitly on other systems. It also has separate timeout and headless settings. See [Prydwen builds](../guides/builds.md).

## Verify the installation

```bash
python -c "from hsr_cards import HonkaiStarrail, NanokaClient, PrydwenClient; print('HSR Cards ready')"
```

Imports do not load environment files, create cache directories, or open provider sessions. Data and card requests may download JSON and artwork. Keep the downloaded assets accessible to your application between runs.

Continue with the [quickstart](quickstart.md) or inspect the [card showcase](../showcase.md).
