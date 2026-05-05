# Network Change Runbook: <CHANGE TITLE>

| Field | Value |
|---|---|
| Change ID | CHG-XXXX |
| Author | <your name> |
| Date | YYYY-MM-DD |
| Maintenance window | YYYY-MM-DD HH:MM – HH:MM <TZ> |
| Risk | Low / Medium / High |
| Approvers | <names> |
| Devices affected | <hostnames or device groups> |

## Summary

One paragraph: what is changing, why, and the user-visible blast radius. If this change touches anything north of "single VLAN on one switch", explicitly call out which traffic flows could be impacted on failure.

## Prerequisites

- [ ] Out-of-band (console / OOB management) access verified
- [ ] Pre-change config backups taken (see Pre-change validation)
- [ ] Maintenance window approved and announced
- [ ] Rollback artifact location: `<path or filename>`
- [ ] Required credentials available (vault path: `<path>`)
- [ ] Peer / on-call coverage for the window

## Pre-change validation

Run these commands and save output before making any changes. Use the output to verify rollback if needed.

```
ssh <device>
terminal length 0
show running-config | redirect flash:pre-change-<CHG-ID>.cfg
show ip route summary | append flash:pre-state-<CHG-ID>.txt
show ip ospf neighbor | append flash:pre-state-<CHG-ID>.txt
show ip bgp summary | append flash:pre-state-<CHG-ID>.txt
show interfaces status | append flash:pre-state-<CHG-ID>.txt
```

Expected baseline state: <describe what "good" looks like — neighbor counts, route counts, interface counts up>.

## Change steps

> Before each step, confirm you're on the right device. Mistyping `enable` on the wrong box is the #1 way changes go wrong.

### Step 1: <description>

```
<exact CLI or playbook command>
```

Expected result: <what you should see>

### Step 2: <description>

```
<exact CLI or playbook command>
```

Expected result: <what you should see>

(Continue for each step. Keep them small and verifiable.)

## Post-change validation

Re-run the *same* commands from pre-change validation. Diff the output. The only deltas should be the intended changes.

```
show running-config | redirect flash:post-change-<CHG-ID>.cfg
show ip route summary
show ip ospf neighbor
show ip bgp summary
show interfaces status
```

Acceptance criteria (all must pass):
- [ ] All previously-up interfaces still up
- [ ] All previously-established routing adjacencies still established
- [ ] Route count within ±X of pre-change
- [ ] <change-specific verification — e.g., new VLAN visible on trunk; new policy hits in counters>

## Rollback

If any acceptance criterion fails or unintended impact is observed:

```
configure replace flash:pre-change-<CHG-ID>.cfg force
```

(Or vendor equivalent: Junos `rollback 1; commit`; Arista `configure session ... abort`; PAN-OS `load config from pre-change.xml; commit`; FortiOS `execute restore config`.)

After rollback, re-run post-change validation commands and confirm state matches pre-change baseline.

## Communications

- **At start of window**: Notify `<channel/distribution list>`: "Beginning <change> on <devices>."
- **On completion**: Notify with summary and any deviations from plan.
- **On rollback**: Notify with reason, and schedule a follow-up.

## Post-change

- [ ] Save running config to startup (`copy run start` / `request system snapshot` / `save config`)
- [ ] Push updated config to backup system / Git
- [ ] Update IPAM/CMDB if topology changed
- [ ] Close change ticket with as-built notes
- [ ] If runbook should be reused, file it in `runbooks/` with the date and outcome
