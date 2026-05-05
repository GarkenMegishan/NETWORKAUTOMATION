# Adding VLAN 75 to Catalyst 9300 Access Switches

## Configuration

Apply this config to both **sw-acc-01** and **sw-acc-02**:

```
! Target: sw-acc-01 / sw-acc-02 (Catalyst 9300, IOS-XE 17.6)
! Change: Add VLAN 75 (IoT_Sensors) and trunk over Po1 to core

vlan 75
 name IoT_Sensors
!
interface Port-channel1
 switchport trunk allowed vlan add 75
 description Trunk to Core
!
end
```

**Key points:**

- The `vlan 75` block creates the VLAN and names it. If VLAN 75 already exists, this re-applies the name (idempotent).
- `switchport trunk allowed vlan add 75` appends VLAN 75 to the existing trunk allowlist on Po1 without removing any existing VLANs. This is safer than `allowed vlan` followed by a fixed list.
- No interface-level config needed; Po1 is assumed already in `switchport mode trunk` and active. If Po1 doesn't exist yet or is down, verify physical member links are up with `show interface status | include Po1`.

---

## Verification Commands

Run these after applying the config to confirm VLAN and trunk state:

### 1. Confirm VLAN exists and is active
```
show vlan brief | include 75
```

**Expected output:**
```
75   IoT_Sensors              active    (member port list)
```

### 2. Confirm VLAN is trunked on Po1
```
show interface Po1 trunk
```

**Expected output:**
```
Port        Mode         Encapsulation  Status        Native vlan
Po1         on           802.1q          trunking      1

Port        Vlans allowed on trunk
Po1         1-75,1002-1005
...
```

Look for VLAN 75 in the "Vlans allowed on trunk" line.

### 3. Check physical bundle status
```
show etherchannel summary | include Po1
```

**Expected output:**
```
Po1(SU)         Eth     LACP     up     GigabitEthernet0/0/47(P)  GigabitEthernet0/0/48(P)
```

All member ports should show `(P)` for participating. If any show `(w)` for waiting or `(d)` for down, the bundle is degraded; investigate the physical links.

---

## Rollback Procedure

IOS-XE 17.6 supports config archive. Before applying changes:

### Pre-change snapshot
```
copy running-config flash:pre-change-vlan75-2026-05-05.cfg
```

### If the change breaks connectivity or VLAN traffic:
```
configure replace flash:pre-change-vlan75-2026-05-05.cfg force
```

**Explanation:** `configure replace` atomically loads the saved config and removes any lines not in it. This reverts both the VLAN and the trunk amendment in one shot.

### Alternative: Dead-man switch (if OOB console unavailable)
```
reload in 5
! Apply changes above
! Verify with show commands above
reload cancel
```

If connectivity drops, the switch automatically reloads in 5 minutes, reverting to startup-config. Once verified good, issue `reload cancel` to prevent the reload.

---

## Trade-offs

- **`switchport trunk allowed vlan add 75`** vs. **specifying the full VLAN list**: The `add` form is safer for incremental changes and doesn't require knowing the complete current state. Full lists are useful only if you're reconciling drift.
- **Port-channel vs. individual interface**: If Po1 is a bundle of physical links (e.g., Gi0/0/47–48), trunk config on Po1 automatically applies to all members. This is cleaner than configuring each member individually.
- **Reload-in vs. config archive**: Archive is preferred for non-routing changes (VLANs, trunk ports). Reload-in is simpler but requires a full revert to startup-config. Use reload-in only if archive is unavailable.

Save the output of your `show running-config` to a file before making changes; you'll need it for the change record and as a secondary rollback artifact.
