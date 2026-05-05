# Multi-vendor NTP Ansible playbook

You've got three vendors with three different network OSes, so the cleanest approach is one playbook with three plays — one per OS group — each using the official collection's NTP resource module. This stays idempotent, supports `--check --diff` dry-run, and avoids hand-pushing `ntp server` lines.

## Inventory

`inventory.yml`:

```yaml
all:
  vars:
    ansible_user: "{{ vault_net_user }}"
    ansible_password: "{{ vault_net_password }}"
    ansible_connection: ansible.netcommon.network_cli
  children:
    cisco_ios:
      hosts:
        ios-sw-01: { ansible_host: 10.10.0.11 }
        ios-sw-02: { ansible_host: 10.10.0.12 }
        ios-sw-03: { ansible_host: 10.10.0.13 }
        ios-sw-04: { ansible_host: 10.10.0.14 }
        ios-sw-05: { ansible_host: 10.10.0.15 }
        ios-sw-06: { ansible_host: 10.10.0.16 }
        ios-sw-07: { ansible_host: 10.10.0.17 }
        ios-sw-08: { ansible_host: 10.10.0.18 }
        ios-sw-09: { ansible_host: 10.10.0.19 }
        ios-sw-10: { ansible_host: 10.10.0.20 }
        ios-sw-11: { ansible_host: 10.10.0.21 }
        ios-sw-12: { ansible_host: 10.10.0.22 }
      vars:
        ansible_network_os: cisco.ios.ios

    juniper_junos:
      hosts:
        ex-sw-01: { ansible_host: 10.10.1.11 }
        ex-sw-02: { ansible_host: 10.10.1.12 }
        ex-sw-03: { ansible_host: 10.10.1.13 }
        ex-sw-04: { ansible_host: 10.10.1.14 }
      vars:
        ansible_network_os: junipernetworks.junos.junos

    arista_eos:
      hosts:
        eos-sw-01: { ansible_host: 10.10.2.11 }
        eos-sw-02: { ansible_host: 10.10.2.12 }
      vars:
        ansible_network_os: arista.eos.eos
```

Credentials reference an Ansible Vault — define `vault_net_user` and `vault_net_password` in `group_vars/all/vault.yml` (encrypted with `ansible-vault encrypt`). Never commit plaintext credentials.

## Required collections

Make sure these are installed (one-time):

```bash
ansible-galaxy collection install cisco.ios junipernetworks.junos arista.eos
```

## Playbook

`push_ntp.yml`:

```yaml
---
- name: NTP — Cisco IOS-XE
  hosts: cisco_ios
  gather_facts: false
  vars:
    ntp_servers:
      - 10.50.0.10
      - 10.50.0.11
  tasks:
    - name: Configure NTP servers (Cisco)
      cisco.ios.ios_ntp_global:
        config:
          servers:
            - server: "{{ item }}"
              version: 4
        state: merged
      loop: "{{ ntp_servers }}"

- name: NTP — Juniper Junos (EX)
  hosts: juniper_junos
  gather_facts: false
  vars:
    ntp_servers:
      - 10.50.0.10
      - 10.50.0.11
  tasks:
    - name: Configure NTP servers (Junos)
      junipernetworks.junos.junos_ntp_global:
        config:
          servers:
            - server: "{{ item }}"
        state: merged
      loop: "{{ ntp_servers }}"

- name: NTP — Arista EOS
  hosts: arista_eos
  gather_facts: false
  vars:
    ntp_servers:
      - 10.50.0.10
      - 10.50.0.11
  tasks:
    - name: Configure NTP servers (Arista)
      arista.eos.eos_ntp_global:
        config:
          servers:
            - server: "{{ item }}"
        state: merged
      loop: "{{ ntp_servers }}"
```

`state: merged` is the right default — it adds NTP servers to whatever's already there without removing existing config. If you want to enforce *exactly* this list (replace any other NTP servers), use `state: replaced`.

## Dry-run first

Always dry-run before applying. The `--diff` flag is the magic here — it shows you the exact lines that would change on each device:

```bash
ansible-playbook -i inventory.yml push_ntp.yml --check --diff
```

Output for each host will look like:

```
TASK [Configure NTP servers (Cisco)] ***
--- before
+++ after
@@ -1,2 +1,4 @@
 ntp source Loopback0
+ntp server 10.50.0.10 version 4
+ntp server 10.50.0.11 version 4
```

If the diff is empty, the change is already in place — that's the idempotency you want. If it's wrong, fix the playbook before applying.

## Apply

```bash
ansible-playbook -i inventory.yml push_ntp.yml
```

## Verification

Add a verification play if you want assertion-style validation:

```yaml
- name: Verify NTP — Cisco
  hosts: cisco_ios
  gather_facts: false
  tasks:
    - name: Show NTP associations
      cisco.ios.ios_command:
        commands: show ntp associations
      register: ntp_status
    - name: Confirm both NTP servers present
      ansible.builtin.assert:
        that:
          - "'10.50.0.10' in ntp_status.stdout[0]"
          - "'10.50.0.11' in ntp_status.stdout[0]"
        fail_msg: "NTP servers not found on {{ inventory_hostname }}"
```

Equivalent verification on Junos uses `show ntp associations`; on Arista, also `show ntp associations`.

## Notes / trade-offs

- **`ios_ntp_global` vs older `ios_ntp`**: the `_global` resource module is the modern (5.0.0+ collection) declarative form. If you're on an older Ansible collection, fall back to `ios_ntp` with `state: present` per server.
- **Why not raw `ios_command` to push `ntp server` lines?** Resource modules detect drift and reconcile state. Raw command pushes don't — re-running them produces no diff but you have no proof they aligned with intent.
- **Hostname patterns**: real inventories typically use a CSV import or NetBox dynamic inventory rather than a static YAML. The structure above is fine for one-off use; for larger fleets use `nb_inventory` or write your own dynamic inventory plugin.
