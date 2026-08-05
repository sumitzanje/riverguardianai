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
- secrets and credentials

## Runtime Launcher

Production runtime command:

```bash
/home/arduino/riverguardianai/.venv/bin/python /home/arduino/riverguardianai/python/main_runtime.py
```

## Device Access Path

- Use Tailscale SSH for remote management.
- Do not depend on LAN IP addressing for field operations.

## Controlled Deploy Command

```bash
sudo /usr/local/sbin/riverguardian-deploy v0.1.0
```

Behavior requirements:

- Deploy only explicit approved tags.
- Validate before runtime stop.
- Preserve host-specific state and secrets.
- Restart service and verify health.
- Roll back on failed restart/health check.

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
3. On device, fetch tag into staging release directory.
4. Run syntax/import checks.
5. Switch to new release only if validation passes.
6. Restart service and verify health.
7. Roll back to previous release on failure.
