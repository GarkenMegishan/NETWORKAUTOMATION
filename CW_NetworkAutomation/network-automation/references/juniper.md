# Juniper Junos

Junos has a fundamentally different config model than IOS — hierarchical, candidate/commit, with built-in rollback. Lean into it. The biggest mistake with Junos automation is treating it like IOS and pushing line-by-line; you'll fight the config engine the whole way.

## The candidate/commit model

Every change is staged into a candidate config first, then committed atomically. This is your safety net.

```
[edit]
user@router# set vlans guest vlan-id 50
user@router# show | compare       # see the diff
user@router# commit confirmed 5   # apply, auto-rollback in 5 min if not confirmed
user@router# commit               # confirm (cancels the timer)
```

If the change disconnects you, do nothing — `commit confirmed` rolls back automatically. This is the gold-standard safety mechanism on Junos and you should default to it for any non-trivial change.

Other rollback affordances:

```
rollback ?            # show available rollback points (0–49)
rollback 1            # revert to the previous commit
load merge terminal   # paste a config block
load override <file>  # full config replace from file
```

## Set vs. configure-mode hierarchy

Junos configs are usually shown two ways. Both are valid; choose based on what's clearer:

**Hierarchical (curly-brace) form:**
```
interfaces {
    ge-0/0/1 {
        unit 0 {
            family ethernet-switching {
                interface-mode access;
                vlan {
                    members guest;
                }
            }
        }
    }
}
```

**Set form (better for automation, paste-ready):**
```
set interfaces ge-0/0/1 unit 0 family ethernet-switching interface-mode access
set interfaces ge-0/0/1 unit 0 family ethernet-switching vlan members guest
```

Always provide set form when generating Junos config for an engineer to apply — it's paste-ready into config mode. Use `show | display set` to convert hierarchical to set form when reading existing configs.

## Idempotency

`set` is idempotent — re-applying the same line is a no-op. `delete` is not (errors if the path doesn't exist; in Ansible, use `state: absent` semantics).

The Ansible `junipernetworks.junos` collection wraps this nicely — `junos_config` with `update: merge` is the right default; `update: replace` is the equivalent of `load override`.

## Common config patterns

### VLAN + access port (EX series)
```
set vlans guest vlan-id 50 description "Guest WiFi"
set interfaces ge-0/0/1 unit 0 family ethernet-switching interface-mode access
set interfaces ge-0/0/1 unit 0 family ethernet-switching vlan members guest
```

### Trunk port (EX series)
```
set interfaces ge-0/0/48 unit 0 family ethernet-switching interface-mode trunk
set interfaces ge-0/0/48 unit 0 family ethernet-switching vlan members [ data voice guest ]
set interfaces ge-0/0/48 native-vlan-id 999
```

### OSPF
```
set protocols ospf area 0.0.0.0 interface ge-0/0/1.0 interface-type p2p
set protocols ospf area 0.0.0.0 interface lo0.0 passive
set routing-options router-id 10.0.0.1
```

### BGP (MX/SRX)
```
set routing-options autonomous-system 65001
set protocols bgp group EXTERNAL type external
set protocols bgp group EXTERNAL peer-as 65002
set protocols bgp group EXTERNAL neighbor 10.0.0.2 description PEER-TO-R2
set protocols bgp group EXTERNAL neighbor 10.0.0.2 import IN-FROM-R2
set protocols bgp group EXTERNAL neighbor 10.0.0.2 export OUT-TO-R2
```

Note: Junos uses *peer groups* and applies policy at the group level by default, with neighbor-level overrides. Plan your group structure before generating config.

### Firewall filter (Junos's name for an ACL)
```
set firewall family inet filter BLOCK-RFC1918 term 1 from source-address 10.0.0.0/8
set firewall family inet filter BLOCK-RFC1918 term 1 then discard
set firewall family inet filter BLOCK-RFC1918 term default then accept
```

Apply with `set interfaces ge-0/0/0.0 family inet filter input BLOCK-RFC1918`. Filters are evaluated top-to-bottom; **always include a final `then accept` term** — Junos's implicit default is *discard*, which will lock you out otherwise.

### SRX zones and security policies
SRX uses zones (not interfaces) as policy endpoints:

```
set security zones security-zone trust interfaces ge-0/0/1.0
set security zones security-zone untrust interfaces ge-0/0/0.0
set security policies from-zone trust to-zone untrust policy ALLOW-OUT match source-address any destination-address any application any
set security policies from-zone trust to-zone untrust policy ALLOW-OUT then permit
```

## Common troubleshooting

| Symptom | First-line commands |
|---|---|
| Interface down | `show interfaces ge-0/0/1 extensive` |
| OSPF adjacency stuck | `show ospf neighbor`, `show ospf interface ge-0/0/1.0 detail` |
| BGP not establishing | `show bgp summary`, `show bgp neighbor 10.0.0.2` |
| Route not in RIB | `show route 10.1.1.0/24 exact`, `show route hidden` (hidden = next-hop unreachable, etc.) |
| Filter dropping traffic | `show firewall filter BLOCK-RFC1918` (counters per term) |

## Automation tooling

- **Ansible**: `junipernetworks.junos` — `junos_config`, resource modules, NETCONF-based. Solid.
- **PyEZ** (`junos-eznc`): Python library, RPC-based. Good for `get_facts`, `get_route_table`, programmatic config push.
- **NAPALM**: `napalm-junos` — getters and `load_replace_candidate` / `commit_config`.

## Gotchas

- **No autosave.** `commit` doesn't write to disk on EX/QFX — it does on MX/SRX. To be safe, after final commit run `request system snapshot` for full system backup or rely on the rollback history (which persists, up to 49 entries).
- **`commit confirmed` requires a follow-up `commit`** to cancel the rollback timer. If you forget, the box reverts on you. Set yourself a reminder, or shorten the timer.
- **Apply-groups** are powerful but make config hard to read. When generating new config, prefer explicit settings over apply-groups unless you know the existing structure uses them.
- **`replace:` keyword** in load merge — `replace: pattern` substitutes a stanza; useful for surgical changes to deeply nested config.
- **EX vs MX vs SRX** have meaningfully different feature sets. `ethernet-switching` family is EX/QFX; MX uses `bridge` and EVPN; SRX uses `inet` with zone-based security. Don't paraphrase across.
