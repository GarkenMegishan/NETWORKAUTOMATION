# Arista EOS

EOS feels like Cisco IOS at first glance, but the differences matter — especially around config sessions, EOS's Linux substrate, and the EVPN/VXLAN heritage. Arista is most often deployed as datacenter spine/leaf, so the patterns here lean that direction.

## Config sessions — Arista's safety mechanism

EOS supports config sessions, which give you Junos-like staging on a Cisco-like CLI:

```
configure session add-vlan-50
   vlan 50
      name Guest_WiFi
   show session-config diffs
   commit timer 0:05:00       ! auto-rollback in 5 min if not confirmed
   commit                      ! confirm
```

Default to sessions for any change beyond a one-line tweak. They produce diffs you can review, support timed auto-rollback, and don't pollute the running config until commit.

The CLI shortcut `show session-config diffs` is the equivalent of Junos's `show | compare`.

## Idempotency

EOS CLI is idempotent in the same way Cisco IOS is — re-applying the same line is a no-op. The `arista.eos` Ansible collection has resource modules (`eos_l2_interfaces`, `eos_bgp_global`) that reconcile state declaratively.

eAPI (HTTP/JSON-RPC) is the preferred programmatic interface — much faster and structured-data-friendlier than screen-scraping `show` output.

## Linux substrate matters

EOS runs on Linux and exposes it. You can `bash` from the EOS CLI, write Python directly on the box, or run agents (eAPI, sFlow, syslog forwarders) as native processes. This is occasionally relevant for automation — e.g., dropping a Python troubleshooting script on the device itself.

## Common config patterns

### VLAN + access port
```
vlan 50
   name Guest_WiFi
!
interface Ethernet1
   description Access port - Guest WiFi
   switchport mode access
   switchport access vlan 50
   spanning-tree portfast
   spanning-tree bpduguard enable
```

### Trunk
```
interface Ethernet48
   description Uplink to spine
   switchport mode trunk
   switchport trunk allowed vlan 10,20,30,50
   switchport trunk native vlan 999
```

### MLAG (Arista's vPC equivalent)
```
mlag configuration
   domain-id MLAG-LEAF-PAIR
   local-interface Vlan4094
   peer-address 10.255.255.2
   peer-link Port-Channel1000
!
interface Port-Channel10
   mlag 10
```

### EVPN/VXLAN leaf basics
This is where Arista really lives. Skeleton:

```
service routing protocols model multi-agent
!
interface Vxlan1
   vxlan source-interface Loopback1
   vxlan udp-port 4789
   vxlan vlan 50 vni 10050
!
router bgp 65001
   router-id 10.0.0.1
   no bgp default ipv4-unicast
   neighbor SPINES peer group
   neighbor SPINES remote-as 65000
   neighbor SPINES update-source Loopback0
   neighbor SPINES send-community extended
   neighbor 10.0.0.10 peer group SPINES
   !
   address-family evpn
      neighbor SPINES activate
   !
   vlan 50
      rd auto
      route-target both auto
      redistribute learned
```

When generating EVPN configs, always confirm the symmetric vs asymmetric IRB choice with the user — symmetric is the modern default but the configs are not interchangeable.

### BGP underlay (typical leaf)
```
router bgp 65001
   router-id 10.0.0.1
   neighbor 10.0.0.10 remote-as 65000
   neighbor 10.0.0.10 description SPINE-1
   address-family ipv4
      neighbor 10.0.0.10 activate
      network 10.0.0.1/32
```

## Common troubleshooting

| Symptom | First-line commands |
|---|---|
| Interface down | `show interfaces ethernet 1`, `show interfaces status` |
| MLAG split-brain | `show mlag detail`, `show mlag config-sanity` |
| BGP not establishing | `show bgp summary`, `show bgp neighbors 10.0.0.10` |
| EVPN routes missing | `show bgp evpn summary`, `show bgp evpn route-type mac-ip`, `show vxlan vtep` |
| Hardware programming | `show platform trident hardware capacity` (Trident chips), `show hardware capacity` |

For VXLAN troubleshooting, `show vxlan vtep` and `show vxlan address-table` are the bread and butter.

## Automation tooling

- **Ansible**: `arista.eos` collection — eAPI-based, has resource modules. `arista.avd` (Arista Validated Designs) is a higher-level role library for full fabric generation.
- **eAPI**: native HTTP/JSON-RPC. Either via `pyeapi` (Python) or direct REST. Returns structured JSON — much nicer than parsing CLI.
- **CloudVision Portal (CVP)**: Arista's centralized management; has an API for config push at scale. Worth mentioning when the user is at >50 switches.
- **NAPALM**: `napalm-eos` — works fine, but eAPI directly is usually cleaner.

## Gotchas

- **`copy running-config startup-config`** is required — same as Cisco. EOS doesn't auto-save.
- **`service routing protocols model multi-agent`** is required for EVPN; older "ribd" model can't do EVPN. If the user's existing config doesn't have this line and they're trying to add EVPN, that's the first fix.
- **MLAG peer-link must allow all VLANs** that are stretched between peers. Mismatch → black-holed traffic.
- **VXLAN `vxlan udp-port 4789`** is the IETF default. Some legacy VMware NSX-V deployments use 8472 — confirm before generating.
- **eAPI ships disabled by default**. To use any API automation, you need `management api http-commands` enabled.
