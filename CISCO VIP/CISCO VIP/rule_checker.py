import re

def check_duplicate_ip(show_output, symptom, topology):
    """Checks if the output indicates duplicate IP addresses or conflict."""
    patterns = [
        r"(duplicate IP|IP address collision|same IP assigned|IP conflict)",
        r"duplicate address",
    ]
    for pattern in patterns:
        if re.search(pattern, show_output, re.IGNORECASE) or re.search(pattern, symptom, re.IGNORECASE):
            return {
                "rule_name": "Duplicate IP",
                "triggered": True,
                "evidence": f"Found duplicate IP indicator: '{pattern}' in data.",
                "severity": "High"
            }
    return {"rule_name": "Duplicate IP", "triggered": False}

def check_mask_mismatch(show_output, symptom, topology):
    """Checks if the output indicates subnet mask or scope mask mismatches."""
    patterns = [
        r"(wrong mask|mask mismatch|subnet mask mismatch|incorrect mask|subnet mismatch|wrong subnet)",
    ]
    for pattern in patterns:
        if re.search(pattern, show_output, re.IGNORECASE) or re.search(pattern, symptom, re.IGNORECASE):
            return {
                "rule_name": "Subnet Mask Mismatch",
                "triggered": True,
                "evidence": f"Found subnet mask/scope mismatch: '{pattern}' in data.",
                "severity": "Medium"
            }
    return {"rule_name": "Subnet Mask Mismatch", "triggered": False}

def check_gateway_mismatch(show_output, symptom, topology):
    """Checks if the output indicates a default gateway or default-router mismatch."""
    patterns = [
        r"(gateway mismatch|wrong default-router|incorrect default-router|incorrect gateway|wrong gateway|gateway configuration error)",
    ]
    for pattern in patterns:
        if re.search(pattern, show_output, re.IGNORECASE) or re.search(pattern, symptom, re.IGNORECASE):
            return {
                "rule_name": "Gateway Mismatch",
                "triggered": True,
                "evidence": f"Found default gateway/router mismatch: '{pattern}' in data.",
                "severity": "High"
            }
    return {"rule_name": "Gateway Mismatch", "triggered": False}

def check_interface_down(show_output, symptom, topology):
    """Checks if the output indicates inactive or down switch/router interfaces."""
    patterns = [
        r"(interface down|admin.*down|suspended|port inactive|inactive port|ports inactive|shutdown)",
    ]
    for pattern in patterns:
        if re.search(pattern, show_output, re.IGNORECASE) or re.search(pattern, symptom, re.IGNORECASE):
            return {
                "rule_name": "Interface Down",
                "triggered": True,
                "evidence": f"Found inactive/down interface indicator: '{pattern}' in data.",
                "severity": "High"
            }
    return {"rule_name": "Interface Down", "triggered": False}

def check_missing_vlan(show_output, symptom, topology):
    """Checks if the output indicates a missing or suspended VLAN."""
    patterns = [
        r"(missing vlan|vlan.*not found|vlan.*suspended|vlan.*disabled|no trunking|vlan.*not exist)",
    ]
    for pattern in patterns:
        if re.search(pattern, show_output, re.IGNORECASE) or re.search(pattern, symptom, re.IGNORECASE):
            return {
                "rule_name": "Missing VLAN",
                "triggered": True,
                "evidence": f"Found missing or disabled VLAN: '{pattern}' in data.",
                "severity": "High"
            }
    return {"rule_name": "Missing VLAN", "triggered": False}

def check_missing_route(show_output, symptom, topology):
    """Checks if the routing table is missing critical routes (static, dynamic, default)."""
    patterns = [
        r"(missing route|route not found|no route|gateway of last resort not set|missing default route|network unreachable|unreachable)",
    ]
    for pattern in patterns:
        if re.search(pattern, show_output, re.IGNORECASE) or re.search(pattern, symptom, re.IGNORECASE):
            return {
                "rule_name": "Missing Route",
                "triggered": True,
                "evidence": f"Found missing routing entry: '{pattern}' in data.",
                "severity": "High"
            }
    return {"rule_name": "Missing Route", "triggered": False}

def run_rule_checker(show_output, symptom, topology):
    """Runs all deterministic rules on the given case fields."""
    rules = [
        check_duplicate_ip,
        check_mask_mismatch,
        check_gateway_mismatch,
        check_interface_down,
        check_missing_vlan,
        check_missing_route,
    ]
    triggered = []
    for rule in rules:
        res = rule(show_output, symptom, topology)
        if res["triggered"]:
            # Clean up the response for storage
            del res["triggered"]
            triggered.append(res)
    return triggered
