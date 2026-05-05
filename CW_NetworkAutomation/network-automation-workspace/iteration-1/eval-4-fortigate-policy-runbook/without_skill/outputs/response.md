# FortiGate 100F — Add Policy: DMZ to Internal Server (TCP/8443)

## Overview

This runbook covers adding a new firewall policy on a FortiGate 100F running FortiOS 7.2 (no VDOMs) to allow TCP/8443 traffic from the DMZ zone to the internal server at 10.20.30.40.

## Pre-Change Checks

1. **Backup current configuration**:
   - Via GUI: System → Settings → Configuration → Backup
   - Or CLI: `execute backup config tftp <filename> <server-ip>`

2. **Verify zone setup**:
   ```
   show system zone
   ```

3. **Note existing policy IDs** to avoid collisions:
   ```
   show firewall policy
   ```

4. **Confirm appropriate change window** is open and stakeholders are notified.

## Change Steps

### Step 1: Define the address object

```
config firewall address
    edit "Internal-App-Server"
        set subnet 10.20.30.40/32
    next
end
```

### Step 2: Define a custom service for TCP/8443

```
config firewall service custom
    edit "TCP-8443"
        set protocol TCP
        set tcp-portrange 8443
    next
end
```

### Step 3: Add the firewall policy

```
config firewall policy
    edit 0
        set name "DMZ-to-AppServer-8443"
        set srcintf "dmz"
        set dstintf "internal"
        set srcaddr "all"
        set dstaddr "Internal-App-Server"
        set action accept
        set schedule "always"
        set service "TCP-8443"
        set logtraffic all
    next
end
```

The `edit 0` lets FortiOS auto-assign a policy ID. Note the ID for later.

## Validation

### Verify the policy was created

```
show firewall policy
```

Look for the new policy in the list. Verify the source/destination zones, address, and service are correct.

### Test connectivity from a DMZ host

From a workstation in the DMZ zone:
```
telnet 10.20.30.40 8443
```

A successful connection (or "Connected to 10.20.30.40") confirms the policy is working.

### Check policy hit count

```
diagnose firewall iprope lookup
```

Or via GUI: Policy & Objects → Firewall Policy, look at the hit counter for the new policy.

### Check logs

Forward Traffic logs in the GUI (Log & Report → Forward Traffic) should show entries matching the new policy.

## Rollback

If something goes wrong:

### Option A: Disable the policy

```
config firewall policy
    edit <policy-id>
        set status disable
    next
end
```

This keeps the policy defined but inactive.

### Option B: Delete the policy and objects

```
config firewall policy
    delete <policy-id>
end

config firewall service custom
    delete TCP-8443
end

config firewall address
    delete Internal-App-Server
end
```

### Option C: Restore from backup

```
execute restore config tftp <filename> <server-ip>
```

This will reboot the firewall — only use if other rollback options fail.

## Post-Change

1. Save configuration:
   ```
   execute save
   ```
   (Note: FortiOS typically auto-saves, but explicit save is good practice.)

2. Update documentation with the new policy ID and details.

3. Notify stakeholders the change is complete.

## Notes for the Junior Engineer

- Always run commands one at a time and verify each step before proceeding.
- The `0` in `edit 0` lets FortiOS pick an unused ID automatically.
- If you see errors about the address object or service already existing, someone may have added them previously — verify they match what you need.
- Console access is your friend if SSH stops working — keep the console cable handy.
- Don't forget to update the change ticket with the actual policy ID after creation.
