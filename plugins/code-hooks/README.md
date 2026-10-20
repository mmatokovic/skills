# code-hooks

Windows toast notifications for Claude Code `Stop` and `Notification` hooks.

## Requirements

**Windows only.** The hooks use the Windows Runtime toast notification API and require PowerShell to be available on `PATH`.

On a standard Windows installation `powershell.exe` is already on `PATH`:

```
where.exe powershell
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe
```

### Running inside WSL

When Claude Code runs inside WSL, `powershell.exe` must be reachable through Windows interop. Verify with:

```sh
which powershell.exe
```

If the command returns nothing, enable Windows interop or add the Windows PowerShell directory to your WSL `PATH`:

```sh
export PATH="$PATH:/mnt/c/Windows/System32/WindowsPowerShell/v1.0"
```

## Hooks

| Hook | Script | Trigger |
|------|--------|---------|
| Stop | `hooks/stop.ps1` | Claude finishes responding |
| Notification | `hooks/notify.ps1` | Claude sends a notification event |