# VLAN 75 Configuration for Catalyst 9300 Access Switches

## Configuration Summary

You'll need to push configuration to add VLAN 75 ("IoT_Sensors") on both access switches and ensure it's trunked over the Port Channel to the core.

## Configuration to Push

### Configuration Block (Apply to sw-acc-01 and sw-acc-02)

```
! VLAN creation
vlan 75
  name IoT_Sensors
  exit

! Port-Channel interface configuration
interface Port-channel 1
  description Trunk to Core
  switchport mode trunk
  switchport trunk allowed vlan add 75
  exit
```

### Applied to Individual Member Ports (if needed)

If your Po1 is built from individual Ethernet interfaces, ensure those interfaces are added to the port-channel:

```
interface range Ethernet1/1-2
  description Po1 Member
  channel-group 1 mode active
  no shutdown
  exit
```

**Note:** On Catalyst 9300 running IOS-XE 17.6, if Po1 already exists and is trunking, you only need to add VLAN 75 to the allowed list. If Po1 doesn't exist, create it first using the above port-channel configuration.

## Verification Commands

Run these commands on both switches to confirm successful deployment:

```
! Verify VLAN exists
show vlan id 75
show vlan brief | include IoT_Sensors

! Verify Port-Channel status
show interface port-channel 1
show etherchannel summary

! Verify VLAN is allowed on trunk
show interface port-channel 1 trunk
show interfaces trunk

! Verify member ports are bundled
show etherchannel 1 detail
show interface port-channel 1 status

! Confirm switchport mode and encapsulation
show interfaces port-channel 1 switchport
```

**Expected output verification:**
- `show vlan id 75` should display the VLAN with name "IoT_Sensors"
- `show interface port-channel 1 trunk` should list VLAN 75 in the "Vlans allowed on trunk" output
- `show etherchannel summary` should show Po1 with status "SU" (suspended, up) or "U" (up) with all member ports active
- `show interface port-channel 1` should show "up/up" status

## Safe Rollback Procedure

If you lose access after the configuration change, follow this rollback strategy:

### Method 1: Configuration Rollback (Preferred)

```
! Access the switch via console or out-of-band management
enable
configure terminal
  no vlan 75
  interface Port-channel 1
    no switchport trunk allowed vlan add 75
    (or: switchport trunk allowed vlan remove 75)
  exit
exit
write memory
```

### Method 2: Full Configuration Restore

If you need to revert completely and have a backup:

```
copy flash:config.backup running-config
```

Then confirm the load and save:

```
write memory
reload
```

### Prevention Best Practices

1. **Always have console access available** – Don't rely solely on SSH/in-band management when making trunk changes
2. **Backup configuration before changes:**
   ```
   copy running-config flash:config.backup
   ```
3. **Use out-of-band management** – If available, maintain a management network separate from the data VLAN
4. **Test on one switch first** – Deploy to sw-acc-01, verify for 5-10 minutes, then apply to sw-acc-02
5. **Prepare rollback commands** – Have them ready in a notepad before you start
6. **Verify core side acceptance** – Confirm the core switch recognizes the new VLAN on its trunk interface to Po1

### If You Lose SSH Access

If the switch becomes unreachable:

- **Use console cable** to connect directly and execute the rollback commands above
- **Power cycle with caution** – Only as last resort; ensure the configuration is saved before power-cycling
- **Check if VLAN is on management interface** – If VLAN 75 inadvertently took over the management IP, access via console is essential

## Key Reminders for IOS-XE 17.6

- Catalyst 9300 uses modern IOS-XE with standard Cisco syntax
- Port-Channel numbering starts at 1; confirm yours is correctly numbered
- The `switchport trunk allowed vlan add` command appends to existing allowed VLANs (doesn't overwrite)
- Always save configuration: `write memory` or `copy running-config startup-config`
- Etherchannel must be configured consistently on both ends of the trunk

This approach keeps your changes minimal, easily reversible, and well-documented for operational clarity.
