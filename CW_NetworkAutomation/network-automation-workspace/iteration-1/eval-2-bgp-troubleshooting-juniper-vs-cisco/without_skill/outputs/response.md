# BGP Troubleshooting: MX480 to ASR1001-X

When eBGP gets stuck in Active or Idle/Active, the session is failing to establish a TCP connection or the OPEN message is being rejected. Here's a checklist of things to verify on both sides.

## On the Juniper MX480

```
show bgp summary
show bgp neighbor 10.0.0.x
show route receive-protocol bgp 10.0.0.x
show route advertising-protocol bgp 10.0.0.x
show configuration protocols bgp
```

The `show bgp neighbor` output will show you the last error, the peer AS, the local AS, the holdtime, the keepalive timer, and the description. Look at `Last Error` and `Last State` to understand why it's transitioning out of Active.

Also useful:
```
show log messages | match bgp
monitor traffic interface ge-0/0/0 matching tcp port 179
```

The `monitor traffic` command captures live packets — useful if you want to see whether SYNs are leaving and being responded to.

## On the Cisco ASR1001-X

```
show ip bgp summary
show ip bgp neighbors 10.0.0.x
show ip route 10.0.0.x
show running-config | section bgp
debug ip bgp 10.0.0.x
debug ip tcp transactions
```

`show ip bgp neighbors` will give you state details, last reset reason, and the configured options. The debug commands should be used carefully on a production router — turn them off as soon as you have what you need.

## Things to check

1. **AS numbers on both sides** — you said these are correct, but worth double-checking the `peer-as` on Junos matches the local-as on Cisco and vice versa.

2. **Source/destination IPs** — make sure each side's `neighbor` statement points to the IP that the other side is sourcing from. If one side uses a loopback as update-source and the other uses the directly-connected interface, the IPs won't match.

3. **TCP port 179 reachability** — try a TCP connection test from each side:
   - Juniper: `telnet 10.0.0.x 179`
   - Cisco: `telnet 10.0.0.x 179`
   If either fails, an ACL or filter is blocking it.

4. **Authentication / MD5 password** — if one side has a BGP password configured and the other doesn't (or they differ), the session will fail. Check both:
   - Juniper: `show configuration protocols bgp group X neighbor Y` for `authentication-key`
   - Cisco: `show running-config | section bgp` for `password`

5. **MTU mismatch** — TCP-MSS clamping or a path-MTU issue can prevent BGP packets from being delivered. Check:
   - Juniper: `show interfaces ge-0/0/0 | match MTU`
   - Cisco: `show interfaces gi0/0/1 | include MTU`

6. **Hold-time / keepalive mismatch** — generally not a hard failure but can cause flaps.

7. **Routing to the peer IP** — make sure each side has a route to the peer's IP. Direct-connected should be automatic but worth verifying with `show route` / `show ip route`.

8. **TTL** — eBGP defaults to TTL=1; if there's any layer-3 hop between the two routers (a switch with routing enabled?), you'd need `multihop` configured.

## Order of operations

1. Verify physical link and basic IP reachability (ping the peer IP from each side).
2. Verify TCP/179 reachability with `telnet x.x.x.x 179`.
3. Inspect ACLs and firewall filters for anything blocking 179.
4. Compare `update-source` (Cisco) and `local-address` (Junos) configs.
5. Check for password mismatch.
6. Check AS configurations.
7. If still stuck, enable debug or monitor traffic to see SYNs.

The Last Error / Last Reset Reason output from `show ip bgp neighbors` and `show bgp neighbor` is usually the most informative single piece of data. Start there.

## Quick sanity check

Does each side ping the other's peer IP? If not, you have an L1/L2/L3 problem and BGP is downstream of that. If ping works but `telnet x.x.x.x 179` fails, you have a filter problem. If telnet works but BGP is still stuck, you have a config problem (passwords, source-interface, etc.).
