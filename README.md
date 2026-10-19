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
| `enter`, `1`-`9` | open a link and close the view, or show a note in full |
| `o` | open a link and stay in the view |
| `a` | add a link or one-line note (URL prefilled from the clipboard) |
| `n` | add a multi-line note in `$VISUAL` / `$EDITOR` |
| `e` / `E` | edit in the prompt / edit the value in the editor |
| `/` | filter by label or value (`esc` clears it) |
| `d` | delete (type `y` to confirm) |
| `y` | copy the value to the clipboard |
| `q`, `esc` | close |

A value that starts with `http://` or `https://` is a link; anything else is a note.

## Where data lives

Entries are state, not settings, so they are stored in `metadata.json` in the plugin's state
directory (`~/.local/state/herdr/plugins/momer.space-metadata`), not in this repository. Older
versions kept the file in the config directory; it is moved over the first time the plugin runs.

Entries are keyed by the Herdr workspace id, which stays the same across restarts, so each space
has its own list even when two spaces share a directory. Workspace ids are local to a Herdr
session, so the file is not portable between machines.

## Sidebar summary

The plugin reports a short summary (for example `2↗ 1✎`) as the `meta` token on each space. To
show it, add `$meta` to your space rows in `config.toml`, then run `herdr server reload-config`:

```toml
[ui.sidebar.spaces]
rows = [["state_icon", "workspace"], ["branch", "git_status"], ["$meta"]]
```

## License

MIT, see [LICENSE](LICENSE).
