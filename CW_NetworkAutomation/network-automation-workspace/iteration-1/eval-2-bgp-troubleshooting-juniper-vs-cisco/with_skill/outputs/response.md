# eBGP stuck — MX480 ↔ ASR1001-X

Symptom restated: eBGP between MX480 (Junos 21.4, AS 65100) and ASR1001-X (IOS-XE 17.9, AS 65200) won't establish. Junos shows `Active`; Cisco shows `Idle/Active`. Direct point-to-point link, ASNs configured.

When BGP is stuck in `Active`, that means *one side is trying to open a TCP-179 connection and not getting a response*. So the diagnostic order should follow the OSI/connection-establishment chain — fastest-to-check failures first.

## Ranked likely causes

1. **TCP/179 not reaching the other side** (ACL on Cisco, firewall-filter on Junos, or the link itself dropping it).
2. **Source-interface / update-source mismatch** — neighbor IP doesn't match what the other side expects to see as source.
3. **MD5/authentication mismatch** — one side has a password, the other doesn't, or they differ.
4. **Hold-down between flaps** — if it just changed, give it 60s before declaring it stuck.
5. **MTU / TCP-MSS** — less common at this stage (BGP won't even open the TCP session if MTU is too small for SYN, but path-MTU issues kill it after open).
6. **BGP-level policy** — only relevant once the session is established; if it's stuck in Active, it's pre-OPEN.

## Step-by-step diagnostic

### Step 1 — Confirm the session state and what each side is trying

**On the MX480 (Junos):**
```
show bgp summary
show bgp neighbor <cisco-peer-ip>
```
Look for:
- `Peer: <ip> AS <as>` — confirm AS numbers
- `Type: External` — confirm eBGP
- `Local: <ip>` — what source-IP Junos is using
- `State: Active` — confirms our symptom
- `Last Error:` — connection refused, hold timer expired, etc. — this often points right at the cause

**On the ASR (IOS-XE):**
```
show ip bgp summary
show ip bgp neighbors <junos-peer-ip>
```
Look for:
- `BGP state = Active` (or Idle)
- `Local host: <ip>, Local port: random`
- `Last reset reason:` — same as Junos's `Last Error`
- Configured `update-source` — if any

The two `Local:` IPs must be reachable from each other and must match the `neighbor <ip>` configured on the opposite side.

### Step 2 — TCP/179 reachability

This catches the most common cause first.

**From the Junos side, telnet to the Cisco's BGP IP on 179:**
```
ssh
telnet <cisco-peer-ip> 179
```
(Junos shell-out, or `request system process telnet 179 host <cisco-peer-ip>`.)

**From the Cisco side:**
```
telnet <junos-peer-ip> 179
```

If telnet to 179 fails one direction, look at filters:

**Junos — check firewall-filters in the path:**
```
show configuration interfaces <wan-interface> | display set | match filter
show firewall log
show firewall counter filter <name>
```

**Cisco — check ACLs on transit interfaces:**
```
show running-config interface <wan-interface> | include access-group
show access-lists <ACL-NAME>
show ip access-lists <ACL-NAME>
```

Look for `tcp eq bgp` or `tcp eq 179` permits. ACL hit counters reveal whether traffic is even reaching the rule.

### Step 3 — Source-interface alignment

This is sneaky: if Junos has `local-address 10.0.0.1` set but Cisco's `neighbor 10.0.0.1 remote-as 65100` config points to the wrong Junos IP, the SYNs arrive from one IP and the listener expects another.

**Junos:**
```
show configuration protocols bgp group <group-name> | display set
```
Look for `local-address` or `neighbor <ip>`.

**Cisco:**
```
show running-config | section bgp
```
Look for `update-source <interface>` — that determines the source-IP Cisco uses. The Junos side's `neighbor <ip>` must equal the IP on Cisco's update-source interface.

### Step 4 — Authentication

**Junos:**
```
show configuration protocols bgp group <group-name> neighbor <ip> | display set | match authentication
```

**Cisco:**
```
show running-config | section bgp | include password
```
Look for `neighbor <ip> password ...`. If one side has it and the other doesn't, the TCP handshake completes but the OPEN never gets accepted — you'll see `Authentication failed` or `MD5 digest mismatch` in logs.

### Step 5 — If still stuck, capture the SYN

**Cisco:** enable BGP events debugging briefly (low-impact):
```
debug ip bgp <junos-peer-ip> events
```
Watch terminal monitor for "active open failed", "timed out", etc. Disable with `undebug all` immediately after — never leave on a production box.

**Junos:** enable BGP traceoptions:
```
set protocols bgp traceoptions file bgp-debug.log
set protocols bgp traceoptions flag open detail
set protocols bgp traceoptions flag state detail
commit confirmed 5
```
Then read with `show log bgp-debug.log`. Roll back when done.

## Most-common culprits in this scenario

When I see a brand-new eBGP between two routers and one side stuck in Active:
- ~40% of the time: an inbound ACL on Cisco's WAN interface that didn't permit `tcp eq 179` (or a firewall-filter on Junos doing the same).
- ~25%: source-interface mismatch (especially when one side uses a loopback peer and the other uses the physical interface IP).
- ~20%: MD5 password typo'd on one side.
- ~10%: ASNs configured but wrong on one side (less likely here since you said both are right).
- ~5%: physical/MTU issues.

Start with the telnet test in Step 2 — it tells you in 5 seconds whether the problem is L3/L4 connectivity or something further up the stack.
