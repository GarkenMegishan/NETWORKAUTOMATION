# Dual-Hub SD-WAN Lab — HK5 / TY9 / LON (Fortinet)

**Lab platform:** PNETLab on VMware Workstation 17
**SD-WAN stack:** Fortinet FortiGate-VM + FortiManager + FortiAnalyzer
**Author:** Garry Gautane
**Last updated:** 2026-05-04
**Status:** _Draft template — fill in placeholders marked `<TBD>`_

---

## 1. Purpose

This document describes a multi-region SD-WAN lab built on PNETLab. The lab models a **dual-hub** SD-WAN deployment with active hubs in **HK5 (Hong Kong DC)** and **TY9 (Tokyo DC)** and a representative branch site in **LON (London)**. It exists to:

- Validate a production design before a green-field cutover or a brown-field migration.
- Serve as a reproducible test bed for change requests and break-fix scenarios.
- Provide a sandbox for vendor PoCs and feature validation (e.g., new policy, new transport).

---

## 2. Scope and Out-of-Scope

**In scope**
- Fortinet ADVPN dual-hub overlay across two DC sites (HK5, TY9).
- One representative spoke (LON) attached to both hubs.
- Underlay simulation across two transports (`MPLS`, `INET`).
- Central management onboarding via FortiManager; logging via FortiAnalyzer.
- iBGP per-overlay on loopbacks for route exchange.
- SD-WAN rules + Performance SLAs for application-aware steering.
- Failover, route-policy, and SLA-driven path selection tests.

**Out of scope**
- Production circuit performance.
- Real ISP SLAs (latency/jitter/loss are emulated).
- Production identity stores / RADIUS / AD federation.
- DDoS or scale testing beyond what the lab host supports.

---

## 3. Lab Host Environment

| Component | Value |
|---|---|
| Hypervisor | VMware Workstation 17 Pro |
| Lab orchestrator | PNETLab `<version>` |
| Host CPU | `<TBD — e.g., 12-core / 24-thread>` |
| Host RAM | `<TBD — e.g., 64 GB>` |
| Host storage | `<TBD — NVMe size, free GB>` |
| Nested virt | Intel VT-x / EPT enabled |
| Mgmt network | `<TBD subnet — e.g., 10.10.0.0/24>` |
| PNETLab IP | `<TBD>` |

**Resource budget** (recommended floor for this topology):

| Role | vCPU | RAM | Disk |
|---|---|---|---|
| Each FortiGate-VM edge (HK5-FGT / TY9-FGT / LON-FGT) | 2 | 4 GB | 30 GB |
| FortiManager-VM | 4 | 8 GB | 80 GB |
| FortiAnalyzer-VM (optional) | 4 | 8 GB | 80 GB |
| Underlay routers (PE/CE emulation) | 1 | 2 GB | 4 GB |
| Test endpoints (Linux) | 1 | 1 GB | 4 GB |

---

## 4. Vendor and Image Inventory

| Function | Vendor / Image | Version | Notes |
|---|---|---|---|
| SD-WAN edge | FortiGate-VM64-KVM / FGT_VM64 | FortiOS `<7.4.x>` | Same build on hubs and spoke |
| Central management | FortiManager-VM | `<7.4.x>` | ADOM = `lab-sdwan` |
| Logging / analytics | FortiAnalyzer-VM | `<7.4.x>` | optional but recommended for SLA dashboards |
| Transport / PE | Cisco IOL L3 or vIOS-L3 | `<image build>` | provides MPLS + INET clouds |
| Test endpoint | Ubuntu Server `<22.04>` | | iperf3, mtr, tcpdump |

**Licensing note:** evaluation FortiGate-VM images allow ~15 days without a license; raise an eval license in the FortiCare portal if you need to keep the lab live. FortiManager runs in trial mode without a license but is limited to 5 managed devices, which is sufficient for this topology.

---

## 5. Topology

### 5.1 Site roles

| Site code | Location | Role | FortiGate nodes |
|---|---|---|---|
| HK5 | Hong Kong DC | Primary hub | HK5-FGT-01 (`<+ -02 if HA cluster>`) |
| TY9 | Tokyo DC | Secondary hub | TY9-FGT-01 (`<+ -02 if HA cluster>`) |
| LON | London branch | Spoke | LON-FGT-01 |

### 5.2 ASCII topology (logical overlay)

```
                       ┌────────────────────┐
                       │   FortiManager     │
                       │   FortiAnalyzer    │
                       └─────────┬──────────┘
                                 │ FGFM mgmt + syslog
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
   ┌────┴────┐              ┌────┴────┐              ┌────┴────┐
   │ HK5-FGT │◀── ADVPN ───▶│ TY9-FGT │◀── ADVPN ───▶│ LON-FGT │
   │  (hub1) │              │  (hub2) │              │ (spoke) │
   └────┬────┘              └────┬────┘              └────┬────┘
        │ MPLS  INET             │ MPLS  INET             │ MPLS  INET
   ┌────┴────┐              ┌────┴────┐              ┌────┴────┐
   │  PE-HK  │              │  PE-TY  │              │  PE-LON │
   └─────────┘              └─────────┘              └─────────┘
```

**Overlay model:** Two IPsec tunnels per transport per spoke (one to HK5 hub, one to TY9 hub) — total **4 IPsec tunnels on LON-FGT** (`MPLS→HK5`, `MPLS→TY9`, `INET→HK5`, `INET→TY9`). ADVPN shortcuts negotiate spoke-to-spoke tunnels on demand.

### 5.3 Transport matrix (SD-WAN members)

Each FortiGate homes to **two transports** as SD-WAN members under a single SD-WAN zone (`overlay`). Underlay interfaces sit in zone `underlay` and are not part of the SD-WAN selection.

| FortiGate | MPLS member (zone `overlay`) | INET member (zone `overlay`) |
|---|---|---|
| HK5-FGT-01 | `vpn-mpls-spoke` (hub side) | `vpn-inet-spoke` (hub side) |
| TY9-FGT-01 | `vpn-mpls-spoke` (hub side) | `vpn-inet-spoke` (hub side) |
| LON-FGT-01 | `vpn-mpls-hk5`, `vpn-mpls-ty9` | `vpn-inet-hk5`, `vpn-inet-ty9` |

---

## 6. IP Addressing Plan

> Adjust to your real plan; this is a vendor-neutral example.

### 6.1 Underlay (transport-side)

| Transport | Subnet | Notes |
|---|---|---|
| MPLS core | `192.168.10.0/24` | static or BGP between edges and PE |
| Internet core | `203.0.113.0/24` | static defaults toward gateway |

### 6.2 FortiGate transport interfaces

| Device | MPLS WAN IP | INET WAN IP |
|---|---|---|
| HK5-FGT-01 | `192.168.10.1/30` | `203.0.113.1/30` |
| TY9-FGT-01 | `192.168.10.5/30` | `203.0.113.5/30` |
| LON-FGT-01 | `192.168.10.9/30` | `203.0.113.9/30` |

### 6.2.1 Overlay (IPsec) addressing

Use `/30` per overlay tunnel. Hubs own `.1`, spokes get `.2`.

| Tunnel | Subnet | Hub IP | Spoke IP |
|---|---|---|---|
| `LON ↔ HK5` over MPLS | `10.200.1.0/30` | `10.200.1.1` (HK5) | `10.200.1.2` (LON) |
| `LON ↔ HK5` over INET | `10.200.2.0/30` | `10.200.2.1` (HK5) | `10.200.2.2` (LON) |
| `LON ↔ TY9` over MPLS | `10.200.3.0/30` | `10.200.3.1` (TY9) | `10.200.3.2` (LON) |
| `LON ↔ TY9` over INET | `10.200.4.0/30` | `10.200.4.1` (TY9) | `10.200.4.2` (LON) |

### 6.3 LAN / service-side

| Site | Service VRF | LAN subnet | Notes |
|---|---|---|---|
| HK5 | `corp` | `10.50.0.0/16` | DC servers |
| TY9 | `corp` | `10.51.0.0/16` | DC servers |
| LON | `corp` | `10.52.0.0/24` | branch users |

### 6.4 Loopbacks (BGP router-id / source for iBGP)

Used as the BGP source on each FortiGate (`router bgp → router-id` and `update-source loopback`). One loopback per box; advertised into BGP so the overlay carries a stable next-hop independent of the transport.

| Device | Loopback | BGP AS | Site ID |
|---|---|---|---|
| HK5-FGT-01 | `10.255.0.1/32` | `65000` | `100` |
| TY9-FGT-01 | `10.255.0.2/32` | `65000` | `200` |
| LON-FGT-01 | `10.255.0.3/32` | `65000` | `300` |
| FortiManager | `10.255.0.250/32` | n/a | n/a |
| FortiAnalyzer | `10.255.0.251/32` | n/a | n/a |

---

## 7. Control-Plane Design (Fortinet)

| Element | Value |
|---|---|
| Management model | FortiManager central, ADOM `lab-sdwan` |
| Provisioning template | Per-platform CLI templates + per-device meta-fields |
| Site IDs (meta-field) | HK5=100, TY9=200, LON=300 |
| ADVPN | Enabled on all hubs and the spoke; shortcuts allowed |
| IKE / IPsec | IKEv2, AES-256-GCM, DH group 19, PFS on |
| Authentication | PSK from FortiManager template (`<vault ref>`) |
| Routing protocol | iBGP AS `65000`, neighbours per loopback, route-reflector on each hub for spokes |
| Path preference | SD-WAN rules + Performance SLA — see Section 8.2 |
| Health check / SLA probe | ICMP to `10.50.0.10` (HK5 loopback target) and `10.51.0.10` (TY9), interval 500 ms, fail-after 5 |

---

## 8. Policy

### 8.1 Routing / topology policy

- LON spoke advertises `10.52.0.0/24` to both hub neighbours over iBGP.
- Hubs advertise their LAN prefixes (`10.50.0.0/16`, `10.51.0.0/16`) and reflect spoke prefixes between sites (route-reflector on each hub).
- LON installs **HK5 path as primary** for `10.50.0.0/16` and **TY9 path as primary** for `10.51.0.0/16`. Cross-site backup via local-preference / `route-map` weights set in the FortiManager template.
- ADVPN shortcuts: **enabled** — branch-to-branch will negotiate direct tunnels through hub signalling.

### 8.2 SD-WAN rules + Performance SLA

Defined under `config system sdwan` on each FortiGate (template-driven from FortiManager). Performance SLA `corp-health` runs ICMP probes through both transports.

| Rule order | App / class | SLA target | Member preference (priority) | Strategy |
|---|---|---|---|---|
| 10 | Voice (RTP, SIP) | `lat<150 / jit<30 / loss<1` | MPLS → INET | `sla` |
| 20 | Video conferencing (Zoom, Teams) | `lat<200 / loss<2` | MPLS → INET | `sla` |
| 30 | Bulk data / backup (port 9000, NFS) | best-effort | INET → MPLS | `manual` |
| 99 | Default (catch-all) | best-effort | MPLS → INET | `manual` |

### 8.3 Security policy (if integrated NGFW present)

| Zone pair | Action | Notes |
|---|---|---|
| `LAN → WAN` | inspect | basic AV/IPS profile |
| `WAN → LAN` | deny | except published services |
| `LAN → LAN inter-site` | inspect | logging on |

---

## 9. Build Procedure (PNETLab)

1. Import FortiGate-VM, FortiManager-VM, and FortiAnalyzer-VM into PNETLab (`/opt/unetlab/addons/qemu/fortinet-fgt-<ver>/`, etc.) and set permissions:
   - `/opt/unetlab/wrappers/unl_wrapper -a fixpermissions`
2. Create a new lab: `Dual-Hub-SDWAN-HK5-TY9-LON`.
3. Add nodes per Section 5; tag with site codes (HK5 / TY9 / LON) and a `role` meta-field (`hub` / `spoke`).
4. Wire transport networks first (MPLS bridge, INET bridge), then service-side bridges per site, then a dedicated mgmt bridge for FortiManager / FortiAnalyzer reachability.
5. Power on **FortiManager and FortiAnalyzer first**; complete first-boot wizard, set the ADOM `lab-sdwan`, register a 15-day eval if needed.
6. Power on hubs (HK5-FGT-01 then TY9-FGT-01). On each, set hostname, mgmt IP, and run `execute central-management register`. Approve the device in FortiManager and import.
7. Power on LON-FGT-01, repeat the registration step.
8. From FortiManager, push the **ADVPN provisioning template** (phase1/phase2, BGP, SD-WAN zone, SD-WAN members, Performance SLA, SD-WAN rules, firewall policies).
9. Verify on each FortiGate: tunnels up, BGP peers established, Performance SLA `alive`, SD-WAN rules selecting expected member.

---

## 10. Validation Tests

For each test, capture: pass/fail, observed metric, screenshot of relevant `show` output.

| # | Test | Method (Fortinet CLI) | Expected |
|---|---|---|---|
| T01 | FortiManager management healthy | `diagnose fdsm central-mgmt` on each FGT; check device status in FortiManager | All devices `synchronized`, no out-of-sync flag |
| T02 | IPsec tunnels up | `diagnose vpn ike gateway list` and `get vpn ipsec tunnel summary` on LON-FGT | 4 tunnels `established` (HK5/MPLS, HK5/INET, TY9/MPLS, TY9/INET) |
| T03 | BGP neighbours up | `get router info bgp summary` on LON-FGT | 2 peers `Established` (HK5 loopback, TY9 loopback); prefixes received from both |
| T04 | SD-WAN Performance SLA | `diagnose sys sdwan health-check` and `diagnose sys sdwan member` on LON-FGT | All members `alive`, latency / jitter / loss within thresholds |
| T05 | SD-WAN rule selection | `diagnose sys sdwan service` on LON-FGT | Rule 10 (voice) → MPLS member; Rule 30 (bulk) → INET member |
| T06 | LON → HK5 reachability | `execute ping-options source 10.255.0.3` then `execute ping 10.50.0.10` | success, RTT recorded |
| T07 | Hub failover | shut HK5-FGT LAN port, observe convergence | TY9 path active; BGP withdraw in `<X>s`; SD-WAN re-evaluates routes |
| T08 | Path failover | drop MPLS member on LON-FGT (`set status disable`) | INET carries all traffic; voice SLA still met on INET (or rule falls back per `sla` strategy) |
| T09 | Voice SLA under loss | inject 3% loss on MPLS underlay (PNETLab netem) | Performance SLA marks MPLS `dead` for voice rule; voice shifts to INET |
| T10 | Bulk pinned to INET | iperf3 LON → HK5 dst port 9000 | Session uses INET member per Rule 30; MPLS load unaffected |
| T11 | ADVPN shortcut | ping LON-LAN → simulated second-spoke LAN; observe `diagnose vpn ike gateway list` | New shortcut tunnel appears between spokes |

---

## 11. Failure / Recovery Scenarios

| Scenario | Trigger | Expected behaviour | Recovery |
|---|---|---|---|
| Primary hub down | shut HK5-FGT WAN ports | LON tunnels to HK5 drop; BGP withdraws HK5 routes; SD-WAN selects TY9 hub | restore HK5-FGT; verify tunnels re-establish and BGP re-prefers HK5 |
| Single transport loss at branch | `set status disable` on LON MPLS member | INET carries all traffic; SD-WAN rules re-evaluate | re-enable MPLS member; verify rule selection returns to baseline |
| FortiManager outage | power off FortiManager-VM | Data plane unaffected; FortiGates show `lost` status; new policy pushes blocked | restart FortiManager; verify devices reconnect (FGFM tunnel) |
| FortiAnalyzer outage | power off FortiAnalyzer-VM | Logs queue locally on FortiGate disk; SLA dashboard goes stale | restart FortiAnalyzer; logs flush from FGT queue |
| Eval license expiry | roll FGT clock forward 16 days | FGT enters reduced-functionality mode | apply trial license; reboot |
| BGP neighbour flap | `clear router bgp neighbor 10.255.0.1` | Routes withdrawn briefly; tunnels stay up; SLA still measures | session re-establishes; routes reinstall |

---

## 12. Lab Snapshots

Recommended PNETLab snapshot set:

- `00-bare` — wired but not configured
- `10-fmg-faz-up` — FortiManager + FortiAnalyzer onboarded, no FGTs
- `20-hubs-up` — HK5 + TY9 FGTs registered to FortiManager, ADVPN ready
- `30-spoke-up` — LON-FGT joined; tunnels and BGP healthy (T01–T03)
- `40-policy-applied` — SD-WAN rules + Performance SLA + firewall policies in place
- `90-known-good` — full pass of Section 10

---

## 13. Cutover / Migration Notes

When promoting this design to a brown-field environment:

- Stage FortiGates on the **same FortiOS build** validated in lab (Section 4) and on the same FortiManager version.
- Re-use the **FortiManager provisioning template** from the lab; bind it to the production ADOM with site meta-fields.
- Replace lab PSKs with vault-sourced PSKs or move to certificate-based IKE.
- Pre-stage loopback IPs and BGP AS to match lab to keep route-maps and policies portable.
- Run T07/T08 in a production maintenance window before cutover.
- Keep an MPLS-only fallback (SD-WAN rules disabled, static routes pinned) documented in the change-request rollback section.

---

## 14. Known Issues / Caveats

- FortiGate-VM eval license expires after 15 days; the data plane keeps forwarding but throughput drops to 1 Mbps and management throws license warnings.
- Nested FortiGate-VM clock drift can cause IKE failures — enable NTP on every FGT pointed at the FortiManager or PNETLab host clock.
- Performance SLA `<500 ms` interval can spike CPU on small VM sizing; raise the interval or boost vCPU if you see false `dead` flags.
- ADVPN shortcuts require the spokes to also have an ADVPN-capable phase1; verify with `diagnose vpn ike gateway list name <tunnel>` and look for `auto-discovery: enabled`.
- PNETLab nodes do not represent real path latency; SD-WAN SLA thresholds must be re-validated on real circuits before production.

---

## 15. References

- Fortinet SD-WAN Architecture Guide — `<URL>`
- Fortinet ADVPN Deployment Guide — `<URL>`
- FortiManager Administration Guide — `<URL>`
- Internal design doc — `<link to Dual-Hub-SDWAN-HK5-TY9-LON.docx>`
- Change request template — `<link>`
- This lab in PNETLab — `<URL>`

---

## 16. Appendix A — Per-node config snippets

Paste the working FortiOS CLI from each device here. Keep them in fenced code blocks so they paste cleanly into change tickets and FortiManager scripts later.

```
# HK5-FGT-01
config system global
    set hostname "HK5-FGT-01"
end
config vpn ipsec phase1-interface
    edit "vpn-mpls-spoke"
        ...
    next
end
config router bgp
    set as 65000
    ...
end
config system sdwan
    ...
end
```

```
# TY9-FGT-01
<config>
```

```
# LON-FGT-01
<config>
```

---

## 17. Appendix B — Test evidence

Attach screenshots of `show` outputs and traffic captures for each test in Section 10. Name files `T01-control-connections.png` etc.
