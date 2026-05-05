ciscoconfaudit
published PyPI - Python Version Code style: black Imports: isort LICENSE Commit Activity PyPI - Version PyPI - Status Downloads Say Thanks!

Based on Use Cisco IOS XE Hardening Guide and some opinionated best practices.

This package gives an overview of the hardening techniques that can be used to secure a Cisco network device. Network security is not a one-layer thing, yet, it depends on multiple factors. If you harden your devices, then it is a good starting point that increases the overall security of the environment you manage.

Installation
Install from PyPi

$ pip install ciscoconfaudit
Usage
You can try out two examples in the repo in examples.

(.venv) $ python3 basic_online.py   # Parses config from a device (Uses netmiko)
(.venv) $ python3 basic_offline.py  # Parses config from text file
Example Output
Global Config Audit (Sample)	Interface-Level Audit
Global Config Audit	Interface Level Audit
Use Case
Ever been tired of checking whether the Cisco hardneing technqiues (here) are applied to your network devices one by one? This package is very handy in generating a tabular report for you.
Author
Osama Abbas

Credits
This package was inspired by jonarm from cisco-ios-audit.

Contributions
You are welcome to contribute to this Cisco Swiss army knife.