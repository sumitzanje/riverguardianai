# RiverGuardian Recovery

## Rollback after a failed deployment

1. Check service status:

```bash
sudo systemctl status riverguardian.service --no-pager
```

2. Check recent deploy log:

```bash
tail -n 20 /home/arduino/.riverguardian/deploy.log
```

3. Roll back to a known good tag:

```bash
sudo /usr/local/sbin/riverguardian-deploy <known-good-tag>
```

## Emergency runtime recovery

1. Confirm LTE route:

```bash
ip route get 8.8.8.8
```

Expected interface: enx024bb3b9ebe5.

2. Confirm Tailscale service:

```bash
systemctl is-active tailscaled
```

3. Restart runtime:

```bash
sudo systemctl restart riverguardian.service
```

4. Check logs:

```bash
journalctl -u riverguardian.service -n 100 --no-pager
```
