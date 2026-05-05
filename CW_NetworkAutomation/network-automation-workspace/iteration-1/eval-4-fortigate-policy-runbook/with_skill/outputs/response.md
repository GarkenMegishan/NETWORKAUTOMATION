# Network Change Runbook: Allow TCP/8443 from DMZ to internal app server

| Field | Value |
|---|---|
| Change ID | CHG-NET-001 |
| Author | <your name> |
| Date | 2026-05-05 |
| Maintenance window | Tonight, 22:00–23:00 local |
| Risk | Low |
| Approvers | <network manager>, <security team rep> |
| Devices affected | FortiGate 100F (FortiOS 7.2, no VDOMs) |

## Summary

Add a new firewall policy permitting TCP/8443 from the DMZ zone to a single internal server `10.20.30.40` for application access. No VDOMs are in play. The change is additive only — no existing policy is modified or deleted, so blast radius is limited to traffic that would now match this rule. If the rule is misordered or misconfigured, worst case is the new traffic doesn't pass; existing flows are unaffected.

## Prerequisites

- [ ] Out-of-band / console access to the FortiGate verified (in case the change locks management out — unlikely here since management isn't on DMZ, but still verify)
- [ ] Pre-change config backup downloaded (see Pre-change validation)
- [ ] Maintenance window approved
- [ ] Engineer is logged into the FortiGate as an admin with policy-edit privilege
- [ ] Confirmation that `dmz` and `internal` zones already exist on this FortiGate (they almost certainly do; verify in Step 1)

## Pre-change validation

Run before making any changes. Save the output for rollback comparison.

```
# Backup the running config to local file (then SCP it off)
execute backup config tftp pre-change-CHG-NET-001.conf <tftp-server-ip>

# OR via GUI: System > Settings > Configuration Backup

# Verify zones exist
show system zone

# Note current policy IDs in use
show firewall policy | grep edit

# Confirm no existing object named obj-app-server-8443 (we're adding new)
show firewall address | grep app-server

# Confirm no existing custom service for tcp/8443
show firewall service custom | grep 8443
```

Expected baseline: `dmz` and `internal` zones present; no conflicting object/policy names.

## Change steps

> Before each step, verify you're on the right device. The FortiGate prompt should read `FGT100F-...`. If a VDOM prompt appears, abort — the change assumes no VDOMs.

### Step 1: Create the address object for the destination server

```
config firewall address
    edit "obj-app-server-8443"
        set type ipmask
        set subnet 10.20.30.40 255.255.255.255
        set comment "App server reachable from DMZ on TCP/8443 — CHG-NET-001"
    next
end
```

Expected result: command returns to root prompt with no error. Verify with:

```
show firewall address obj-app-server-8443
```

The output should show the subnet `10.20.30.40 255.255.255.255`. Note: FortiOS uses `IP MASK` form (space-separated), not CIDR.

### Step 2: Create the custom service for TCP/8443

```
config firewall service custom
    edit "svc-tcp-8443"
        set tcp-portrange 8443
        set comment "Custom TCP/8443 — CHG-NET-001"
    next
end
```

Expected result: prompt returns clean. Verify with:

```
show firewall service custom svc-tcp-8443
```

### Step 3: Create the firewall policy

Before creating, find an unused policy ID. If your policy IDs are sparse (e.g., 10, 20, 30...), pick one in the right range; if dense, FortiOS auto-assigns the next ID if you use `edit 0`.

```
config firewall policy
    edit 0
        set name "ALLOW-DMZ-TO-APPSRV-8443"
        set srcintf "dmz"
        set dstintf "internal"
        set srcaddr "all"
        set dstaddr "obj-app-server-8443"
        set action accept
        set schedule "always"
        set service "svc-tcp-8443"
        set logtraffic all
        set comments "CHG-NET-001 — allow TCP/8443 from DMZ to app server"
    next
end
```

Expected result: prompt returns and the assigned policy ID is shown. Note that ID for the rollback step.

If you need the rule to land in a specific position (e.g., before a broader DMZ deny), use `move <id> before <other-id>` after creation.

## Post-change validation

### Test 1: Policy lookup (does FortiOS pick this rule for the intended traffic?)

```
diagnose firewall iprope lookup <some-dmz-source-ip> 49152 10.20.30.40 8443 6
```

(Trailing `6` = TCP protocol.) The output should reference your new policy ID and the `accept` action. If it references a different policy, the rule order is wrong — adjust with `move`.

### Test 2: Real traffic (have someone in DMZ initiate the connection)

```
# From a host on DMZ:
nc -zv 10.20.30.40 8443
# OR
curl -kv https://10.20.30.40:8443/
```

Expect a TCP SYN/ACK from the server (success means the firewall passed it).

### Test 3: Confirm logging

```
execute log filter category 0       # 0 = traffic
execute log filter device 0
execute log filter field policyid <new-policy-id>
execute log display
```

You should see hits from the test traffic. If no hits but traffic seems to flow, check that `set logtraffic all` was actually applied.

Acceptance criteria (all must pass):
- [ ] Policy lookup (Test 1) references the new policy ID with `accept`.
- [ ] Real traffic (Test 2) connects.
- [ ] Log shows hits (Test 3).
- [ ] No prior policies broken (random sanity-check on an existing internal-bound flow).

## Rollback

If any acceptance criterion fails or unintended impact is observed, delete the additions in reverse order (policy first, then service, then address):

```
# Delete the policy (use the ID from Step 3)
config firewall policy
    delete <new-policy-id>
end

# Delete the service
config firewall service custom
    delete svc-tcp-8443
end

# Delete the address object
config firewall address
    delete obj-app-server-8443
end
```

Reverse order matters: you can't delete an address object that's still referenced by a policy. Verify with `show firewall policy` after each deletion that nothing references the next thing you'll delete.

If the delete-in-reverse-order approach fails for any reason, the nuclear option is `execute restore config tftp pre-change-CHG-NET-001.conf <tftp-server-ip>` followed by reboot — but this restores everything to the pre-change snapshot, including any other unrelated changes that may have happened since. Prefer the surgical deletions.

## Communications

- **Window start (22:00)**: Notify network/security teams: "Beginning CHG-NET-001 on FGT100F."
- **On completion**: "CHG-NET-001 complete. TCP/8443 from DMZ to 10.20.30.40 now permitted; verified via policy lookup and live traffic."
- **On rollback**: "CHG-NET-001 rolled back due to <reason>. App server 10.20.30.40 still unreachable on TCP/8443 from DMZ. Will reschedule after RCA."

## Post-change

- [ ] No need to `execute save` — FortiOS persists config automatically when commands return cleanly.
- [ ] Push updated config snapshot to backup repo / Git.
- [ ] Update internal IPAM/firewall-rule docs with the new policy ID, source, destination, port.
- [ ] Close ticket with as-built notes including the assigned policy ID.
