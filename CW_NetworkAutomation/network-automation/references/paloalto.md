# Palo Alto PAN-OS

PAN-OS is fundamentally object-oriented and zone-based. The mental model is different from a traditional router — you build address objects, service objects, and security profiles, then reference them in policies. Generate configs that respect this structure rather than fighting it.

Two deployment modes you'll see:
- **Standalone PA firewall** — manage via web UI or CLI on the device.
- **Panorama-managed** — central management. Configs live in device groups and templates, pushed to firewalls. For any environment with more than a handful of firewalls, Panorama is the answer; generate Panorama-flavored configs in those cases.

## The candidate / commit model

Like Junos, PAN-OS has candidate config and explicit commit. Until you commit, nothing is live.

```
edit
set address obj-web-server ip-netmask 10.1.1.10/32
commit description "Add web server object"
```

In the web UI, the `Commit` button at top-right triggers the same operation. In automation, the XML API call is `op cmd=<commit>`.

There's no `commit confirmed` equivalent in PAN-OS. The closest is `commit` followed by validation, with a manual rollback if something breaks. For risky changes, snapshot the running config first (`save config to pre-change.xml`) so you can `load config from pre-change.xml` and re-commit.

## Idempotency

PAN-OS XML config is idempotent at the object level — you can re-create the same address object and nothing happens. The `paloaltonetworks.panos` Ansible collection works well for this.

For policy automation, **rule order matters**. Inserting a rule blindly can change the effective policy. Always specify position (`location: top` / `bottom` / `before` + `existing-rule`).

## Object model

The hierarchy that matters:

```
Address objects → Address groups
Service objects → Service groups
Security profiles (AV, AS, URL, file blocking, WildFire) → Profile groups
Tags
Applications (built-in + custom)
                ↓
        Security policy rules (use the above)
        NAT policy rules
        QoS policy rules
        Decryption policy rules
```

Generate objects first, then policies that reference them. Don't inline IPs into rules (`source: 10.1.1.10`) — create an address object (`obj-web-server`) and reference it. Future you will thank you.

## Common config patterns (CLI / set form)

### Address object
```
set address obj-web-server description "Production web server" ip-netmask 10.1.1.10/32
set address obj-rfc1918-10 ip-netmask 10.0.0.0/8
```

### Address group
```
set address-group grp-internal-servers static [ obj-web-server obj-db-server obj-app-server ]
```

### Service object
```
set service svc-tcp-8443 protocol tcp port 8443
```

### Security policy rule (zones are mandatory)
```
set rulebase security rules ALLOW-WEB-INBOUND \
    from untrust to trust \
    source any \
    destination obj-web-server \
    application [ web-browsing ssl ] \
    service application-default \
    action allow \
    log-end yes \
    profile-setting group default-profiles
```

Note `application` + `service application-default` — PAN-OS App-ID is the differentiator vs port-based firewalls. Use App-ID where possible, port-based as fallback.

### NAT rule (destination NAT for inbound)
```
set rulebase nat rules NAT-WEB-INBOUND \
    from untrust to untrust \
    source any \
    destination <PUBLIC_IP_OBJ> \
    service svc-tcp-443 \
    to-interface ethernet1/1 \
    destination-translation translated-address obj-web-server translated-port 8443
```

Note the to/from zone for inbound DNAT — it's `untrust → untrust` because the destination zone is determined *after* NAT.

### Panorama device group + template
```
edit
set device-group GLOBAL description "Global rules for all firewalls"
set device-group GLOBAL pre-rulebase security rules <as above>
set template TPL-BASE description "Base template (NTP, syslog, DNS)"
```

When generating Panorama config, always specify whether rules are pre-rulebase (evaluated before local) or post-rulebase (after local). Default to pre for shared baseline policies.

## Common troubleshooting

| Symptom | First-line commands |
|---|---|
| Traffic blocked | `show session all filter source x.x.x.x destination y.y.y.y`, then `show session id <id>` for details |
| Policy not matching | `test security-policy-match from trust to untrust source x.x.x.x destination y.y.y.y application web-browsing` |
| URL category wrong | `test url <url>` |
| BGP / routing | `show routing protocol bgp summary`, `show routing route` |
| Commit failing | Check the commit log in the GUI; CLI `show jobs id <id>` |

The `test` commands are gold — they let you query the policy engine without sending real traffic.

## Automation tooling

- **Ansible**: `paloaltonetworks.panos` collection. Uses the XML API under the hood. Works against firewalls and Panorama.
- **pan-os-python** (`panos` package): Python SDK. Better for building larger applications; cleaner than calling XML API directly.
- **Terraform**: `paloaltonetworks/panos` provider — works for both single-firewall and Panorama. State management is critical here; never commit `tfstate`.
- **Expedition**: Palo Alto's official migration tool (other vendors → PAN-OS). Mention it for migration projects.

## Gotchas

- **Zone names are case-sensitive** in some operations and config locations. Stick to a convention (`untrust`, `trust`, `dmz` lowercase).
- **App-ID dependencies**: `web-browsing` implicitly depends on `dns`. If you allow only `web-browsing` and not `dns`, lookups fail. Always cross-reference application dependencies.
- **Implicit deny at the bottom**: PAN-OS has an implicit `deny all` at the end of the rulebase, plus default `intrazone-default allow` and `interzone-default deny`. Don't forget these — they often explain "why is this traffic working/not working".
- **Commit can take minutes** on large configs. In automation, set generous timeouts.
- **Panorama push order**: Commit to Panorama first, then push to devices. They are separate operations. Confused order = "config differs" warnings.
- **Service `application-default`** is not the same as "any service" — it's "the default port for the matched App-ID". Subtle and important.
