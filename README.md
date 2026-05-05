# network-automation

A Claude skill for safe, vendor-correct network automation across Cisco IOS/IOS-XE/NX-OS, Juniper Junos, Arista EOS, Palo Alto PAN-OS, and Fortinet FortiOS.

The skill turns Claude into a focused network engineering collaborator: it produces idempotent device configs, structured Ansible/Nornir playbooks, ranked troubleshooting plans, and proper change-management runbooks — with rollback always built in. It's tuned for working enterprise network engineers, not generalists, and refuses to paraphrase across vendor syntaxes.

## What's a "Claude skill"?

A skill is a folder of markdown and helper files that Claude consults when relevant questions come up. You install a packaged `.skill` file once, and from then on Claude will load the skill's instructions whenever you ask something it covers — VLAN changes, BGP troubleshooting, firewall policies, multi-vendor migrations, etc.

The `.skill` file is just a renamed ZIP archive containing `SKILL.md` and bundled reference files. There's no service, no daemon — Claude reads the files when needed.

For a thorough explanation of how skills work end-to-end, read [`HOW-SKILLS-WORK.md`](HOW-SKILLS-WORK.md) in this repo. It's a tutorial built around exactly this skill.

## Installation

### Option 1: Download the latest release

Grab `network-automation.skill` from the [Releases](../../releases) page. In Cowork (Claude desktop), drag the file into a chat window — or use Settings → Skills → Install from file.

### Option 2: Build from source

```bash
git clone https://github.com/<your-username>/CW_NetworkAutomation.git
cd CW_NetworkAutomation
```

Then double-click `package-skill.bat` (Windows). This produces `network-automation.skill` in the repo root. Install it the same way as Option 1.

## What's covered

| Vendor | OS variants | Topics |
|---|---|---|
| Cisco | IOS, IOS-XE, NX-OS | VLANs, trunking, OSPF, BGP, vPC, EVPN, archive/replace rollback |
| Juniper | Junos (EX, MX, SRX, QFX) | Set-form configs, commit confirmed, OSPF, BGP, firewall filters, SRX zones |
| Arista | EOS | Config sessions, MLAG, EVPN/VXLAN spine-leaf, eAPI |
| Palo Alto | PAN-OS, Panorama | Address objects, App-ID-based policy, NAT, device groups, templates |
| Fortinet | FortiOS, FortiManager | Block syntax, firewall policies, VIPs, BGP, VDOMs |

Cross-cutting capabilities:

- Ansible Collections (`cisco.ios`, `junipernetworks.junos`, `arista.eos`, `paloaltonetworks.panos`, `fortinet.fortios`) — declarative resource modules over raw command-push
- Nornir / Netmiko / NAPALM playbook patterns
- Jinja2 device templates with structured YAML inventories
- BGP / OSPF / EVPN / MPLS / VXLAN design and troubleshooting
- Change-management runbooks with pre-validation, change steps, post-validation, and rollback
- Terraform / Pulumi for on-prem network gear (NSX-T, ACI, Panorama)

The skill is *not* for pure cloud networking (AWS VPC, Azure VNet) without on-prem touch — defer to general cloud IaC tools for those.

## Repository structure

```
CW_NetworkAutomation/
├── network-automation/          source folder for the skill
│   ├── SKILL.md                 main skill instructions
│   ├── references/              per-vendor reference files (loaded on demand)
│   │   ├── cisco.md
│   │   ├── juniper.md
│   │   ├── arista.md
│   │   ├── paloalto.md
│   │   └── fortinet.md
│   ├── assets/                  templates the skill includes in output
│   │   ├── runbook-template.md
│   │   ├── playbook-template.yml
│   │   └── jinja-template-example.j2
│   ├── scripts/                 helper Python scripts
│   │   ├── render_template.py
│   │   └── config_diff.py
│   └── evals/                   test prompts (excluded from the .skill bundle)
│       └── evals.json
├── package-skill.ps1            build script: folder -> .skill
├── package-skill.bat            double-clickable wrapper for the .ps1
├── HOW-SKILLS-WORK.md           tutorial on Claude skills, built around this one
├── README.md                    you are here
├── LICENSE
└── .gitignore
```

The `network-automation-workspace/` folder (eval results, baseline comparisons, the static review HTML) is generated when you run the eval loop and is gitignored — see `.gitignore`.

## Modifying and contributing

To change the skill:

1. Edit files inside `network-automation/`. The most common edits:
   - Tighten or expand the `description` field in `SKILL.md` (must stay ≤ 1024 characters)
   - Add a new vendor reference at `references/<vendor>.md` and link it from the main `SKILL.md`
   - Add a script under `scripts/` for repeatable tasks
2. Rebuild: double-click `package-skill.bat`
3. Reinstall the new `.skill` in Cowork (drag-drop will replace the prior version)
4. Verify with a real prompt in a fresh chat

If you want to be more rigorous, the eval loop in [`HOW-SKILLS-WORK.md` §10](HOW-SKILLS-WORK.md) walks through how to compare with-skill vs baseline outputs on a fixed set of prompts.

## Safety model

This skill produces *text* — configs, playbooks, runbooks. It does not push changes to live devices, run commands on your network, or hold credentials. Every output is for you to review and apply manually.

Operating principles baked into the skill (read `network-automation/SKILL.md` for the canonical list):

- Idempotence beats cleverness — declarative resource modules over raw command pushes
- Changes are reviewed before they're pushed — `commit confirmed`, `configure replace`, `configure session`
- State, then change — diagnostic output beats guessing
- Vendor syntax is not interchangeable — refuse to paraphrase across vendors
- Explain trade-offs — name the alternative and why it wasn't chosen

## License

See [`LICENSE`](LICENSE).

## Credits

Built collaboratively with Claude (Anthropic) using the [skill-creator](https://github.com/anthropics/skills) workflow. The vendor reference files were authored from first-hand operational practice — corrections and additions welcome via PR.
