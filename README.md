# TablePro Launcher

Open your saved TablePro connections from Alfred.

## Features

- Search all saved connections
- Filter by tags with `tag:<name>`
- Filter by groups with `group:<name>`
- Open the related SSH or host URL in your default browser
- Copy the browser URL or the generated TablePro URL
- Show an in-app help overlay with `tpro help`, `tpro --help`, or `tpro -h`

## Keyword

`tpro`

## Query examples

- `tpro`
- `tpro postgres`
- `tpro tag:production`
- `tpro group:backend`
- `tpro group:backend tag:production postgres`

## Actions

- `Enter` opens the selected connection in TablePro
- `Command+Enter` opens the SSH host or host URL in the default browser
- `Option+Enter` copies the SSH host or host URL
- `Control+Enter` copies the generated TablePro connection URL
- `Shift+Enter` shows the help overlay

## Notes

- Browser actions prefer `sshHost` when SSH is enabled.
- TablePro is launched via AppleScript first, then the connection is opened.
- The workflow reads `com.TablePro.connections`, `com.TablePro.tags`, and `com.TablePro.groups` from `~/Library/Preferences/com.TablePro.plist`.
