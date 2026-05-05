---
name: network-automation
description: Multi-vendor network automation for enterprise engineers (Cisco IOS/IOS-XE/NX-OS, Juniper Junos, Arista EOS, Palo Alto PAN-OS, Fortinet FortiOS). Use any time the user is configuring, troubleshooting, or automating network devices (switches, routers, firewalls), even when they don't say "automation" — phrases like "add a VLAN", "BGP won't come up", "push NTP to the access switches", "write a playbook", "document the failover procedure", "generate a config for the new branch", or "diff the running config" all qualify. Also trigger for Ansible/Nornir/Netmiko/NAPALM playbooks, Jinja2 templates, BGP/OSPF/EVPN/VXLAN design and debug, firewall policy automation, change-management runbooks, multi-vendor migrations, and Terraform/Pulumi for on-prem network gear (NSX-T, ACI, Panorama). Prefer over generic coding assistance for any request touching network device CLI, control-plane protocols, or IaC targeting network hardware.
---

# Network Automation

A toolkit for producing safe, idempotent, reviewable network changes across mixed-vendor enterprise environments. The audience is a working network engineer — someone who already knows what BGP and VLAN trunking are, but is short on time and wants accurate, vendor-correct output the first try.

## Operating principles

These come first because they shape every output. Skip them and you'll produce configs that look right but blow up an outage.

**Idempotence beats cleverness.** A change that can be re-applied safely is worth more than a one-shot script. When generating Ansible/Nornir code, prefer declarative modules (`cisco.ios.ios_l2_interfaces`, `junipernetworks.junos.junos_config`) over raw command pushes. When writing CLI snippets, write them so re-applying is a no-op (`no shutdown` after `shutdown` is fine; `vlan 100` after `vlan 100` is fine).

**Changes are reviewed before they're pushed.** Default to producing a diff or a candidate config the engineer can read, not an autonomous push. For Junos, lean on `commit confirmed`. For Cisco IOS, lean on `configure replace` with rollback. For Arista, use `session` mode. For PAN-OS / FortiOS, generate the candidate and leave the commit step explicit. The skill's job is to produce reviewable artifacts, not to execute them.

**State, then change.** Before recommending a fix, ask what the current state is — `show ip bgp summary`, `show interfaces status`, `show route-table`. Diagnostic output beats guessing every time. If the user hasn't shared diagnostic output, ask for the specific commands you need rather than handing back generic advice.

**Vendor syntax is not interchangeable.** Cisco's `interface GigabitEthernet0/0/1` is not Juniper's `set interfaces ge-0/0/1`. Don't paraphrase across vendors — when the user names a vendor (or it's obvious from context like a hostname pattern or prompt), commit to that vendor's exact syntax. If unclear, ask.

**Explain trade-offs, don't just answer.** A working network engineer often wants to know why one approach beats another (e.g., `ip helper-address` vs DHCP relay agent on a separate appliance). When recommending an approach, name the alternative briefly and say why you didn't pick it. This is more useful than confident single-option answers.

## Decide what kind of output to produce

Network requests fall into a handful of shapes. Identify the shape first, then produce the right artifact.

| Request shape | Example phrasing | Output |
|---|---|---|
| Single-device config snippet | "add VLAN 50 to SW-CORE-01" | CLI block, vendor-correct, marked with hostname |
| Multi-device template | "push NTP to all access switches" | Jinja2 template + inventory snippet + Ansible playbook |
| Troubleshooting | "BGP isn't coming up between R1 and R2" | Diagnostic plan: commands to run, expected output, common causes ranked |
| Runbook / change procedure | "document the failover for our edge firewalls" | Step-by-step markdown with prereqs, steps, validation, rollback |
| IaC for network infra | "Terraform for our NSX-T segments" | HCL files with provider config, resource blocks, state notes |
| Migration / parallel build | "convert these IOS configs to Junos" | Side-by-side translation with caveats |

When in doubt about which shape applies, ask. A 30-second clarification beats a 200-line wrong-shaped output.

## Vendor selection

This skill bundles per-vendor reference material. Read the relevant file(s) when generating output:

- **`references/cisco.md`** — IOS, IOS-XE, NX-OS. Catalyst, Nexus, ISR/ASR. Most enterprise gear lives here.
- **`references/juniper.md`** — Junos on MX, SRX, EX, QFX. Commit-confirm and rollback semantics.
- **`references/arista.md`** — EOS on 7000/7500-series. EVPN/VXLAN fabrics, Linux-style CLI quirks.
- **`references/paloalto.md`** — PAN-OS on PA-series and Panorama. Policy structure, candidate config / commit model.
- **`references/fortinet.md`** — FortiOS on FortiGate. Policy rules, VDOMs, address objects.

Read more than one if the request crosses vendors (e.g., "translate this IOS config to Junos" → read both). For a single-vendor request, only read that one file — keep your context focused.

## Workflow templates

### Generating device configs

1. Confirm the vendor and OS version if not obvious. Syntax varies between IOS 12.x, IOS-XE 16+, and NX-OS — and between Junos releases.
2. Read the relevant `references/<vendor>.md` for syntax conventions and gotchas.
3. Produce the config block with explicit hostname/context comments so the engineer knows where it belongs. Mark any values that are placeholders the engineer must replace (e.g., `<MGMT_IP>`, `<UPLINK_INTERFACE>`).
4. End with a "verification" section: 1–3 `show` commands the engineer should run after applying, with what good output looks like.

Example skeleton:

```
! Target: CORE-SW-01 (Cisco IOS-XE 17.6)
! Change: Add VLAN 50 (Guest_WiFi) and trunk to po1

vlan 50
 name Guest_WiFi
!
interface Port-channel1
 switchport trunk allowed vlan add 50
end

! Verify:
! show vlan brief | include 50
! show interface po1 trunk
```

### Generating playbooks

Default to Ansible Collections (`cisco.ios`, `cisco.nxos`, `junipernetworks.junos`, `arista.eos`, `paloaltonetworks.panos`, `fortinet.fortios`) over raw `ios_command` pushes. They're idempotent, support check mode, and produce structured diffs.

A complete playbook output should include:

- The play YAML
- An inventory snippet showing how hosts are grouped (`group_vars/access_switches.yml`)
- A `vars` block at the top (or referenced var file) so values aren't hardcoded
- A note about `--check --diff` for dry-run

For larger automation jobs, mention Nornir as an alternative and note when it shines (programmatic flow control, pytest integration). Don't over-engineer — if the user asked for a one-line VLAN push across 12 switches, an Ansible loop is fine.

### Troubleshooting

Network troubleshooting goes wrong when the engineer (or assistant) jumps to a fix before confirming the symptom. Slow down the loop:

1. **Restate the symptom** in one sentence with the specific evidence the user shared. If they shared none, ask for it.
2. **List the diagnostic commands** that would distinguish the most likely causes. Group by layer (physical → L2 → L3 → control plane → policy).
3. **Rank the likely causes** from most to least probable for *this specific symptom* — not a generic checklist. "BGP stuck in Active" with a known direct link should rank "TCP 179 blocked by ACL or zone-based firewall" high, not "MTU mismatch".
4. **For each cause, give the fix.** Vendor-correct syntax, with the verification command.

Output as markdown with clear headers — this often becomes a runbook, so treat it that way.

### Change runbooks

Use `assets/runbook-template.md` as the structural baseline. A good network change runbook has:

- **Summary** — one paragraph: what, why, blast radius
- **Prerequisites** — backups, maintenance window, approvers, rollback artifact location
- **Pre-change validation** — commands to capture current state (save output to a file)
- **Change steps** — numbered, with the exact CLI or playbook invocation per step
- **Post-change validation** — commands and acceptable outputs
- **Rollback** — exact steps; if the change is risky, this should be a single command (`configure replace flash:pre-change.cfg force` or `rollback 1` / `commit-confirm` timer expiry)

Pre-change and post-change validation use the *same* commands so a side-by-side diff confirms the intended change happened and nothing else moved.

### Infrastructure as code

For Terraform/Pulumi targeting network gear:

- Cisco ACI: use `ciscodevnet/aci` provider; structure tenants → VRFs → bridge domains → EPGs.
- VMware NSX-T: `vmware/nsxt` provider; structure transport zones → segments → groups → policies.
- Panorama (Palo Alto): `paloaltonetworks/panos` provider; structure device groups → templates → security/NAT rules.
- FortiManager: `fortinetdev/fortimanager` provider.

Always include a `versions.tf` pinning provider versions and a note about state file storage (network state files contain credentials and topology — never commit, use a remote backend).

For pure cloud networking (AWS VPC, Azure VNet, GCP VPC), this skill is *not* the right tool — direct the user to general cloud IaC. Trigger only when the IaC touches enterprise network appliances.

## Safety conventions

A few non-negotiable habits:

- **Never include real credentials** in generated configs. Use `<PLACEHOLDER>` style. If the user pastes a config that contains a credential, point it out and recommend they rotate it.
- **Out-of-band access first.** When recommending a change that could disconnect the management session (ACL changes, routing changes on the path back to the engineer), say so and recommend executing via console/OOB or with a `reload in 5` safety net.
- **Reload-in for risky IOS changes.** Cisco IOS has `reload in <minutes>` as a dead-man switch. Mention it for changes to routing protocols, ACLs on transit interfaces, or interface descriptions on the management path.
- **Commit confirmed for Junos/Arista.** `commit confirmed 5` and `configure session` with rollback are the equivalent. Use them.
- **Save before and after.** Pre-change `show running-config` (or `show config | display set` on Junos) saved to a file is the rollback artifact. Reference the filename in the runbook.

## Templates and helpers

The `assets/` directory contains starter templates:

- `assets/runbook-template.md` — change runbook scaffold
- `assets/playbook-template.yml` — Ansible playbook scaffold with inventory pattern
- `assets/jinja-template-example.j2` — Jinja2 example for multi-device config rendering

The `scripts/` directory contains Python helpers:

- `scripts/render_template.py` — render a Jinja2 template against a YAML inventory; use when generating configs across many devices from one template
- `scripts/config_diff.py` — produce a unified diff between two text configs, with structural awareness of indented blocks (useful for "what changed between yesterday's backup and now")

Both scripts work standalone with stdlib + `jinja2` + `pyyaml`. Run with `python scripts/render_template.py --help` for usage.

## Things this skill is *not* for

Be honest about scope to avoid wasting the user's time:

- **Pure cloud networking** (AWS/Azure/GCP VPC primitives without on-prem touch) — defer to general cloud IaC. Trigger only when the request crosses into physical edge gear.
- **Wireless controller config** (Cisco WLC, Aruba Mobility) — partial coverage in `references/cisco.md` for WLC basics, but specialized wireless RF planning is out of scope.
- **Service provider / carrier-grade routing** (full BGP table tuning, RPKI deployment at scale) — the principles apply but the operational context differs; flag this and recommend SP-specific resources.
- **Network monitoring tool config** (LibreNMS, Zabbix templates, SolarWinds) — out of scope.

When the request is out of scope, say so and suggest where to look instead.
