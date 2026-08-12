// MarketEdge UK launcher.
//
// A double-clickable Windows entry point for the docker-compose stack this
// repo is built around — there is no way to avoid the Docker Compose
// dependency (Postgres, Redis, the API, two workers, and the web UI are
// separate services), so this launcher's job is narrow and honest: make
// sure Docker is actually running, start the stack, wait for it to answer
// health checks, then open the dashboard in the default browser. It does
// not install Docker itself — see the message box text below for why.
//
// Build (from the repo root, on any OS with Go installed — this cross
// compiles cleanly since it only uses the standard library):
//
//	GOOS=windows GOARCH=amd64 go build -ldflags="-H=windowsgui" -o MarketEdge.exe ./launcher
//
// The -H=windowsgui linker flag builds a GUI-subsystem binary so double
// clicking it never flashes a console window; message boxes are the only
// UI. The .exe must stay in the repository root (next to
// docker-compose.yml) — it operates on its own directory.
package main

import (
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
	"time"
	"unsafe"
)

var (
	user32          = syscall.NewLazyDLL("user32.dll")
	procMessageBoxW = user32.NewProc("MessageBoxW")
)

const (
	mbIconInformation = 0x00000040
	mbIconError       = 0x00000010
	mbIconWarning     = 0x00000030
)

func messageBox(text, title string, flags uintptr) {
	t, _ := syscall.UTF16PtrFromString(title)
	m, _ := syscall.UTF16PtrFromString(text)
	_, _, _ = procMessageBoxW.Call(0, uintptr(unsafe.Pointer(m)), uintptr(unsafe.Pointer(t)), flags)
}

// hiddenCommand builds an *exec.Cmd that never flashes a console window,
// even though this process itself has none (GUI subsystem) — without this,
// Windows spawns a fresh visible console for each child process.
func hiddenCommand(name string, args ...string) *exec.Cmd {
	cmd := exec.Command(name, args...)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	return cmd
}

func main() {
	exePath, err := os.Executable()
	if err != nil {
		messageBox("Could not determine install location:\n\n"+err.Error(), "MarketEdge UK", mbIconError)
		os.Exit(1)
	}
	dir := filepath.Dir(exePath)
	if err := os.Chdir(dir); err != nil {
		messageBox("Could not access the install folder:\n\n"+err.Error(), "MarketEdge UK", mbIconError)
		os.Exit(1)
	}

	// First run: create .env from the template so the stack has something
	// to read. It boots fine with every credential left blank — connectors
	// just idle in PAPER mode (see docs/STATUS.md) — so this is safe by
	// default. It does NOT overwrite an existing .env.
	if _, err := os.Stat(".env"); os.IsNotExist(err) {
		if data, readErr := os.ReadFile(".env.example"); readErr == nil {
			_ = os.WriteFile(".env", data, 0o644)
		}
	}

	if _, err := exec.LookPath("docker"); err != nil {
		messageBox(
			"Docker Desktop was not found on this machine.\n\n"+
				"MarketEdge UK runs as a set of Docker containers (database, cache, API, "+
				"background workers and the web dashboard) — that's not something a single "+
				".exe can replace.\n\n"+
				"Install Docker Desktop from https://www.docker.com/products/docker-desktop, "+
				"start it, then run MarketEdge UK again.",
			"MarketEdge UK — Docker required", mbIconError,
		)
		os.Exit(1)
	}

	if err := hiddenCommand("docker", "info").Run(); err != nil {
		messageBox(
			"Docker Desktop is installed but doesn't appear to be running.\n\n"+
				"Start Docker Desktop, wait for it to finish starting (the whale icon in your "+
				"system tray stops animating), then run MarketEdge UK again.",
			"MarketEdge UK — Docker not running", mbIconWarning,
		)
		os.Exit(1)
	}

	messageBox(
		"Starting MarketEdge UK.\n\n"+
			"The first run can take several minutes while Docker builds the images — "+
			"later runs are much faster. Your dashboard will open automatically once "+
			"it's ready.\n\n"+
			"Note: without Betfair/odds-provider credentials in .env, everything still "+
			"starts fine — you just won't see live prices yet. Add credentials to .env "+
			"and run MarketEdge UK again whenever you're ready for those.",
		"MarketEdge UK", mbIconInformation,
	)

	upCmd := hiddenCommand("docker", "compose", "up", "-d", "--build")
	if err := upCmd.Run(); err != nil {
		messageBox(
			"MarketEdge UK failed to start.\n\n"+
				"Open a terminal in this folder and run:\n\n    docker compose up --build\n\n"+
				"to see the full error.",
			"MarketEdge UK — startup failed", mbIconError,
		)
		os.Exit(1)
	}

	client := http.Client{Timeout: 3 * time.Second}
	healthy := false
	for i := 0; i < 180; i++ { // up to ~15 minutes for a slow first build
		resp, err := client.Get("http://localhost:8000/v1/health")
		if err == nil {
			resp.Body.Close()
			if resp.StatusCode == http.StatusOK {
				healthy = true
				break
			}
		}
		time.Sleep(5 * time.Second)
	}

	if !healthy {
		messageBox(
			"MarketEdge UK is taking longer than expected to start.\n\n"+
				"It may still be starting in the background — check Docker Desktop's "+
				"container logs, or open http://localhost:5173 yourself in a few minutes.",
			"MarketEdge UK — still starting", mbIconWarning,
		)
		os.Exit(0)
	}

	_ = hiddenCommand("cmd", "/c", "start", "http://localhost:5173").Start()
}
