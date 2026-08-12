# MarketEdge UK launcher

`MarketEdge.exe` (built from `main_windows.go`, repo root) is a small
native Windows program — not a Python/Node wrapper, not a script-to-exe
conversion — that:

1. Confirms Docker Desktop is installed and running.
2. Creates `.env` from `.env.example` on first run if it doesn't exist yet
   (safe — the stack boots fine with every credential blank, connectors
   just idle in `PAPER` mode).
3. Runs `docker compose up -d --build` in the repo root.
4. Polls `http://localhost:8000/v1/health` until the API answers.
5. Opens `http://localhost:5173` (the dashboard) in your default browser.

It never leaves a console window open — every status update is a message
box. It does **not** install Docker itself: this app is a multi-container
stack (Postgres, Redis, the API, two background workers, the web UI), and
that isn't something a single .exe can replace without reimplementing all
of those as native Windows services. If Docker Desktop isn't found or
isn't running, the launcher says so and stops rather than guessing.

## Rebuilding it

The launcher is pure Go standard library — no external dependencies, so it
cross-compiles from any platform with Go installed (this repo's own build
was done from Linux):

```bash
make launcher
# or directly:
cd launcher && GOOS=windows GOARCH=amd64 go build -ldflags="-H=windowsgui" -o ../MarketEdge.exe .
```

`-H=windowsgui` is what suppresses the console window. CI (`.github/workflows/ci.yml`,
`launcher` job) rebuilds it on every push and confirms a valid Windows PE
binary comes out, so this stays buildable as the rest of the repo changes.

## Why not a "real" installer

A full installer (MSI/NSIS bundling Docker Desktop itself, or a
from-scratch native port of Postgres/Redis/FastAPI/the workers) is out of
scope for this stage of the build — the spec's product boundary is a
personal-use tool, and Docker Compose is already how every environment
(local dev, this launcher, eventually a small VPS) runs the same stack
identically. If distributing this more broadly ever becomes a goal, that's
a deliberate future decision, not something to bolt on silently here.
