# Windows helper scripts

Local tooling used on the development workstation: harvester backfills, portal start-up and the agent work queue. Every script resolves the repository root from its own location, so run them from anywhere:

```powershell
powershell -NoProfile -File scripts/windows/Start-Portal.ps1
```

Production does not use these scripts; see `deploy/` for the server setup.
