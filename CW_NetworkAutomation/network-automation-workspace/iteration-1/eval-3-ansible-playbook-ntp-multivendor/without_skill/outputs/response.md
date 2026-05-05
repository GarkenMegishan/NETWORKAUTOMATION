# Multi-vendor NTP Push Playbook

This playbook pushes NTP server configuration to a mixed inventory of Cisco IOS-XE, Juniper EX, and Arista 7050 switches.

## Inventory

```yaml
# inventory.yml
all:
  children:
    cisco:
      hosts:
        ios-01:
        ios-02:
        ios-03:
        ios-04:
        ios-05:
        ios-06:
        ios-07:
        ios-08:
        ios-09:
        ios-10:
        ios-11:
        ios-12:
      vars:
        ansible_network_os: ios
        ansible_connection: network_cli

    juniper:
      hosts:
        ex-01:
        ex-02:
        ex-03:
        ex-04:
      vars:
        ansible_network_os: junos
        ansible_connection: netconf

    arista:
      hosts:
        eos-01:
        eos-02:
      vars:
        ansible_network_os: eos
        ansible_connection: network_cli
```

You'll want to add `ansible_host` for each device with the actual IP. Set `ansible_user` and `ansible_password` either in inventory, in group_vars, or pass at runtime.

## Playbook

```yaml
---
- name: Push NTP config to Cisco IOS-XE
  hosts: cisco
  gather_facts: no
  vars:
    ntp_servers:
      - 10.50.0.10
      - 10.50.0.11
  tasks:
    - name: Configure NTP servers
      ios_config:
        lines:
          - "ntp server {{ item }}"
        save_when: modified
      loop: "{{ ntp_servers }}"

- name: Push NTP config to Juniper EX
  hosts: juniper
  gather_facts: no
  vars:
    ntp_servers:
      - 10.50.0.10
      - 10.50.0.11
  tasks:
    - name: Configure NTP servers
      junos_config:
        lines:
          - "set system ntp server {{ item }}"
        comment: "Add NTP server"
      loop: "{{ ntp_servers }}"

- name: Push NTP config to Arista EOS
  hosts: arista
  gather_facts: no
  vars:
    ntp_servers:
      - 10.50.0.10
      - 10.50.0.11
  tasks:
    - name: Configure NTP servers
      eos_config:
        lines:
          - "ntp server {{ item }}"
        save_when: modified
      loop: "{{ ntp_servers }}"
```

## How to dry-run

Use `--check` to do a dry-run, and `--diff` to see what would change:

```
ansible-playbook -i inventory.yml ntp_push.yml --check --diff
```

This will report which devices would have changes applied without actually applying them. After verifying the diff looks right, run again without `--check`.

## Required collections

Make sure you have the relevant Ansible collections installed:

```
ansible-galaxy collection install cisco.ios
ansible-galaxy collection install junipernetworks.junos
ansible-galaxy collection install arista.eos
```

## Notes

- The `ios_config`, `junos_config`, and `eos_config` modules are part of the official collections. They'll be invoked as `cisco.ios.ios_config`, etc., depending on your Ansible version.
- For SSH credentials, use `ansible-vault` for the password. Don't hardcode passwords in inventory or playbooks.
- The `save_when: modified` argument writes config to startup only if changes were made.
- For Juniper, you can use NETCONF (port 830) instead of CLI. Set `ansible_connection: netconf` in the inventory.

## Troubleshooting

If the playbook fails:
- Check connectivity: `ansible cisco -m ping`
- Verify collection installed: `ansible-galaxy collection list`
- For Juniper: ensure NETCONF is enabled with `set system services netconf ssh`
- For Arista: enable eAPI with `management api http-commands` if using HTTPS connection

You can also add a verification step at the end to run `show ntp associations` on each device and confirm the servers are present.
