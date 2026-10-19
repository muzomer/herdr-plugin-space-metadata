# Space metadata

A [Herdr](https://herdr.dev) plugin to attach links (Jira, Sentry, chat threads) and notes to a
space, and browse them from the keyboard. Python 3, standard library only, no build step.

## Install

```sh
herdr plugin install muzomer/herdr-plugin-space-metadata
```

For local development:

```sh
herdr plugin link .
```

Bind a key in your Herdr config (`prefix` is your leader):

```toml
[[keys.command]]
key = "prefix+m"
type = "plugin_action"
command = "momer.space-metadata.open"
description = "space metadata"
```

## Keys

| Key | Action |
| --- | --- |
| `j` / `k`, arrows | move |
| `enter`, `1`-`9` | open a link, or show a note in full |
| `a` | add a link or one-line note (URL prefilled from the clipboard) |
| `n` | add a multi-line note in `$VISUAL` / `$EDITOR` |
| `e` / `E` | edit in the prompt / edit the value in the editor |
| `/` | filter by label or value (`esc` clears it) |
| `d` | delete (type `y` to confirm) |
| `y` | copy the value to the clipboard |
| `q`, `esc` | close |

A value that starts with `http://` or `https://` is a link; anything else is a note.

## Where data lives

Entries are stored in `metadata.json` in the plugin's config directory
(`herdr plugin config-dir momer.space-metadata`), not in this repository. They are keyed by
`<git remote>#<directory name>`, so the same checkout shares its list across machines if you copy
the file. Directories without a git remote are keyed by absolute path.

## Sidebar summary

The plugin reports a short summary (for example `2↗ 1✎`) as the `meta` token on each space. To
show it, add `$meta` to your space rows in `config.toml`, then run `herdr server reload-config`:

```toml
[ui.sidebar.spaces]
rows = [["state_icon", "workspace"], ["branch", "git_status"], ["$meta"]]
```

## License

MIT, see [LICENSE](LICENSE).
