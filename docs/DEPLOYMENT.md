# RiverGuardian Deployment (Controlled)

This project uses controlled, tag-approved deployments.

## Rules

- GitHub private repository is the source of truth.
- Do not auto-deploy every push.
- Deploy only approved release tags.
- Validate before switching runtime.
- Keep production state outside Git checkout.

## Production State Outside Repository

- config/settings.json
- .env
- SQLite database files
- runtime logs
- local queues
- secrets and credentials

## Runtime Launcher

Production runtime command:

```bash
cd /home/arduino/riverguardianai
./.venv/bin/python python/main_runtime.py
```

From project root, this command is incorrect:

```bash
./.venv/bin/python main_runtime.py
```

## Target Deployment Layout (Pre-Install Design)

```text
/home/arduino/riverguardian/
	current -> /home/arduino/riverguardian/releases/<tag>-<commit>
	releases/
	shared/
		venv/
		config/settings.json
		config/ambient_weather_secrets.json
		.env
		data/
		logs/
		queues/
		secrets/
		credentials/
```

Notes:
- `/home/arduino/riverguardianai` remains untouched until migration is reviewed and tested.
- `current` is switched atomically only after staged validation.
- Python environment is persistent at `shared/venv` and reused across releases.

## Device Access Path

- Use Tailscale SSH for remote management.
- Do not depend on LAN IP addressing for field operations.

## Controlled Deploy Command

```bash
sudo /usr/local/sbin/riverguardian-deploy <approved-tag>
```

Behavior requirements:

- Deploy only explicit approved tags.
- Validate before runtime stop.
- Preserve host-specific state and secrets.
- Restart service and verify health.
- Roll back on failed restart/health check.

## First-Time Migration (Explicit)

Run once on hosts currently using `/home/arduino/riverguardianai` as a normal directory:

```bash
sudo /usr/local/sbin/riverguardian-migrate-layout <approved-tag>
```

Migration behavior:
- creates backup archive of legacy install;
- initializes `/home/arduino/riverguardian/{releases,shared,state}`;
- copies private settings and secrets into `shared`;
- copies persistent data/log/queue/secret/credential directories;
- reuses or creates persistent venv at `shared/venv`;
- stages approved tag and creates `current` symlink;
- leaves `/home/arduino/riverguardianai` untouched for rollback safety.

## Install Artifacts (Review First)

Deployment artifacts live in deploy/ and must be reviewed before installation:

- deploy/riverguardian.service
- deploy/riverguardian-deploy
- deploy/riverguardian-dhcp-renew
- deploy/riverguardian-dhcp-renew.sudoers
- deploy/install-deployment.sh

Do not install sudoers automatically. Use manual review via visudo.

## Release Workflow (High Level)

1. Commit and push to private repo.
2. Create and push annotated tag.
3. On first install, run explicit migration command.
4. For each release, deploy approved tag and run staged validation.
5. Switch `current` only if validation passes.
6. Restart service and verify health.
7. Roll back to previous release target on failure.
