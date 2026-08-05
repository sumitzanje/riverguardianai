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

## Release Workflow (High Level)

1. Commit and push to private repo.
2. Create and push annotated tag.
3. On device, fetch tag into staging release directory.
4. Run syntax/import checks.
5. Switch to new release only if validation passes.
6. Restart service and verify health.
7. Roll back to previous release on failure.
