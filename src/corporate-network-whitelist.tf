# Corporate network egress allowlist (EXAMPLE / template)
#
# This is a Service Control Policy (SCP) that DENIES AWS API calls whose
# source IP is NOT on your organization's known egress allowlist. The agent's
# ip_lookup_tool parses the CIDR + trailing "// comment" entries below to tell
# you which corporate egress an IP belongs to.
#
# The IPs below are ILLUSTRATIVE placeholders (RFC 5737 / RFC 1918 ranges).
# >>> Replace them with your own organization's real egress CIDRs. <<<

locals {
    corporate_network_whitelist = {
        sid       = "DenyIfNotCorporateEgress"
        effect    = "Deny"
        actions   = ["*"]
        resources = ["*"]

        conditions = [
            {
                test     = "StringLike"
                variable = "aws:PrincipalArn"
                values   = [
                    "arn:aws:iam::*:role/aws-reserved/sso.amazonaws.com/*/AWSReservedSSO_*"
                ]
            },
            {
                test     = "Bool"
                variable = "aws:ViaAWSService"
                values   = ["false"]
            },
            {
                test     = "NotIpAddress"
                variable = "aws:SourceIp"
                values   = [
                    # --- SASE / secure web gateway egress (example) ---
                    "203.0.113.10/32",    // SASE PoP region-A egress
                    "203.0.113.11/32",    // SASE PoP region-B egress
                    "203.0.113.12/32",    // SASE PoP region-C egress

                    # --- Cloud VWAN / transit egress (example) ---
                    "198.51.100.20/32",   // VWAN non-prod egress region-A
                    "198.51.100.21/32",   // VWAN non-prod egress region-B

                    # --- Site NAT gateways (example) ---
                    "192.0.2.30/32",      // Office site 1 NAT GW
                    "192.0.2.31/32",      // Office site 2 NAT GW
                    "192.0.2.32/28",      // Branch offices NAT pool

                    # --- Corporate VPN egress (example) ---
                    "203.0.113.40/32",    // Remote-access VPN egress
                    "203.0.113.41/32",    // Break-glass admin egress

                    # --- On-prem data center egress (example, RFC1918 shown for illustration) ---
                    "198.51.100.50/32",   // DC-1 internet egress
                    "198.51.100.51/32",   // DC-2 internet egress
                ]
            }
        ]
    }
}
