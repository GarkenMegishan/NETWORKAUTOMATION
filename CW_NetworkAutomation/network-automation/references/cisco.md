# Cisco IOS / IOS-XE / NX-OS

Three OS families ride under the "Cisco" umbrella and they have different syntax, different config models, and different automation tooling. Identify which one before generating output.

| OS | Typical platforms | Notes |
|---|---|---|
| IOS | Older Catalyst (2960, 3560, 3750) | Legacy. Flat config, no commit/rollback by default. |
| IOS-XE | Catalyst 9000, ISR 4000, ASR 1000 | Modern. Supports `configure replace`, archive, NETCONF/YANG, gNMI. |
| NX-OS | Nexus 5000/7000/9000 | Datacenter. VPC, VRF-lite, MP-BGP EVPN, feature-based config. |

Quick discriminators when the user hasn't said:
- `vpc domain`, `feature ospf`, `vrf context` → NX-OS
- `archive`, `configure replace` available → IOS-XE
- Otherwise IOS

## Idempotency

Cisco CLI is mostly idempotent — `vlan 100 / name foo` re-applied is a no-op. Exceptions:

- `interface description` overwrites; safe to re-apply.
- `ip address` on an interface — adding a second address requires `secondary`. Re-applying the same line is a no-op.
- `no` commands are not idempotent in the sense that they produce errors if the line isn't there. In Ansible, prefer `state: absent` over a literal `no` push.

For reliable idempotence at scale, use the Ansible `cisco.ios` / `cisco.nxos` resource modules (`ios_l2_interfaces`, `ios_bgp_global`, etc.) — they reconcile state declaratively.

## Rollback / safe change

**IOS-XE — config archive + replace** (preferred for risky changes):

```
! Pre-change: snapshot
archive
 path flash:archive/
 maximum 5
end
copy running-config flash:pre-change-2026-05-05.cfg

! Make changes...

! If something breaks:
configure replace flash:pre-change-2026-05-05.cfg force
```

**IOS / IOS-XE — reload-in dead-man switch** (for changes to ACLs, routing, management-path interfaces):

```
reload in 5
! make changes
! verify connectivity
reload cancel
```

If the change disconnects you, the box reloads and reverts to the saved config.

**NX-OS — checkpoint / rollback**:

```
checkpoint pre-change
! make changes
rollback running-config checkpoint pre-change
```

Always reference the snapshot/checkpoint name in the runbook.

## Common config patterns

### VLANs (IOS / IOS-XE)
```
vlan 50
 name Guest_WiFi
!
interface range Gi1/0/1 - 24
 switchport mode access
 switchport access vlan 50
 spanning-tree portfast
 spanning-tree bpduguard enable
```

### Trunk port
```
interface Gi1/0/48
 switchport mode trunk
 switchport trunk encapsulation dot1q   ! IOS only; IOS-XE/NX-OS implicit
 switchport trunk allowed vlan 10,20,30,50
 switchport trunk native vlan 999
```

### OSPF (IOS-XE)
```
router ospf 1
 router-id 10.0.0.1
 passive-interface default
 no passive-interface Gi0/0/1
!
interface Gi0/0/1
 ip ospf 1 area 0
 ip ospf network point-to-point
```

### BGP (IOS-XE)
```
router bgp 65001
 bgp log-neighbor-changes
 neighbor 10.0.0.2 remote-as 65002
 neighbor 10.0.0.2 description PEER-TO-R2
 neighbor 10.0.0.2 password <BGP_PASSWORD>
 !
 address-family ipv4
  neighbor 10.0.0.2 activate
  neighbor 10.0.0.2 prefix-list IN-FROM-R2 in
  neighbor 10.0.0.2 prefix-list OUT-TO-R2 out
 exit-address-family
```

### NX-OS feature pattern
NX-OS requires explicit `feature` enables before configuring most protocols:

```
feature ospf
feature bgp
feature vpc
feature interface-vlan
```

### NX-OS vPC essentials
```
vpc domain 10
 peer-keepalive destination 10.99.99.2 source 10.99.99.1
 peer-gateway
 ip arp synchronize
!
interface port-channel10
 vpc peer-link
```

## Common troubleshooting

| Symptom | First-line commands |
|---|---|
| Interface down | `show interfaces Gi1/0/1`, `show interfaces status err-disabled` |
| OSPF adjacency stuck | `show ip ospf neighbor`, `show ip ospf interface Gi0/0/1` (check network type, MTU, area) |
| BGP not establishing | `show ip bgp summary`, `show ip bgp neighbors x.x.x.x` (check TCP 179, AS numbers, source-interface) |
| MAC flapping | `show mac address-table`, `show spanning-tree vlan 50`, `show interfaces trunk` |
| ACL dropping traffic | `show access-lists IN-ACL`, `show ip access-list IN-ACL` (counters reveal hits) |
| QoS not classifying | `show policy-map interface Gi0/0/1` (drops/marks per class) |

## Automation tooling

- **Ansible collections**: `cisco.ios`, `cisco.iosxr`, `cisco.nxos` — use resource modules over raw `ios_command` whenever possible.
- **NAPALM**: `napalm-ios`, `napalm-nxos` — good for getters (`get_facts`, `get_bgp_neighbors`) and atomic config replace.
- **Netmiko**: connection layer; reach for it when collections don't expose what you need.
- **pyATS / Genie**: Cisco's own parser library. Excellent for parsing `show` output into structured data without regex pain.

## Gotchas

- **`copy running-config startup-config`** is not automatic. Always include `wr mem` (or `write memory` / `copy run start`) at the end of any procedure that should persist.
- **IOS interface naming** varies wildly: `GigabitEthernet0/1`, `Gi0/0/1`, `Te1/1/1`, `TwoGigE1/0/1`. Don't guess — use the exact names from the user's `show interfaces`.
- **NX-OS `port-channel`** members must match config (speed, MTU, mode). NX-OS will refuse to bundle mismatched members; IOS will, and bad things follow.
- **Catalyst 9000 IBNS 2.0** vs legacy `dot1x` config — these are not interchangeable; check `show authentication sessions` style before generating.
