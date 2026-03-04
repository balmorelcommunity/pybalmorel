# Developing pybalmorel

pybalmorel uses [pixi](https://pixi.prefix.dev/latest/#installation) to manage reproducible development environments. There are two environments available:

- **`default` (dev)** — for developing pybalmorel and building its documentation locally
- **`user`** — for testing pybalmorel as an end-user, with only the PyPI package installed

## Installing pixi

If you do not have pixi installed yet, follow the [official installation instructions](https://pixi.prefix.dev/latest/#installation) or run:

```bash
curl -fsSL https://pixi.sh/install.sh | sh
```

```{toctree}
:maxdepth: 1

developing/environments.md
developing/publishing.md
developing/building_docs.md
```
