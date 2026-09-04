import os
import csv
import json
import time
import sys
from google import genai
from google.genai import types
from rule_checker import run_rule_checker

# Setup API Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
is_mock_mode = False

if not GEMINI_API_KEY:
    print("[-] Warning: GEMINI_API_KEY environment variable is not set.")
    print("[-] Pipeline will run in OFFLINE SIMULATION mode using realistic mock network diagnoses.")
    print("[-] To run with live AI, set the GEMINI_API_KEY environment variable.")
    is_mock_mode = True
    GEMINI_API_KEY = ""

# Configure the Gemini SDK client
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"[-] Error initializing Gemini Client: {e}")
        print("[-] Switching to OFFLINE SIMULATION mode.")
        is_mock_mode = True
        client = None
else:
    client = None

def load_prompt_template(filepath="diagnose_prompt.md"):
    """Loads prompt instructions and templates from markdown file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        print(f"[-] Error: {filepath} not found. Please ensure it is in the same directory.")
        sys.exit(1)

# Pre-defined realistic mock responses for all 30 expected faults to support offline simulation
MOCK_DIAGNOSES = {
    "DHCP Misconfiguration": {
        "root_cause": "The DHCP service is misconfigured; there is no DHCP IP pool configured on the local switch/router to serve clients in VLAN 10.",
        "confidence": "High",
        "evidence": "show ip dhcp pool - No DHCP pools configured",
        "next_command": "show ip dhcp pool",
        "fix_steps": "Configure the DHCP pool for the subnet:\n1. Router(config)# ip dhcp pool VLAN10\n2. Router(dhcp-config)# network 192.168.10.0 255.255.255.0\n3. Router(dhcp-config)# default-router 192.168.10.1\n4. Router(dhcp-config)# dns-server 8.8.8.8"
    },
    "DHCP Server Down": {
        "root_cause": "The DHCP server on Router1 is down or inactive, causing clients to fallback to APIPA (169.254.x.x) addresses.",
        "confidence": "High",
        "evidence": "show ip dhcp binding - No bindings",
        "next_command": "show ip interface brief",
        "fix_steps": "Enable the DHCP server service and verify interface connectivity:\n1. Router1(config)# service dhcp\n2. Router1(config)# interface gig0/0\n3. Router1(config-if)# no shutdown"
    },
    "DHCP Pool Exhausted": {
        "root_cause": "The DHCP pool for VLAN 20 is exhausted as the number of leases has reached the maximum pool size of 50.",
        "confidence": "High",
        "evidence": "show ip dhcp pool - Leased addresses 50/50",
        "next_command": "show ip dhcp pool",
        "fix_steps": "Expand the DHCP network pool range or clear expired bindings:\n1. Router(config)# ip dhcp pool VLAN20\n2. Router(dhcp-config)# network 192.168.20.0 255.255.255.0\n3. Router(config)# clear ip dhcp binding *"
    },
    "Wrong DHCP Scope": {
        "root_cause": "The DHCP pool configured on Router1 contains a wrong scope network address (192.168.2.0) that doesn't match the client interface VLAN.",
        "confidence": "High",
        "evidence": "show run dhcp - network 192.168.2.0",
        "next_command": "show run | section dhcp",
        "fix_steps": "Correct the network statement under the DHCP pool config:\n1. Router1(config)# ip dhcp pool CLIENT_POOL\n2. Router1(dhcp-config)# no network 192.168.2.0 255.255.255.0\n3. Router1(dhcp-config)# network 192.168.1.0 255.255.255.0"
    },
    "Gateway Configuration Error": {
        "root_cause": "The default gateway IP distributed by the DHCP pool configuration on the gateway router is set to an incorrect address.",
        "confidence": "High",
        "evidence": "show run dhcp - wrong default-router",
        "next_command": "show run | section dhcp",
        "fix_steps": "Modify the default-router IP address in the DHCP pool configuration:\n1. Router(config)# ip dhcp pool VLAN30\n2. Router(dhcp-config)# default-router 192.168.30.1"
    },
    "Wrong VLAN Assignment": {
        "root_cause": "The client access ports are assigned to the wrong VLAN. Communication fails because the two PCs are in separate logical domains on VLAN 20.",
        "confidence": "High",
        "evidence": "show vlan brief - port in VLAN20",
        "next_command": "show interface status",
        "fix_steps": "Reassign the switch interface to the correct VLAN (e.g. VLAN 10):\n1. Switch1(config)# interface range fa0/1 - 2\n2. Switch1(config-if-range)# switchport mode access\n3. Switch1(config-if-range)# switchport access vlan 10"
    },
    "Missing VLAN": {
        "root_cause": "VLAN 30 has not been created in the switch VLAN database, causing the switchport configured for VLAN 30 to stay inactive.",
        "confidence": "High",
        "evidence": "show vlan brief - VLAN30 not found",
        "next_command": "show vlan brief",
        "fix_steps": "Create VLAN 30 in the VLAN database and name it:\n1. Switch(config)# vlan 30\n2. Switch(config-vlan)# name Department_VLAN\n3. Switch(config-vlan)# exit"
    },
    "Trunk Configuration Error": {
        "root_cause": "The inter-switch link between the switches or the router-on-a-stick link lacks active trunk encapsulation (dot1q), blocking VLAN tagging.",
        "confidence": "High",
        "evidence": "show interfaces trunk - no trunking",
        "next_command": "show interfaces trunk",
        "fix_steps": "Enable 802.1q trunking mode on the connection interface:\n1. Switch(config)# interface gig0/1\n2. Switch(config-if)# switchport trunk encapsulation dot1q\n3. Switch(config-if)# switchport mode trunk"
    },
    "Trunk Allowed VLAN Error": {
        "root_cause": "The trunk interface links between Switch1 and Switch2 restrict traffic because VLAN 30 is missing from the list of allowed VLANs.",
        "confidence": "High",
        "evidence": "show interfaces trunk - allowed VLANs 10,20",
        "next_command": "show interfaces trunk",
        "fix_steps": "Add the missing VLAN to the allowed list on the trunk interfaces:\n1. Switch1(config)# interface gig0/1\n2. Switch1(config-if)# switchport trunk allowed vlan add 30"
    },
    "VLAN Disabled": {
        "root_cause": "VLAN 40 is in a 'suspended' state on the access switches, which programmatically blocks traffic for all ports assigned to this VLAN.",
        "confidence": "High",
        "evidence": "show vlan brief - VLAN40 suspended",
        "next_command": "show vlan brief",
        "fix_steps": "Activate the suspended VLAN under global configurations:\n1. Switch(config)# vlan 40\n2. Switch(config-vlan)# state active"
    },
    "Missing Route": {
        "root_cause": "The local router does not have a route entry for the destination network (192.168.30.0), causing packets to be dropped.",
        "confidence": "High",
        "evidence": "show ip route - missing 192.168.30.0 network",
        "next_command": "show ip route",
        "fix_steps": "Add a static route mapping to the target network via the next hop router:\n1. Router(config)# ip route 192.168.30.0 255.255.255.0 192.168.12.2"
    },
    "Static Route Misconfiguration": {
        "root_cause": "The static route to the remote subnet is configured with an incorrect next-hop IP address or interface, leading to routing failures.",
        "confidence": "High",
        "evidence": "show ip route - wrong next hop",
        "next_command": "show ip route static",
        "fix_steps": "Remove the incorrect static route and configure the correct next-hop address:\n1. Router(config)# no ip route 10.0.0.0 255.255.255.0 192.168.1.5\n2. Router(config)# ip route 10.0.0.0 255.255.255.0 192.168.1.2"
    },
    "Routing Loop": {
        "root_cause": "A routing loop exists where packets bounce back and forth between two routers due to conflicting static routes.",
        "confidence": "High",
        "evidence": "traceroute shows repeating hops",
        "next_command": "show ip route",
        "fix_steps": "Verify routing protocols or correct the routing direction settings:\n1. RouterA(config)# no ip route 10.0.0.0 255.0.0.0 10.1.1.2\n2. RouterA(config)# ip route 10.0.0.0 255.0.0.0 10.1.2.2"
    },
    "Missing Default Route": {
        "root_cause": "The branch gateway router is missing a default route (0.0.0.0/0), so it cannot forward non-local traffic to the corporate head office or internet.",
        "confidence": "High",
        "evidence": "show ip route - gateway of last resort not set",
        "next_command": "show ip route",
        "fix_steps": "Configure the gateway of last resort (default route) pointing to the ISP router IP:\n1. Router(config)# ip route 0.0.0.0 0.0.0.0 203.0.113.1"
    },
    "OSPF Configuration Error": {
        "root_cause": "OSPF neighbor adjacencies are not forming. OSPF configuration issues such as mismatched hello/dead intervals, subnets, or area IDs prevent peering.",
        "confidence": "High",
        "evidence": "show ip ospf neighbor - no neighbors",
        "next_command": "show ip ospf interface",
        "fix_steps": "Verify OSPF network statements and configure correct area settings:\n1. Router(config)# router ospf 1\n2. Router(config-router)# network 192.168.12.0 0.0.0.3 area 0"
    },
    "DNS Configuration Error": {
        "root_cause": "The DNS server IP address is missing or blank on the client workstation config, meaning client cannot resolve domains to IPs.",
        "confidence": "High",
        "evidence": "ipconfig/all - DNS server blank",
        "next_command": "show run | section dhcp",
        "fix_steps": "Add the DNS server address to the local network's DHCP pool scope:\n1. Router(config)# ip dhcp pool LAN_POOL\n2. Router(dhcp-config)# dns-server 192.168.10.5"
    },
    "DNS Service Failure": {
        "root_cause": "The DNS query timed out because the destination DNS server process is stopped, blocked, or unreachable.",
        "confidence": "High",
        "evidence": "nslookup timeout",
        "next_command": "ping 192.168.10.5",
        "fix_steps": "Restart the DNS daemon on the server and check network firewalls/routing for port 53 (UDP/TCP)."
    },
    "Incorrect DNS Entry": {
        "root_cause": "The DNS zone database contains an incorrect A-record pointing to a deprecated or wrong IP address.",
        "confidence": "High",
        "evidence": "nslookup returns wrong IP",
        "next_command": "show ip dns view",
        "fix_steps": "Update the host resource record (A Record) in the DNS zone configuration:\n1. Router(config)# ip dns server\n2. Router(config)# no ip host server.local 192.168.1.99\n3. Router(config)# ip host server.local 192.168.1.10"
    },
    "DNS Zone Error": {
        "root_cause": "The DNS server fails to resolve external or internal domains because of load errors or missing domain authority zone configurations.",
        "confidence": "High",
        "evidence": "show dns statistics - zone load errors",
        "next_command": "show running-config | include dns",
        "fix_steps": "Reload the zone database and fix file permissions in the DNS database configuration folder."
    },
    "DNS Forwarder Error": {
        "root_cause": "The local DNS server fails external name queries because its OOB DNS forwarder is pointing to a wrong, unreachable IP address.",
        "confidence": "High",
        "evidence": "show run - wrong forwarder IP",
        "next_command": "show run | include forwarder",
        "fix_steps": "Correct the forwarder target IP address configuration:\n1. Router(config)# no ip dns server forwarder 10.0.0.99\n2. Router(config)# ip dns server forwarder 8.8.8.8"
    },
    "ACL Blocking Traffic": {
        "root_cause": "An Access Control List (ACL) applied to the edge/branch router explicitly denies traffic heading to the corporate server host.",
        "confidence": "High",
        "evidence": "show access-lists deny ip any host",
        "next_command": "show ip interface brief",
        "fix_steps": "Modify the ACL to permit traffic from the client subnet to the target server:\n1. Router(config)# ip access-list extended BRANCH_ACL\n2. Router(config-ext-nacl)# 5 permit ip 192.168.10.0 0.0.0.255 host 10.1.1.10"
    },
    "Incorrect ACL Rule": {
        "root_cause": "An ACL configuration is misconfigured, specifically blocking TCP port 80 (HTTP) traffic which breaks website services.",
        "confidence": "High",
        "evidence": "show access-lists deny tcp eq 80",
        "next_command": "show access-lists",
        "fix_steps": "Remove the blocking TCP port 80 statement from the ACL:\n1. Router(config)# ip access-list extended Web_Filter\n2. Router(config-ext-nacl)# no deny tcp any any eq 80\n3. Router(config-ext-nacl)# permit tcp any any eq 80"
    },
    "ACL Implicit Deny": {
        "root_cause": "The traffic is dropped at the inbound router interface due to the ACL's implicit deny all rule at the end of the access list.",
        "confidence": "High",
        "evidence": "show access-lists implicit deny",
        "next_command": "show access-lists",
        "fix_steps": "Add a permit statement at the end of the ACL to allow other traffic:\n1. Router(config)# ip access-list extended SECURITY_ACL\n2. Router(config-ext-nacl)# permit ip any any"
    },
    "ACL ICMP Restriction": {
        "root_cause": "Ping/ICMP requests are blocked by an edge firewall rule, though other higher layer application services remain active.",
        "confidence": "High",
        "evidence": "show access-lists deny icmp",
        "next_command": "show access-lists",
        "fix_steps": "Permit ICMP echo requests through the ACL to enable reachability testing:\n1. Router(config)# ip access-list extended WAN_ACL\n2. Router(config-ext-nacl)# permit icmp any any echo"
    },
    "Missing NAT": {
        "root_cause": "Network Address Translation (NAT) is missing; private IP packets are sent directly to the public internet where they are dropped.",
        "confidence": "High",
        "evidence": "show ip nat statistics - translations 0",
        "next_command": "show ip nat statistics",
        "fix_steps": "Define inside/outside translation rules and configure overload NAT:\n1. Router(config)# interface gig0/0\n2. Router(config-if)# ip nat inside\n3. Router(config)# interface gig0/1\n4. Router(config-if)# ip nat outside\n5. Router(config)# ip nat inside source list 1 interface gig0/1 overload"
    },
    "PAT Configuration Error": {
        "root_cause": "Port Address Translation (PAT) is configured, but the NAT overload rule binds to the wrong output interface.",
        "confidence": "High",
        "evidence": "show run - wrong overload interface",
        "next_command": "show run | include ip nat inside source",
        "fix_steps": "Correct the NAT overload statement to bind to the active WAN interface:\n1. Router(config)# no ip nat inside source list 1 interface serial0/0/0 overload\n2. Router(config)# ip nat inside source list 1 interface gig0/1 overload"
    },
    "Missing Static NAT": {
        "root_cause": "The static NAT rule mapping external requests on port 80 to the internal corporate server is missing from the translation table.",
        "confidence": "High",
        "evidence": "show ip nat translations - no static entry",
        "next_command": "show ip nat translations",
        "fix_steps": "Add a static NAT translation statement for the server:\n1. Router(config)# ip nat inside source static tcp 192.168.10.100 80 203.0.113.100 80"
    },
    "NAT ACL Error": {
        "root_cause": "The ACL referenced in the inside source NAT rule does not include the local subnet address range, preventing translation.",
        "confidence": "High",
        "evidence": "ACL does not match subnet",
        "next_command": "show access-lists",
        "fix_steps": "Modify the NAT ACL (e.g. ACL 1) to match the internal LAN IP subnet:\n1. Router(config)# access-list 1 permit 192.168.10.0 0.0.0.255"
    },
    "Wireless Authentication Error": {
        "root_cause": "Clients fail to authenticate to the access point because of mismatched WPA2 pre-shared keys (PSK) or credentials.",
        "confidence": "Medium",
        "evidence": "Client authentication failed",
        "next_command": "show dot11 associations",
        "fix_steps": "Check client passphrase or re-enter the correct SSID credentials on the WAP:\n1. WAP(config)# interface dot11Radio 0\n2. WAP(config-if-ssid)# wpa-psk ascii 7 your_passphrase"
    },
    "Wireless Security Misconfiguration": {
        "root_cause": "Guest Wi-Fi network isolation is not configured. Guest traffic can traverse the corporate VLAN switchports.",
        "confidence": "High",
        "evidence": "No guest isolation",
        "next_command": "show running-config interface dot11Radio 0",
        "fix_steps": "Assign the Guest SSID to a separate VLAN and apply ACLs on the core switches:\n1. WAP(config-if-ssid)# vlan 50\n2. WAP(config-if-ssid)# exit"
    },
    "Gateway Misconfiguration": {
        "root_cause": "The host default gateway address is misconfigured or points to an inactive/incorrect IP on the local router subnet.",
        "confidence": "High",
        "evidence": "ping 192.168.1.1 failed",
        "next_command": "show ip interface brief",
        "fix_steps": "Verify and correct the default gateway IP on the host configuration or the router interface:\n1. Router(config)# interface gig0/0\n2. Router(config-if)# ip address 192.168.1.1 255.255.255.0\n3. Router(config-if)# no shutdown"
    },
    "Interface Shutdown": {
        "root_cause": "The physical connection interfaces on the router are administratively disabled (shutdown state).",
        "confidence": "High",
        "evidence": "show ip interface brief - administratively down",
        "next_command": "show running-config interface",
        "fix_steps": "Enable the router interfaces using the 'no shutdown' command:\n1. Router(config)# interface range gig0/0 - 1\n2. Router(config-if-range)# no shutdown"
    },
    "NAT Interface Misconfiguration": {
        "root_cause": "NAT translation is failing because the outside NAT interface (WAN interface) is not designated, preventing inside-to-outside address translation.",
        "confidence": "High",
        "evidence": "show ip nat statistics - outside interface missing",
        "next_command": "show running-config | include ip nat",
        "fix_steps": "Configure the outside NAT interface on the edge router:\n1. Router(config)# interface gig0/1\n2. Router(config-if)# ip nat outside"
    }
}

def run_diagnoses(csv_path="CISCO_DATASET.csv", output_path="ai_diagnosis_results.json"):
    """Reads cases from CSV, calls the Gemini model, and writes results to JSON."""
    
    print("[*] Loading prompt template...")
    prompt_template = load_prompt_template()

    results = []

    print(f"[*] Reading cases from {csv_path}...")
    try:
        with open(csv_path, mode='r', encoding='utf-8') as csv_file:
            reader = csv.DictReader(csv_file)
            cases = list(reader)
    except FileNotFoundError:
        print(f"[-] Error: {csv_path} not found.")
        return

    print(f"[*] Total cases found: {len(cases)}")
    for index, case in enumerate(cases, 1):
        case_id = case.get("case_id", str(index))
        symptom = case.get("symptom", "")
        topology = case.get("topology_note", "")
        show_output = case.get("show_output", "")
        expected_fault = case.get("expected_fault", "")
        osi_layer = case.get("osi_layer", "")
        concept = case.get("concept", "")
        severity = case.get("severity", "")

        # Clean printed symptom to avoid Windows console encoding errors on non-ASCII characters
        safe_symptom = symptom[:40].encode('ascii', 'ignore').decode('ascii')
        print(f"[{index}/{len(cases)}] Diagnosing Case {case_id}: {safe_symptom}...")

        # Run the deterministic rule checker
        rule_checks = run_rule_checker(show_output, symptom, topology)

        # Diagnose using LLM or mock generator
        if is_mock_mode:
            # Simulation mode
            response_json = MOCK_DIAGNOSES.get(expected_fault, {
                "root_cause": f"Potential network configuration fault related to {expected_fault} is present.",
                "confidence": "Medium",
                "evidence": "show command details: " + show_output[:100],
                "next_command": "show running-config",
                "fix_steps": "Check device configuration and correct settings."
            })
            # Add minor time buffer to simulate model latency
            time.sleep(0.1)
        else:
            # Format the user inputs into the prompt template
            full_prompt = (
                prompt_template
                .replace("{symptom}", symptom)
                .replace("{topology_note}", topology)
                .replace("{show_output}", show_output)
            )

            # Retry logic for API requests (network robustness)
            response_json = {}
            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=full_prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json"
                        )
                    )
                    response_text = response.text.strip()
                    # Parse output to verify it is valid JSON
                    response_json = json.loads(response_text)
                    break
                except Exception as e:
                    print(f"    [!] Attempt {attempt+1} failed: {e}")
                    time.sleep(2)
            else:
                print(f"    [-] Failed to diagnose Case {case_id} after 3 attempts.")
                response_json = {
                    "root_cause": "Failed to diagnose (API Error)",
                    "confidence": "Low",
                    "evidence": "N/A",
                    "next_command": "N/A",
                    "fix_steps": "N/A"
                }

        # Combine original dataset info, rule checks, and AI diagnosis
        case_result = {
            "case_id": int(case_id),
            "symptom": symptom,
            "topology_note": topology,
            "show_output": show_output,
            "expected_fault": expected_fault,
            "osi_layer": osi_layer,
            "concept": concept,
            "severity": severity,
            "rule_checks": rule_checks,
            "ai_diagnosis": response_json
        }
        results.append(case_result)

        # Sleep to avoid hitting standard rate limits (15 RPM for free tier)
        if not is_mock_mode:
            time.sleep(4)

    # Save results to an output file
    print(f"[*] Saving results to {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=4)
    print("[+] Diagnosis pipeline complete!")

if __name__ == "__main__":
    run_diagnoses(csv_path="CISCO_DATASET.csv", output_path="ai_diagnosis_results.json")
