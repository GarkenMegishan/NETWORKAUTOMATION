# Fortinet FortiOS

FortiOS uses a `config` / `edit` / `set` / `next` / `end` block syntax — different from both Cisco and Palo Alto. Every configuration is scoped inside a `config <section>` block, and entries are addressed by ID or name. Generate configs that respect this structure exactly — partial blocks won't apply.

Two deployment modes:
- **Standalone FortiGate** — configure on the device.
- **FortiManager-managed** — central management with ADOMs (Administrative Domains), policy packages, device groups. Use FortiManager flavor when the user mentions FortiManager or has more than a few devices.

## Idempotency

`config` / `edit` / `set` / `next` / `end` is idempotent — re-applying the same block is a no-op. Order within a config block doesn't matter for `set` lines, but the `edit` ID/name does — re-editing entry 5 modifies entry 5, doesn't create a new one.

The `fortinet.fortios` Ansible collection wraps the REST API and is generally the cleanest automation surface.

## Block syntax — read carefully

Every config push must be wrapped:

```
config firewall address
    edit "obj-web-server"
        set subnet 10.1.1.10 255.255.255.255
    next
    edit "obj-rfc1918-10"
        set subnet 10.0.0.0 255.0.0.0
    next
end
```

If you forget the closing `end`, nothing applies. If you forget `next` between entries, you redefine the same one. This is the #1 mistake when generating FortiOS config — be meticulous.

## Object model

Similar shape to PAN-OS, with FortiOS naming:

```
Address objects → Address groups
Service objects (firewall service custom) → Service groups
Schedules
Application control profiles, AV profiles, IPS sensors, URL filters
Security profile groups
                ↓
        Firewall policies (firewall policy)
        SNAT/DNAT (firewall ippool, firewall vip)
        Traffic shapers
```

VDOMs (Virtual Domains) are FortiOS's multi-tenancy primitive — each VDOM is effectively a separate firewall. If the user has VDOMs enabled, every config block is scoped under a VDOM (`config vdom / edit <vdom> / config firewall ... / end`).

## Common config patterns

### Address object
```
config firewall address
    edit "obj-web-server"
        set type ipmask
        set subnet 10.1.1.10 255.255.255.255
        set comment "Production web server"
    next
end
```

Note: `subnet` uses `IP MASK` form (space-separated) on FortiOS, not `IP/PREFIX`.

### Address group
```
config firewall addrgrp
    edit "grp-internal-servers"
        set member "obj-web-server" "obj-db-server" "obj-app-server"
    next
end
```

### Custom service
```
config firewall service custom
    edit "svc-tcp-8443"
        set tcp-portrange 8443
    next
end
```

### Firewall policy (the main one)
```
config firewall policy
    edit 10
        set name "ALLOW-WEB-INBOUND"
        set srcintf "wan1"
        set dstintf "internal"
        set srcaddr "all"
        set dstaddr "obj-web-server"
        set service "HTTPS"
        set action accept
        set schedule "always"
        set logtraffic all
        set utm-status enable
        set ssl-ssh-profile "deep-inspection"
        set av-profile "default"
    next
end
```

Policy `id` matters — it's how you reference the rule for edits later. Plan your numbering scheme. Some shops use ranges (1000s for inbound, 2000s for outbound, etc.).

### VIP for destination NAT
```
config firewall vip
    edit "vip-web"
        set extip 203.0.113.10
        set mappedip "10.1.1.10"
        set extintf "wan1"
        set portforward enable
        set protocol tcp
        set extport 443
        set mappedport 8443
    next
end
```

Then reference the VIP as `dstaddr` in the policy.

### Static route
```
config router static
    edit 1
        set dst 10.99.0.0 255.255.0.0
        set gateway 10.1.0.1
        set device "internal"
    next
end
```

### BGP (FortiOS supports BGP, but watch the syntax)
```
config router bgp
    set as 65001
    set router-id 10.0.0.1
    config neighbor
        edit "10.0.0.2"
            set remote-as 65002
            set description "Peer to R2"
        next
    end
end
```

## Common troubleshooting

| Symptom | First-line commands |
|---|---|
| Traffic blocked | `diagnose debug flow filter saddr <src>`, `diag debug flow filter daddr <dst>`, `diag debug flow show console enable`, `diag debug enable` |
| Policy not matching | `diagnose firewall iprope lookup <src>:<port> <dst>:<port> <protocol>` |
| Routing issues | `get router info routing-table all`, `get router info bgp summary` |
| HA not syncing | `diagnose sys ha checksum cluster`, `get system ha status` |
| Performance | `diagnose sys top 1 30` (running processes), `diagnose hardware sysinfo memory` |

`diagnose debug flow` is the equivalent of "explain why this packet did/didn't pass" — invaluable for policy troubleshooting. Always disable debug after with `diag debug disable`.

## Automation tooling

- **Ansible**: `fortinet.fortios` collection — REST API based, broad coverage. `fortinet.fortimanager` for FortiManager-driven deployments.
- **REST API directly**: well-documented at `<fortigate-ip>/api/v2/`. JSON-based. Simpler to debug than CLI scraping.
- **Terraform**: `fortinetdev/fortios` provider for FortiGates, `fortinetdev/fortimanager` for FortiManager. Both reasonably mature.
- **FortiManager**: scriptable via JSON-RPC API. Mention when the user is at scale.

## Gotchas

- **VDOM context**: when VDOMs are enabled, you must `config vdom / edit <vdom>` before any policy work. Forgetting this lands changes in the wrong VDOM (or the global one).
- **`config` blocks must be closed** with `end`. Missing `end` = nothing applied. Missing `next` = entries collide.
- **HA pairs**: changes propagate from the primary to the secondary, but during HA sync issues you may see mismatch. After a config push, verify `get system ha status` shows in-sync.
- **Implicit deny** is the last rule — but you can add an explicit deny-all rule with logging for visibility, which is a common best practice.
- **`set utm-status enable`** is required to engage security profiles (AV, IPS, etc.). Forgetting it means UTM profiles are configured but not applied.
- **Subnet notation**: FortiOS uses `IP MASK` (space-separated, full mask), not CIDR. `10.1.1.10/32` is `10.1.1.10 255.255.255.255`. Be careful when porting from other vendors.
