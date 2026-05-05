# Dual-Hub SD-WAN Lab — HK5 / TY9 / LON (Fortinet)

**Lab platform:** PNETLab on VMware Workstation 17
**SD-WAN stack:** Fortinet FortiGate-VM (FortiOS 7.4.x)
**ISP simulator:** MikroTik CHR (single VM, multi-port)
**Underlays:** 2 × Internet (ISP-A primary, ISP-B backup) per site, plus a separate MPLS path via per-site MPLS routers
**Author:** Garry Gautane
**Last updated:** 2026-05-04
**Status:** Working lab build — best-practice review notes in §17 and §21

---

## 1. Purpose

A reproducible PNETLab build that models a **dual-hub Fortinet SD-WAN** deployment across three sites (HK5 = Hong Kong DC primary hub, TY9 = Tokyo DC secondary hub, LON = London branch spoke). The lab is used to:

- Validate hub-and-spoke ADVPN designs and SD-WAN rule behaviour before pushing to a green-field or brown-field environment.
- Test failover between two internet underlays plus an MPLS path.
- Sandbox SLA threshold tuning, BGP route-reflector behaviour, and SD-WAN policy changes.

---

## 2. Scope and Out-of-Scope

**In scope**
- 2 internet underlays per site (ISP-A primary, ISP-B backup) terminated on a shared MikroTik ISP simulator.
- 1 MPLS path per site between the per-site MPLS router and the site core switch, with OSPF↔BGP redistribution into the FortiGate.
- FortiGate-as-hub on HK5 and TY9; LON as spoke; ADVPN-capable IPsec overlays.
- iBGP on SD-WAN loopbacks for overlay route exchange; BGP for MPLS path between FortiGate and the MPLS router.
- SD-WAN zones (`underlay`, `HK5DC`, `TY9DC`), Performance SLAs against simulated `8.8.8.8` / `1.1.1.1` on the MikroTik, and SD-WAN service rules.

**Out of scope**
- FortiManager / FortiAnalyzer (managed CLI-direct in this lab; templates can be promoted later).
- Real ISP SLAs (latency / jitter / loss are emulated).
- Production identity, DDoS, throughput / scale testing.
- Firewall UTM profiles beyond the bare minimum.

---

## 3. Lab Host Environment

| Component | Value |
|---|---|
| Hypervisor | VMware Workstation 17 Pro |
| Lab orchestrator | PNETLab `<version>` |
| Host CPU / RAM / disk | `<TBD — fill in your build>` |
| Nested virt | Intel VT-x / EPT enabled |
| Mgmt network | `192.168.100.0/24` (Docker eth1 on PNETLab host) |

**Resource budget (per device, recommended floor):**

| Role | vCPU | RAM | Disk |
|---|---|---|---|
| FortiGate-VM (HK5/TY9/LON) | 2 | 4 GB | 30 GB |
| MikroTik CHR (ISP simulator) | 1 | 1 GB | 4 GB |
| Cisco IOL / QFP (CORE / ACCESS / MPLS-RTR) | 1 | 1 GB | 4 GB |
| Windows Tiny 10 (mgmt PC) | 2 | 2 GB | 20 GB |
| VPC test endpoints | n/a (PNETLab native) | 64 MB | n/a |

---

## 4. Image Inventory

| Function | Image | Version | Notes |
|---|---|---|---|
| SD-WAN edge / hub | FortiGate-VM64-KVM | FortiOS `<7.4.x>` | Same build on all three FGTs |
| ISP simulator | MikroTik CHR | RouterOS `<7.x>` | Single VM, multiple ports |
| Core / access switching | Cisco QFP / IOL-L2 | `<image build>` | Layer-2 + SVI for inter-VLAN |
| MPLS router | Cisco IOL-L3 | `<image build>` | Per-site PE/CE emulating MPLS PE behaviour |
| Mgmt PC | Windows Tiny 10 | n/a | Browser-based admin to FGT GUI / FortiManager |
| Test endpoint | PNETLab VPC | n/a | iperf, ping, traceroute |

**Licensing note:** FortiGate-VM eval runs unlicensed for ~15 days, then drops to 1 Mbps with persistent license warnings. Raise an eval license in FortiCare if you need to keep the lab live longer.

---

## 5. Topology

### 5.1 Physical / logical diagram

The lab is laid out (see attached PNETLab screenshot) as three site stacks plus a shared MPLS cloud and a shared MikroTik ISP simulator:

```
   TY9 site                    HK5 site                   LON site
  ┌───────────┐              ┌───────────┐              ┌───────────┐
  │ TY9-ACCESS│              │ HK5-ACCESS│              │ LON-ACCESS│
  │ 192.168.40│              │ 192.168.210              │ 192.168.190
  └─────┬─────┘              └─────┬─────┘              └─────┬─────┘
        │                          │                          │
  ┌─────┴─────┐              ┌─────┴─────┐              ┌─────┴─────┐
  │ TY9-CORE  │──TY9-MPLS-RTR│ HK5-CORE  │──HK5-MPLS-RTR│ LON-CORE  │──LON-MPLS-RTR
  └─────┬─────┘     │        └─────┬─────┘     │        └─────┬─────┘     │
        │           ▼              │           ▼              │           ▼
  ┌─────┴─────┐  ┌────────┐  ┌─────┴─────┐  ┌────────┐  ┌─────┴─────┐  ┌────────┐
  │  TY9-FGT  │  │ MPLS   │  │  HK5-FGT  │  │ MPLS   │  │  LON-FGT  │  │ MPLS   │
  │ (hub-2)   │  │ CLOUD  │  │ (hub-1)   │  │ CLOUD  │  │  (spoke)  │  │ CLOUD  │
  └─────┬─────┘  └───▲────┘  └─────┬─────┘  └───▲────┘  └─────┬─────┘  └───▲────┘
        │            │             │            │             │            │
        └────────────┴─────────────┴────────────┴─────────────┴────────────┘
                              MPLS CLOUD (OSPF ↔ BGP)
        │                                        │                          │
        └──────── 2 × WAN to MikroTik ───────────┴── 2 × WAN to MikroTik ──┘
                                ┌──────────────┐
                                │  MikroTik    │
                                │ (shared ISP) │
                                │ ISP-A + ISP-B│
                                └──────────────┘
```

**Key points:**
- Each FortiGate has **two WAN-side ports** to MikroTik: ISP-A (primary) and ISP-B (backup).
- Each FortiGate has a **LAN-side trunk** to its CORE switch; the ACCESS switch hangs off the CORE.
- Each site has an **MPLS-RTR** that connects to the CORE switch on one side and to the shared `MPLS-CLOUD` on the other. Redistribution between OSPF (MPLS side) and BGP (LAN / FGT side) happens on the MPLS-RTR or on the CORE.
- A single **MikroTik CHR** simulates both ISPs by terminating each FGT WAN link on a dedicated `/30`.
- **Mgmt network** (`192.168.100.0/24`) is a separate flat LAN reachable from the Docker `eth1` host bridge.

### 5.2 Site roles

| Site code | Location | Role | FortiGate | Site ID |
|---|---|---|---|---|
| HK5 | Hong Kong DC | Primary hub | HK5DCFW | 100 |
| TY9 | Tokyo DC | Secondary hub | TY9DCFW | 200 |
| LON | London branch | Spoke | LONFW | 300 |

### 5.3 Transport matrix per FortiGate

| FortiGate | port1 (MGMT) | port2 (WAN1 / ISP-A) | port3 (WAN2 / ISP-B) | LAN-side ports (to CORE) | MPLS path |
|---|---|---|---|---|---|
| HK5DCFW | 192.168.100.1 | 198.51.100.2/30 | 203.0.113.2/30 | port4, port5 | via HK5-CORE → HK5-MPLS-RTR |
| TY9DCFW | 192.168.100.3 | 198.51.100.6/30 | 203.0.113.6/30 | port4, port5 | via TY9-CORE → TY9-MPLS-RTR |
| LONFW | 192.168.100.5 | 198.51.100.10/30 | 203.0.113.10/30 | port4, port5 | via LON-CORE → LON-MPLS-RTR |

---

## 6. Network Design Overview

### 6.1 Three-transport hybrid model

Each site has three logical paths to peer sites:

1. **ISP-A overlay** (IPsec over `198.51.100.x/30`, MikroTik gw odd-numbered).
2. **ISP-B overlay** (IPsec over `203.0.113.x/30`, MikroTik gw odd-numbered, used as backup).
3. **MPLS path** (native L3 via `MPLS-RTR` on the LAN side of the FortiGate; carried by BGP).

The two internet paths are **SD-WAN members in `zone underlay`** and used to build the ADVPN overlays in `zone HK5DC` and `zone TY9DC`. The MPLS path is **not a SD-WAN member** in this build — it is reached via normal routing through the CORE switch and BGP from the MPLS-RTR. See §17 for the trade-off and an alternative if you want MPLS under SD-WAN steering.

### 6.2 Overlay model

- LON spoke builds **2 IPsec tunnels per hub** (ISP-A and ISP-B), giving **4 tunnels total** from LONFW.
- Each hub terminates a tunnel per spoke per transport.
- ADVPN signalling on hubs allows on-demand spoke-to-spoke shortcuts (when more spokes are added).
- iBGP runs on `SDWAN-Loopback` interfaces between every spoke and both hubs. Hubs act as **route-reflectors**.

---

## 7. Address Plan

### 7.1 Out-of-band / management

| Device | Mgmt IP | Notes |
|---|---|---|
| MGMT_PC (Tiny 10) | 192.168.100.11 | Windows admin host |
| HK5DCFW (port1) | 192.168.100.1 | FGT mgmt |
| TY9DCFW (port1) | 192.168.100.3 | FGT mgmt (note: was `TY5DCFW` in source — typo) |
| LONFW (port1) | 192.168.100.5 | FGT mgmt |
| MikroTik (ether1) | 192.168.100.14 | ISP simulator mgmt |
| Docker host eth1 | 192.168.100.11/24 | PNETLab bridge |

Allowed mgmt access on FGT port1: `ping ssh http https`.

### 7.2 LAN per site

| Site | LAN subnet | Test endpoint |
|---|---|---|
| HK5 | 192.168.210.0/24 | VPC8 |
| TY9 | 192.168.40.0/24 | VPC |
| LON | 192.168.190.0/24 | VPC11 |

### 7.3 ISP-A underlay (TEST-NET-2 — `198.51.100.0/24`)

MikroTik holds the gateway side (odd `.1/.5/.9`); FortiGate holds even (`.2/.6/.10`).

| Link | Subnet | MikroTik gw | FortiGate IP |
|---|---|---|---|
| HK5 ↔ MikroTik (ISP-A) | 198.51.100.0/30 | 198.51.100.1 | 198.51.100.2 |
| TY9 ↔ MikroTik (ISP-A) | 198.51.100.4/30 | 198.51.100.5 | 198.51.100.6 |
| LON ↔ MikroTik (ISP-A) | 198.51.100.8/30 | 198.51.100.9 | 198.51.100.10 |

### 7.4 ISP-B underlay (TEST-NET-3 — `203.0.113.0/24`)

| Link | Subnet | MikroTik gw | FortiGate IP |
|---|---|---|---|
| HK5 ↔ MikroTik (ISP-B) | 203.0.113.0/30 | 203.0.113.1 | 203.0.113.2 |
| TY9 ↔ MikroTik (ISP-B) | 203.0.113.4/30 | 203.0.113.5 | 203.0.113.6 |
| LON ↔ MikroTik (ISP-B) | 203.0.113.8/30 | 203.0.113.9 | 203.0.113.10 |

### 7.5 SD-WAN loopbacks (overlay BGP source / IKE source)

| Device | SDWAN-Loopback | BGP AS |
|---|---|---|
| HK5DCFW | 172.20.196.1/32 | 65000 |
| TY9DCFW | 172.20.196.2/32 | 65000 |
| LONFW | 172.20.196.3/32 | 65000 |

### 7.6 MPLS path (LAN-side, OSPF ↔ BGP redistribution)

| Link | Subnet | FortiGate | CORE / MPLS-RTR |
|---|---|---|---|
| HK5-FGT ↔ HK5-CORE (MPLS VRF SVI) | `<TBD — e.g., 10.10.0.0/30>` | `<.2>` | `<.1>` |
| TY9-FGT ↔ TY9-CORE | `<TBD>` | `<.2>` | `<.1>` |
| LON-FGT ↔ LON-CORE | `<TBD>` | `<.2>` | `<.1>` |
| MPLS core (OSPF area 0) | `<TBD>` | n/a | per MPLS-RTR |

---

## 8. MikroTik ISP Simulator

### 8.1 Initial mgmt and interface naming

```
# Mgmt
/ip address add address=192.168.100.14/24 interface=ether1 comment="LAN Management IP"

# Rename interfaces (adjust to your PNETLab cabling)
/interface ethernet
set [find default-name=ether2] name=to-HK5-wan1-ISP-A
set [find default-name=ether3] name=to-HK5-wan2-ISP-B
set [find default-name=ether4] name=to-TY9-wan1-ISP-A
set [find default-name=ether5] name=to-TY9-wan2-ISP-B
set [find default-name=ether6] name=to-LON-wan1-ISP-A
set [find default-name=ether7] name=to-LON-wan2-ISP-B
```

### 8.2 Underlay /30 addressing

```
/ip address
add address=198.51.100.1/30  interface=to-HK5-wan1-ISP-A  comment="HK5 wan1 gateway"
add address=198.51.100.5/30  interface=to-TY9-wan1-ISP-A  comment="TY9 wan1 gateway"
add address=198.51.100.9/30  interface=to-LON-wan1-ISP-A  comment="London wan1 gateway"
add address=203.0.113.1/30   interface=to-HK5-wan2-ISP-B  comment="HK5 wan2 gateway"
add address=203.0.113.5/30   interface=to-TY9-wan2-ISP-B  comment="TY9 wan2 gateway"
add address=203.0.113.9/30   interface=to-LON-wan2-ISP-B  comment="London wan2 gateway"

/ip route add dst-address=0.0.0.0/0 blackhole comment="Lab ISP simulator - no real upstream"

/ip firewall filter
add chain=input action=accept protocol=icmp comment="Allow ping from lab FortiGates"
add chain=input action=drop                 comment="Drop everything else (optional hardening)"
```

### 8.3 Simulated public DNS targets for SD-WAN health check

Use bridge-as-loopback to host `8.8.8.8` and `1.1.1.1` for stable Performance SLA targets:

```
/interface bridge
add name=loopback-Google-DNS    comment="Simulated 8.8.8.8 for SD-WAN health-check"
add name=loopback-Cloudflare-DNS comment="Simulated 1.1.1.1 for SD-WAN health-check"

/ip address
add address=8.8.8.8/32 interface=loopback-Google-DNS    comment="Simulated Google DNS"
add address=1.1.1.1/32 interface=loopback-Cloudflare-DNS comment="Simulated Cloudflare DNS"
```

> **Review item (see §21):** the source notes also add `/ip route add dst-address=8.8.8.8/32 blackhole` and `1.1.1.1/32 blackhole`. The bridge-with-IP already creates a connected route — the blackhole route is redundant and can confuse troubleshooting. Remove it unless you specifically want to discard probes that miss the connected route.

---

## 9. FortiGate Initial Management

```
# Default credentials (change immediately)
Username: admin
Password: 123

config system interface
    edit "port1"
        set mode static
        set ip 192.168.100.1 255.255.255.0      # change per device
        set allowaccess ping ssh http https
        set type physical
    next
end
```

| Device | port1 mgmt IP |
|---|---|
| HK5DCFW | 192.168.100.1 |
| TY9DCFW | 192.168.100.3 |
| LONFW | 192.168.100.5 |

---

## 10. FortiGate WAN Interface Config

### 10.1 LON spoke (template — repeat with per-site IPs)

```
config system interface
    edit "port2"                                 # wan1 - ISP-A Primary
        set vdom "root"
        set ip 198.51.100.10 255.255.255.252
        set allowaccess ping https ssh
        set type physical
        set alias "ISP-A-Primary"
        set role wan
        set mode static
        set description "wan1 - ISP-A Primary"
    next
    edit "port3"                                 # wan2 - ISP-B Backup
        set vdom "root"
        set ip 203.0.113.10 255.255.255.252
        set allowaccess ping https ssh
        set type physical
        set alias "ISP-B-Backup"
        set role wan
        set mode static
        set description "wan2 - ISP-B Backup"
    next
end
```

### 10.2 HK5 hub

```
config system interface
    edit "port2"
        set ip 198.51.100.2 255.255.255.252
        set alias "ISP-A-Primary"
        set role wan
        set allowaccess ping http ssh
        set type physical
        set mode static
        set description "wan1 - ISP-A Primary"
    next
    edit "port3"
        set ip 203.0.113.2 255.255.255.252
        set alias "ISP-B-Backup"
        set role wan
        set allowaccess ping http ssh
        set type physical
        set mode static
        set description "wan2 - ISP-B Backup"
    next
end
```

### 10.3 TY9 hub

Same pattern as HK5 but with `198.51.100.6/30` and `203.0.113.6/30`.

### 10.4 SD-WAN loopback (all FortiGates)

```
config system interface
    edit "SDWAN-Loopback"
        set vdom "root"
        set ip <site-loopback>/32              # 172.20.196.1 / .2 / .3
        set allowaccess ping
        set type loopback
        set description "SD-WAN BGP source / IKE source"
    next
end
```

### 10.5 Default routes for each WAN

```
config router static
    edit 1
        set dst 0.0.0.0 0.0.0.0
        set gateway 198.51.100.9                # MikroTik gw on ISP-A (LON example)
        set device "port2"
        set distance 10                          # primary
    next
    edit 2
        set dst 0.0.0.0 0.0.0.0
        set gateway 203.0.113.9                  # MikroTik gw on ISP-B
        set device "port3"
        set distance 20                          # backup
    next
end
```

---

## 11. SD-WAN Zones and Members

### 11.1 Zone model

| Zone | Purpose | Members |
|---|---|---|
| `underlay` | Internet underlays (used for IPsec build and direct internet) | `port2` (ISP-A), `port3` (ISP-B) on every FGT |
| `HK5DC` | Overlay tunnels terminating at HK5 hub | hub-side: per-spoke tunnels; spoke-side: 2 tunnels to HK5 |
| `TY9DC` | Overlay tunnels terminating at TY9 hub | hub-side: per-spoke tunnels; spoke-side: 2 tunnels to TY9 |

### 11.2 LON spoke — SD-WAN members

```
config system sdwan
    set status enable
    config zone
        edit "underlay"
        next
        edit "HK5DC"
        next
        edit "TY9DC"
        next
    end
    config members
        edit 1
            set interface "port2"                # wan1 - ISP-A Primary
            set gateway 198.51.100.9
            set source 198.51.100.10
            set cost 10
            set priority 10
            set zone "underlay"
        next
        edit 2
            set interface "port3"                # wan2 - ISP-B Backup
            set gateway 203.0.113.9
            set source 203.0.113.10
            set cost 20
            set priority 5
            set zone "underlay"
        next
        edit 3
            set interface "HK-Overlay-LON"       # IPsec to HK5 (built in §12)
            set zone "HK5DC"
            set source 172.20.196.3
        next
        edit 4
            set interface "TY-Overlay-LON"       # IPsec to TY9
            set zone "TY9DC"
            set source 172.20.196.3
        next
    end
end
```

### 11.3 Hubs — SD-WAN members (overlays only, no internet underlay member needed for steering)

```
# HK5 hub
config system sdwan
    config zone
        edit "HK5DC"
        next
    end
    config members
        edit 1
            set interface "HK-Overlay-LON"
            set zone "HK5DC"
            set source 172.20.196.1
        next
        # add per-spoke tunnels as the lab grows
    end
end

# TY9 hub
config system sdwan
    config zone
        edit "TY9DC"
        next
    end
    config members
        edit 1
            set interface "TY-Overlay-LON"
            set zone "TY9DC"
            set source 172.20.196.2
        next
    end
end
```

---

## 12. ADVPN Overlay (IPsec) — Best-Practice Template

### 12.1 Phase1 / Phase2 (HK5 hub side, ISP-A example)

```
config vpn ipsec phase1-interface
    edit "HK-Overlay-LON-A"
        set type dynamic                         # hub side accepts spokes
        set interface "port2"                    # ISP-A
        set ike-version 2
        set peertype any
        set net-device disable
        set proposal aes256gcm-prfsha384
        set dhgrp 19
        set add-route disable
        set auto-discovery-sender enable         # ADVPN: hub announces shortcut info
        set network-overlay enable
        set network-id 1                         # unique per overlay
        set psksecret <vault ref>
    next
end
config vpn ipsec phase2-interface
    edit "HK-Overlay-LON-A"
        set phase1name "HK-Overlay-LON-A"
        set proposal aes256gcm
        set pfs enable
        set dhgrp 19
    next
end
```

### 12.2 Phase1 / Phase2 (LON spoke side, ISP-A example)

```
config vpn ipsec phase1-interface
    edit "HK-Overlay-LON"                        # spoke-side tunnel name
        set interface "port2"
        set ike-version 2
        set peertype any
        set net-device disable
        set proposal aes256gcm-prfsha384
        set dhgrp 19
        set remote-gw 198.51.100.2               # HK5 ISP-A WAN IP
        set auto-discovery-receiver enable       # ADVPN: spoke can build shortcuts
        set network-overlay enable
        set network-id 1
        set psksecret <vault ref>
    next
end
```

Repeat the four-tunnel pattern for `LON ↔ HK5 over ISP-B`, `LON ↔ TY9 over ISP-A`, `LON ↔ TY9 over ISP-B`.

### 12.3 Tunnel matrix on LONFW

| Tunnel name | Underlay | Remote hub IP | SD-WAN zone |
|---|---|---|---|
| `HK-Overlay-LON-A` | port2 (ISP-A) | 198.51.100.2 (HK5) | HK5DC |
| `HK-Overlay-LON-B` | port3 (ISP-B) | 203.0.113.2 (HK5) | HK5DC |
| `TY-Overlay-LON-A` | port2 (ISP-A) | 198.51.100.6 (TY9) | TY9DC |
| `TY-Overlay-LON-B` | port3 (ISP-B) | 203.0.113.6 (TY9) | TY9DC |

> **Best practice:** keep tunnel names predictable (`<hub>-Overlay-<spoke>-<transport>`). It pays off in `diagnose` output, FortiManager templates, and SD-WAN member ordering.

### 12.4 Overlay tunnel `/30` IPs

Assign tunnel IPs on the IPsec interfaces so iBGP has reachable neighbours:

| Tunnel | HK5 side | LON side |
|---|---|---|
| HK-Overlay-LON-A | 10.200.1.1/30 | 10.200.1.2/30 |
| HK-Overlay-LON-B | 10.200.2.1/30 | 10.200.2.2/30 |
| TY-Overlay-LON-A | 10.200.3.1/30 | 10.200.3.2/30 |
| TY-Overlay-LON-B | 10.200.4.1/30 | 10.200.4.2/30 |

---

## 13. Routing Design

### 13.1 BGP overlay (iBGP on loopbacks)

Hubs act as **route-reflectors**; spokes peer with both hubs over **both transports** for resilience (so 4 BGP sessions per spoke), or simplify to 2 sessions on the SDWAN-Loopback if the underlay tunnels have static routes guaranteeing loopback reachability.

```
# LON spoke
config router bgp
    set as 65000
    set router-id 172.20.196.3
    config neighbor
        edit "172.20.196.1"                      # HK5 hub
            set remote-as 65000
            set update-source "SDWAN-Loopback"
            set ebgp-enforce-multihop enable     # required when peering on loopbacks
            set advertisement-interval 1
            set additional-path receive
        next
        edit "172.20.196.2"                      # TY9 hub
            set remote-as 65000
            set update-source "SDWAN-Loopback"
            set ebgp-enforce-multihop enable
        next
    end
    config network
        edit 1
            set prefix 192.168.190.0 255.255.255.0   # LON LAN
        next
    end
end

# HK5 hub - route-reflector
config router bgp
    set as 65000
    set router-id 172.20.196.1
    config neighbor-group
        edit "spokes"
            set remote-as 65000
            set update-source "SDWAN-Loopback"
            set route-reflector-client enable
            set additional-path send
            set adv-additional-path 4
        next
    end
    config neighbor-range
        edit 1
            set prefix 172.20.196.0/24
            set neighbor-group "spokes"
        next
    end
    config network
        edit 1
            set prefix 192.168.210.0 255.255.255.0   # HK5 LAN
        next
    end
end
```

### 13.2 MPLS path (OSPF ↔ BGP redistribution)

The MPLS-RTR runs OSPF area 0 toward the MPLS cloud and BGP toward the CORE/FGT. Redistribution lives on the MPLS-RTR:

```
! HK5-MPLS-RTR (Cisco IOS-style example)
router ospf 1
 router-id 10.99.0.1
 redistribute bgp 65000 subnets metric-type 1
 network <MPLS-side subnet> 0.0.0.255 area 0

router bgp 65000
 redistribute ospf 1
 neighbor <HK5-FGT-MPLS-side IP> remote-as 65000
 neighbor <HK5-FGT-MPLS-side IP> update-source <iface>
```

On the FortiGate, the MPLS side is just another iBGP neighbour reached via the LAN port toward the CORE. This gives the FGT three logical paths to peer LANs: ISP-A overlay, ISP-B overlay, and MPLS BGP — each with its own `weight` / `local-preference` knobs.

### 13.3 Path preference knobs

| Preference | How to set | Suggested value |
|---|---|---|
| MPLS preferred for `corp` traffic | local-preference on MPLS BGP neighbour | 200 |
| HK5 hub preferred for HK-bound prefixes | local-preference on HK overlay neighbour | 150 |
| TY9 hub preferred for TY-bound prefixes | local-preference on TY overlay neighbour | 150 |
| ISP-B used as backup only | higher cost on SD-WAN member + lower priority | cost 20 / priority 5 |

---

## 14. Health Checks and SLA

```
config system sdwan
    config health-check
        edit "Internet-SLA"
            set server "8.8.8.8" "1.1.1.1"
            set protocol ping
            set interval 500
            set failtime 5
            set recoverytime 5
            set members 0                        # all members
            config sla
                edit 1
                    set latency-threshold 150
                    set jitter-threshold 30
                    set packetloss-threshold 3
                next
            end
        next
        edit "HK-Reachability"
            set server "172.20.196.1"            # HK5 SDWAN-Loopback
            set protocol ping
            set members 3 4                      # only the overlay members reach the loopback
            config sla
                edit 1
                    set latency-threshold 200
                    set jitter-threshold 50
                    set packetloss-threshold 5
                next
            end
        next
    end
end
```

> **Why `set members 3 4`** for the HK-Reachability check: probing a hub loopback over the ISP underlay won't work (loopback isn't reachable in the underlay). Pin the check to the overlay members.

**SLA threshold rationale:**
- `150 ms / 30 ms / 3 %` is a defensible enterprise default for global internet underlays.
- For VoIP/UCaaS-only rules, tighten to `100 / 20 / 1`.
- For bulk/file-transfer-only rules, relax to `250 / 55 / 5`.

---

## 15. SD-WAN Service Rules

### 15.1 Current rule (all traffic, HK preferred)

```
config system sdwan
    config service
        edit 1
            set name "All-Traffic"
            set mode sla
            set dst "all"
            set src "all"
            set priority-zone "HK5DC" "TY9DC"    # ⚠ source notes say "HongKong" "Tokyo" — must match zone names
            set zone-mode enable
            set minimum-sla-meet-members 2
            set sla "Internet-SLA"
            set sla-stickiness enable
            set hold-down-time 30
        next
    end
end
```

> **Review item:** in the source notes, `priority-zone "HongKong" "Tokyo"` does not match the configured zones `HK5DC` / `TY9DC`. The rule won't bind without matching names. Use `HK5DC` / `TY9DC` as shown above. Logged in §21.

### 15.2 Recommended app-aware rules (best practice)

Add ordered rules above the catch-all so latency-sensitive apps pin to the best path:

```
config system sdwan
    config service
        edit 10
            set name "Voice-VoIP"
            set mode sla
            set dst "all"
            set src "all"
            set internet-service enable
            set internet-service-app-ctrl 33078 33077    # SIP, RTP signatures
            set sla "Internet-SLA"
            set priority-members 3 1                     # HK overlay > ISP-A
            set sla-stickiness enable
        next
        edit 20
            set name "Conferencing"
            set mode sla
            set dst "all"
            set src "all"
            set internet-service-app-ctrl <Zoom/Teams ID>
            set sla "Internet-SLA"
            set priority-members 3 1
        next
        edit 30
            set name "Bulk-Backup"
            set mode manual
            set dst "all"
            set src "all"
            set priority-members 2                       # pin to ISP-B (cheap path)
        next
        edit 99                                          # catch-all
            set name "All-Traffic"
            set mode sla
            ...
        next
    end
end
```

> **Best practice:** keep the catch-all rule last. Use `mode sla` for anything you want to fail over on degradation; use `mode manual` to pin traffic to a specific member; use `mode load-balance` for even distribution when both members are healthy.

---

## 16. Firewall Policies (minimum)

| ID | Name | Src zone / addr | Dst zone / addr | Service | NAT | Notes |
|---|---|---|---|---|---|---|
| 1 | LAN-to-Overlay | LAN / `192.168.190.0/24` | `HK5DC`, `TY9DC` / `corp` group | ALL | disable | Branch users → DC LANs |
| 2 | LAN-to-Internet | LAN / `192.168.190.0/24` | `underlay` / all | ALL | enable | Direct internet breakout via ISP-A |
| 3 | Overlay-to-LAN | `HK5DC`, `TY9DC` / `corp` group | LAN / `192.168.190.0/24` | ALL | disable | DC servers → branch |
| 4 | MPLS-LAN-to-LAN | LAN | MPLS-side / `corp` group | ALL | disable | LAN over MPLS |
| 5 | MGMT-only | `mgmt` / `192.168.100.0/24` | self | HTTPS, SSH, PING | n/a | port1 admin |

Apply UTM profiles (AV / IPS / Web) per organisational baseline.

---

## 17. Best-Practice Design Notes for Fortinet SD-WAN

1. **Always use named zones** (`underlay`, per-hub overlay zones). Don't put overlays in the `underlay` zone — it breaks zone-based SD-WAN rules and policy reuse.
2. **One IPsec phase1 per transport per hub** on the spoke side. Don't multiplex multiple transports onto one tunnel — Performance SLA needs to see each path independently.
3. **Use SDWAN-Loopback as BGP source and IKE source** so the BGP session and route-reflector relationship survives a transport flap.
4. **Hubs as route-reflectors** with `additional-path send` and `adv-additional-path 4` so spokes can install backup paths and ADVPN shortcuts work cleanly.
5. **`auto-discovery-sender enable` on hubs**, **`auto-discovery-receiver enable` on spokes** — required for ADVPN shortcut negotiation.
6. **Performance SLA targets matter.** Probe simulated `8.8.8.8` / `1.1.1.1` on the MikroTik (consistent, no flap from real DNS) and add a dedicated overlay reachability probe pinned to overlay members only.
7. **`minimum-sla-meet-members`** — set to `1` if you want failover on first SLA breach, `2` to require both healthy paths before considering the zone "good".
8. **`sla-stickiness enable`** prevents flapping when a path bounces in and out of SLA. Pair with `hold-down-time` (15–60 s).
9. **MPLS as a first-class SD-WAN member (alternative design):** in this lab MPLS is reached via the LAN-side CORE switch, so it's not under SD-WAN selection. To bring MPLS into SD-WAN steering, terminate the MPLS handoff directly on a FortiGate WAN port (or VLAN sub-interface) and add it as a third member in `zone underlay`. Then SD-WAN rules can prefer MPLS over internet for `corp` traffic with one toggle.
10. **Cost vs priority on SD-WAN members:** `cost` is the preference floor when SLA is met; `priority` is the tiebreaker between members of equal cost. Use `cost 10 / priority 10` for primary, `cost 20 / priority 5` for backup.
11. **Symmetric paths:** if you want return traffic to stick to the same path (especially under NAT), enable **session affinity** with `set tie-break sla-target` and watch BGP `additional-path` behaviour at the hub.
12. **Templating:** even in a CLI-direct lab, structure your configs so they map 1:1 to FortiManager CLI templates (per-platform, per-site meta-fields). It'll save hours when you promote to FMG.
13. **Don't redistribute everything everywhere.** At the MPLS-RTR, use route-maps to control what crosses OSPF↔BGP — otherwise you'll get loops or MPLS prefixes leaking into overlays unexpectedly.
14. **Always set `network-id`** and keep it unique per overlay — this is what ADVPN uses to identify the overlay across hubs. Mismatches break shortcut negotiation silently.

---

## 18. Validation Procedures

| # | Test | CLI |
|---|---|---|
| T01 | Mgmt reachable | `ping 192.168.100.1` from MGMT_PC |
| T02 | WAN up on both ISPs | `get system interface physical | grep -A 3 port2` |
| T03 | IPsec tunnels established | `get vpn ipsec tunnel summary` (expect 4 on LON, 2 per hub per spoke) |
| T04 | BGP neighbours up | `get router info bgp summary` (LON shows HK5 + TY9 hubs `Established`) |
| T05 | SD-WAN members healthy | `diagnose sys sdwan health-check` and `diagnose sys sdwan member` |
| T06 | SD-WAN rule selection | `diagnose sys sdwan service` |
| T07 | LAN reachability HK→LON | `execute ping-options source 192.168.210.10` then `execute ping 192.168.190.10` |
| T08 | ADVPN shortcut formation | second-spoke ping; confirm new dynamic tunnel via `diagnose vpn ike gateway list` |
| T09 | Failover ISP-A → ISP-B | `config system interface / edit port2 / set status down` on LON; expect `Internet-SLA` to mark member `dead`, traffic shifts to ISP-B |
| T10 | Failover HK hub → TY hub | shut HK overlay tunnels; LON BGP withdraws HK paths, TY9 takes over |
| T11 | MPLS path preferred for corp | tag corp traffic; `get router info routing-table all` shows MPLS next-hop with higher local-pref |
| T12 | Health probe targets | `diagnose sniffer packet any 'host 8.8.8.8 or host 1.1.1.1' 4` |

---

## 19. Failure Scenarios

| Scenario | Trigger | Expected | Recovery |
|---|---|---|---|
| Primary ISP loss at LON | shut port2 on LONFW | All sessions move to ISP-B; SD-WAN re-evaluates | restore port2; rules return to baseline |
| Primary hub down | shut port2/port3 on HK5DCFW | LON tunnels to HK5 drop; BGP withdraws HK5 routes; TY9 takes over | restore HK5 WAN; tunnels and BGP re-establish |
| MPLS-RTR down | shut HK5-MPLS-RTR | MPLS BGP neighbour drops; corp traffic falls back to overlay | restore MPLS-RTR; BGP re-converges |
| MikroTik reboots | reboot MikroTik CHR | All ISP underlays drop; IPsec re-keys after MikroTik comes back | wait 30–60 s; SLA recovers |
| Eval license expires | roll FGT clock +16 days | Throughput throttled to 1 Mbps; UTM disabled | apply trial license, reboot |
| BGP neighbour flap | `clear router bgp neighbor 172.20.196.1` | Routes briefly withdrawn; ADVPN shortcuts may rebuild | session re-establishes |

---

## 20. PNETLab Snapshots

- `00-bare` — all VMs imported, wired, not configured
- `10-mikrotik-up` — MikroTik fully addressed, simulated DNS hosts replying
- `20-fgt-mgmt-up` — all three FGTs reachable on `192.168.100.x`
- `30-wan-up` — WAN interfaces and default routes in; ISPs pingable
- `40-tunnels-up` — ADVPN tunnels established (T03 green)
- `50-bgp-up` — iBGP overlays + MPLS BGP up (T04 green)
- `60-sdwan-policy` — SLA + service rules + firewall policies in place (T05–T08 green)
- `90-known-good` — full pass of §18

---

## 21. Known Issues / Review Items

1. **`priority-zone "HongKong" "Tokyo"` doesn't match defined zones (`HK5DC` / `TY9DC`).** Either rename the zones to `HongKong` / `Tokyo` everywhere, or change the service rule to `priority-zone "HK5DC" "TY9DC"`. Either way, make them match.
2. **Redundant blackhole routes for `8.8.8.8/32` and `1.1.1.1/32`** on MikroTik. The bridge interface with the IP already creates a connected route — drop the blackhole entries.
3. **`HK-Reachability` health check defaults to all underlay members**, which can't reach the HK loopback (`172.20.196.1`) over the internet underlay. Pin it to overlay members with `set members <ids>`.
4. **`set members 0` semantics:** in current FortiOS, `0` means "all members"; double-check on your build (`get system sdwan health-check` to see the resolved list).
5. **IPsec phase1/phase2 templates not in the source notes.** §12 is a best-practice template — adjust `network-id`, PSK source, and proposal to match your security baseline.
6. **BGP config not in source notes.** §13 is a best-practice template — verify `ebgp-enforce-multihop`, `update-source`, and `additional-path` flags against your FortiOS build.
7. **MPLS path is not an SD-WAN member** in this build. Section §17 item 9 explains how to convert it to one if you want SD-WAN to steer between MPLS and internet.
8. **FGT `port1` mgmt allows HTTP** on hubs (`set allowaccess ping http ssh`). Disable HTTP and stick to HTTPS+SSH for any non-isolated lab.
9. **TY9 mgmt typo:** source called it `TY5DCFW` once; standard is `TY9DCFW`.
10. **Default credentials** (`admin / 123`) — fine for a closed lab, change before exposing the lab on any shared network.

---

## 22. Appendix A — Per-device CLI placeholders

Paste working configs as you stabilise each device.

```
# HK5DCFW
config system global
    set hostname "HK5DCFW"
end
<paste interfaces, sdwan, vpn, router bgp, firewall policy>
```

```
# TY9DCFW
config system global
    set hostname "TY9DCFW"
end
<paste config>
```

```
# LONFW
config system global
    set hostname "LONFW"
end
<paste config>
```

```
# HK5-MPLS-RTR
<paste OSPF + BGP + redistribution>
```

```
# TY9-MPLS-RTR
<paste config>
```

```
# LON-MPLS-RTR
<paste config>
```

```
# MikroTik (ISP simulator)
<final consolidated config>
```

---

## 23. Appendix B — Test evidence

Attach screenshots of `diagnose` / `get` outputs and traffic captures for each test in §18. Suggested filenames: `T01-mgmt.png`, `T03-tunnels.png`, `T04-bgp.png`, `T05-sdwan-health.png`, etc.

---

## 24. References

- Fortinet SD-WAN Architecture Guide — `<URL>`
- Fortinet ADVPN Deployment Guide — `<URL>`
- Fortinet 7.4 Cookbook (SD-WAN sections) — `<URL>`
- Source design doc — `Dual-Hub-SDWAN-HK5-TY9-LON.docx` (uploaded by author)
- This lab in PNETLab — `<URL>`
