"""
Result formatters for AWS Operations Agent.
"""

from typing import Dict, List, Any
from datetime import datetime
import json


class ResultFormatter:
    """Base class for result formatters."""
    
    def format(self, data: Dict[str, Any]) -> str:
        """Format the result data."""
        raise NotImplementedError("Subclasses must implement format()")


class FQDNTraceFormatter(ResultFormatter):
    """Formatter for FQDN trace results in hierarchical format."""
    
    def __init__(self, max_width: int = 100):
        self.max_width = max_width
    
    def format(self, data: Dict[str, Any]) -> str:
        """Format FQDN trace result in hierarchical format."""
        if not data or "fqdn" not in data:
            return "No trace data available"
        
        fqdn = data.get("fqdn", "Unknown")
        trace_path = data.get("trace_path", [])
        timestamp = data.get("timestamp", datetime.utcnow().isoformat())
        
        lines = []
        lines.append("=" * self.max_width)
        lines.append(f"FQDN Trace: {fqdn}")
        lines.append(f"Timestamp: {timestamp}")
        lines.append("=" * self.max_width)
        lines.append("")
        
        if not trace_path:
            lines.append("No resources found in trace path")
            return "\n".join(lines)
        
        for idx, layer_data in enumerate(trace_path, 1):
            layer = layer_data.get("layer", "Unknown Layer")
            resource = layer_data.get("resource", "Unknown Resource")
            details = layer_data.get("details", {})
            status = layer_data.get("status", "success")
            error = layer_data.get("error")
            
            lines.append(f"{idx}. {layer}")
            lines.append("-" * (len(str(idx)) + len(layer) + 3))
            lines.append(f"   Resource: {resource}")
            
            if status == "error" and error:
                lines.append(f"   Status: ERROR - {error}")
            elif status == "partial":
                lines.append(f"   Status: PARTIAL - Some data unavailable")
            else:
                lines.append(f"   Status: OK")
            
            if details and status != "error":
                lines.append("   Details:")
                formatted_details = self._format_layer_details(layer, details)
                for detail_line in formatted_details:
                    lines.append(f"      {detail_line}")
            
            lines.append("")
        
        lines.append("=" * self.max_width)
        lines.append(f"Trace complete: {len(trace_path)} layer(s) discovered")
        lines.append("=" * self.max_width)
        
        return "\n".join(lines)
    
    def _format_layer_details(self, layer: str, details: Dict[str, Any]) -> List[str]:
        """Format layer-specific details."""
        lines = []
        
        if layer == "F5 WAF":
            lines.extend(self._format_f5_details(details))
        elif layer == "Route53":
            lines.extend(self._format_route53_details(details))
        elif layer == "CloudFront":
            lines.extend(self._format_cloudfront_details(details))
        elif "ALB" in layer or "NLB" in layer:
            lines.extend(self._format_elb_details(details))
        elif layer == "Backend":
            lines.extend(self._format_backend_details(details))
        else:
            for key, value in details.items():
                if isinstance(value, (dict, list)):
                    lines.append(f"{key}: {json.dumps(value, indent=2)}")
                else:
                    lines.append(f"{key}: {value}")
        
        return lines
    
    def _format_f5_details(self, details: Dict[str, Any]) -> List[str]:
        """Format F5 WAF details."""
        lines = []
        
        if "load_balancer_name" in details:
            lines.append(f"Load Balancer: {details['load_balancer_name']}")
        if "ves_endpoint" in details:
            lines.append(f"VES Endpoint: {details['ves_endpoint']}")
        if "namespace" in details:
            lines.append(f"Namespace: {details['namespace']}")
        if "domains" in details:
            lines.append(f"Domains: {', '.join(details['domains'])}")
        
        if "origin_pools" in details:
            lines.append("Origin Pools:")
            for pool in details["origin_pools"]:
                pool_name = pool.get("name", "Unknown")
                lines.append(f"  - {pool_name}")
                if "origins" in pool:
                    for origin in pool["origins"]:
                        public_name = origin.get("public_name", "Unknown")
                        port = origin.get("port", "Unknown")
                        lines.append(f"    -> {public_name}:{port}")
        
        return lines
    
    def _format_route53_details(self, details: Dict[str, Any]) -> List[str]:
        """Format Route53 details."""
        lines = []
        
        if "hosted_zone_id" in details:
            lines.append(f"Hosted Zone: {details['hosted_zone_id']}")
        
        if "records" in details:
            lines.append("DNS Records:")
            for record in details["records"]:
                record_type = record.get("type", "Unknown")
                value = record.get("value", "Unknown")
                ttl = record.get("ttl", "N/A")
                lines.append(f"  - {record_type}: {value} (TTL: {ttl})")
        
        return lines
    
    def _format_cloudfront_details(self, details: Dict[str, Any]) -> List[str]:
        """Format CloudFront details."""
        lines = []
        
        if "distribution_id" in details:
            lines.append(f"Distribution ID: {details['distribution_id']}")
        if "domain_name" in details:
            lines.append(f"Domain Name: {details['domain_name']}")
        if "status" in details:
            lines.append(f"Status: {details['status']}")
        
        if "aliases" in details and details["aliases"]:
            lines.append(f"Aliases: {', '.join(details['aliases'])}")
        
        if "origins" in details:
            lines.append("Origins:")
            for origin in details["origins"]:
                origin_id = origin.get("id", "Unknown")
                domain_name = origin.get("domain_name", "Unknown")
                protocol = origin.get("origin_protocol_policy", "Unknown")
                lines.append(f"  - {origin_id}")
                lines.append(f"    Domain: {domain_name}")
                lines.append(f"    Protocol: {protocol}")
        
        return lines
    
    def _format_elb_details(self, details: Dict[str, Any]) -> List[str]:
        """Format ELB (ALB/NLB) details."""
        lines = []
        
        if "load_balancer_name" in details:
            lines.append(f"Name: {details['load_balancer_name']}")
        if "load_balancer_arn" in details:
            lines.append(f"ARN: {details['load_balancer_arn']}")
        if "type" in details:
            lines.append(f"Type: {details['type']}")
        if "scheme" in details:
            lines.append(f"Scheme: {details['scheme']}")
        if "vpc_id" in details:
            lines.append(f"VPC: {details['vpc_id']}")
        if "account_id" in details:
            lines.append(f"Account: {details['account_id']}")
        
        if "target_groups" in details:
            lines.append("Target Groups:")
            for tg in details["target_groups"]:
                tg_name = tg.get("target_group_name", "Unknown")
                protocol = tg.get("protocol", "Unknown")
                port = tg.get("port", "Unknown")
                lines.append(f"  - {tg_name} ({protocol}:{port})")
                
                if "targets" in tg:
                    for target in tg["targets"]:
                        target_id = target.get("id", "Unknown")
                        target_port = target.get("port", "Unknown")
                        health = target.get("health_status", "Unknown")
                        lines.append(f"    -> {target_id}:{target_port} [{health}]")
        
        return lines
    
    def _format_backend_details(self, details: Dict[str, Any]) -> List[str]:
        """Format backend details."""
        lines = []
        
        if "backend_ips" in details:
            lines.append("Backend IPs:")
            for backend in details["backend_ips"]:
                ip = backend.get("ip", "Unknown")
                port = backend.get("port", "Unknown")
                health = backend.get("health", "Unknown")
                lines.append(f"  - {ip}:{port} [{health}]")
        
        return lines


class LogQueryFormatter(ResultFormatter):
    """Formatter for log query results in table format."""
    
    def __init__(self, max_rows: int = 100, max_width: int = 120):
        self.max_rows = max_rows
        self.max_width = max_width
    
    def format(self, data: Dict[str, Any]) -> str:
        """Format log query result in table format."""
        if not data:
            return "No log data available"
        
        query_type = data.get("query_type", "unknown")
        results = data.get("results", [])
        result_count = data.get("result_count", len(results))
        timestamp = data.get("timestamp", datetime.utcnow().isoformat())
        query_execution_id = data.get("query_execution_id", "N/A")
        
        lines = []
        lines.append("=" * self.max_width)
        lines.append(f"Log Query Results: {query_type}")
        lines.append(f"Query ID: {query_execution_id}")
        lines.append(f"Timestamp: {timestamp}")
        lines.append(f"Total Results: {result_count}")
        lines.append("=" * self.max_width)
        lines.append("")
        
        if not results:
            lines.append("No results found")
            lines.append("")
            lines.append("Suggestions:")
            lines.append("  - Try expanding the time range")
            lines.append("  - Check if the resource exists")
            lines.append("  - Verify filter parameters")
            return "\n".join(lines)
        
        display_results = results[:self.max_rows]
        if len(results) > self.max_rows:
            lines.append(f"Showing first {self.max_rows} of {result_count} results")
            lines.append("")
        
        if query_type == "vpc_flow_logs":
            table = self._format_vpc_flow_logs_table(display_results)
        elif query_type == "cloudfront_logs":
            table = self._format_cloudfront_logs_table(display_results)
        else:
            table = self._format_generic_table(display_results)
        
        lines.extend(table)
        lines.append("")
        lines.append("=" * self.max_width)
        
        return "\n".join(lines)
    
    def _format_vpc_flow_logs_table(self, results: List[Dict[str, Any]]) -> List[str]:
        """Format VPC Flow Logs as a table."""
        if not results:
            return ["No VPC Flow Logs to display"]
        
        columns = [
            ("Timestamp", 20),
            ("Source IP", 15),
            ("Dest IP", 15),
            ("Src Port", 8),
            ("Dst Port", 8),
            ("Protocol", 8),
            ("Action", 8)
        ]
        
        lines = []
        header = " | ".join(col[0].ljust(col[1]) for col in columns)
        lines.append(header)
        lines.append("-" * len(header))
        
        for result in results:
            row_values = [
                str(result.get("timestamp", "N/A"))[:20].ljust(20),
                str(result.get("source_ip", "N/A"))[:15].ljust(15),
                str(result.get("destination_ip", "N/A"))[:15].ljust(15),
                str(result.get("source_port", "N/A"))[:8].ljust(8),
                str(result.get("destination_port", "N/A"))[:8].ljust(8),
                str(result.get("protocol", "N/A"))[:8].ljust(8),
                str(result.get("action", "N/A"))[:8].ljust(8)
            ]
            lines.append(" | ".join(row_values))
        
        return lines
    
    def _format_cloudfront_logs_table(self, results: List[Dict[str, Any]]) -> List[str]:
        """Format CloudFront logs as a table."""
        if not results:
            return ["No CloudFront logs to display"]
        
        columns = [
            ("Date", 10),
            ("Time", 8),
            ("Method", 6),
            ("Host", 20),
            ("URI", 25),
            ("Status", 6),
            ("Client IP", 15)
        ]
        
        lines = []
        header = " | ".join(col[0].ljust(col[1]) for col in columns)
        lines.append(header)
        lines.append("-" * len(header))
        
        for result in results:
            row_values = [
                str(result.get("date", "N/A"))[:10].ljust(10),
                str(result.get("time", "N/A"))[:8].ljust(8),
                str(result.get("cs_method", "N/A"))[:6].ljust(6),
                str(result.get("cs_host", "N/A"))[:20].ljust(20),
                str(result.get("cs_uri_stem", "N/A"))[:25].ljust(25),
                str(result.get("sc_status", "N/A"))[:6].ljust(6),
                str(result.get("c_ip", "N/A"))[:15].ljust(15)
            ]
            lines.append(" | ".join(row_values))
        
        lines.append("")
        lines.append("Note: Additional fields available in full results:")
        lines.append("  cs_uri_query, x_edge_result_type, x_edge_detailed_result_type,")
        lines.append("  time_taken, time_to_first_byte, x_edge_location, x_forwarded_for")
        
        return lines
    
    def _format_generic_table(self, results: List[Dict[str, Any]]) -> List[str]:
        """Format generic results as a table."""
        if not results:
            return ["No results to display"]
        
        all_keys = set()
        for result in results:
            all_keys.update(result.keys())
        
        keys = sorted(all_keys)
        col_width = min(20, self.max_width // len(keys) if keys else 20)
        
        lines = []
        header = " | ".join(key[:col_width].ljust(col_width) for key in keys)
        lines.append(header)
        lines.append("-" * len(header))
        
        for result in results:
            row_values = [
                str(result.get(key, "N/A"))[:col_width].ljust(col_width)
                for key in keys
            ]
            lines.append(" | ".join(row_values))
        
        return lines


class IPInvestigationFormatter(ResultFormatter):
    """Formatter for IP investigation results in structured format."""
    
    def __init__(self, max_width: int = 100):
        self.max_width = max_width
    
    def format(self, data: Dict[str, Any]) -> str:
        """Format IP investigation result in structured format."""
        if not data or "ip_address" not in data:
            return "No IP investigation data available"
        
        ip_address = data.get("ip_address", "Unknown")
        source_type = data.get("source_type", "Unknown")
        details = data.get("details", {})
        timestamp = data.get("timestamp", datetime.utcnow().isoformat())
        
        lines = []
        lines.append("=" * self.max_width)
        lines.append(f"IP Investigation: {ip_address}")
        lines.append(f"Timestamp: {timestamp}")
        lines.append("=" * self.max_width)
        lines.append("")
        
        lines.append(f"Source Type: {source_type}")
        lines.append("")
        
        if source_type in ["ALB", "NLB"]:
            lines.extend(self._format_load_balancer_details(details))
        elif source_type == "CloudFront":
            lines.extend(self._format_cloudfront_ip_details(details))
        elif source_type == "F5_WAF":
            lines.extend(self._format_f5_ip_details(details))
        elif source_type in ["EC2", "RDS"]:
            lines.extend(self._format_aws_service_details(details))
        elif source_type == "Unknown":
            lines.extend(self._format_unknown_ip_details(details))
        else:
            lines.extend(self._format_generic_details(details))
        
        lines.append("")
        lines.append("=" * self.max_width)
        
        return "\n".join(lines)
    
    def _format_load_balancer_details(self, details: Dict[str, Any]) -> List[str]:
        """Format load balancer IP details."""
        lines = []
        lines.append("Load Balancer Details:")
        lines.append("-" * 30)
        
        if "load_balancer_name" in details:
            lines.append(f"  Name: {details['load_balancer_name']}")
        if "load_balancer_arn" in details:
            lines.append(f"  ARN: {details['load_balancer_arn']}")
        if "account_id" in details:
            lines.append(f"  Account ID: {details['account_id']}")
        if "type" in details:
            lines.append(f"  Type: {details['type']}")
        if "scheme" in details:
            lines.append(f"  Scheme: {details['scheme']}")
        if "vpc_id" in details:
            lines.append(f"  VPC: {details['vpc_id']}")
        
        if "target_groups" in details:
            lines.append("")
            lines.append("  Associated Target Groups:")
            for tg in details["target_groups"]:
                tg_name = tg.get("target_group_name", "Unknown")
                lines.append(f"    - {tg_name}")
        
        return lines
    
    def _format_cloudfront_ip_details(self, details: Dict[str, Any]) -> List[str]:
        """Format CloudFront IP details."""
        lines = []
        lines.append("CloudFront Details:")
        lines.append("-" * 30)
        
        if "edge_location" in details:
            lines.append(f"  Edge Location: {details['edge_location']}")
        
        if "distributions" in details and details["distributions"]:
            lines.append("")
            lines.append("  Associated Distributions:")
            for dist in details["distributions"]:
                lines.append(f"    - {dist}")
        
        lines.append("")
        lines.append("  Note: This IP belongs to AWS CloudFront's global CDN network")
        
        return lines
    
    def _format_f5_ip_details(self, details: Dict[str, Any]) -> List[str]:
        """Format F5 WAF IP details."""
        lines = []
        lines.append("F5 Distributed Cloud WAF Details:")
        lines.append("-" * 30)
        
        if "ves_endpoint" in details:
            lines.append(f"  VES Endpoint: {details['ves_endpoint']}")
        if "load_balancer_name" in details:
            lines.append(f"  Load Balancer: {details['load_balancer_name']}")
        if "namespace" in details:
            lines.append(f"  Namespace: {details['namespace']}")
        
        return lines
    
    def _format_aws_service_details(self, details: Dict[str, Any]) -> List[str]:
        """Format AWS service IP details."""
        lines = []
        lines.append("AWS Service Details:")
        lines.append("-" * 30)
        
        if "service" in details:
            lines.append(f"  Service: {details['service']}")
        if "region" in details:
            lines.append(f"  Region: {details['region']}")
        if "instance_id" in details:
            lines.append(f"  Instance ID: {details['instance_id']}")
        if "resource_id" in details:
            lines.append(f"  Resource ID: {details['resource_id']}")
        
        return lines
    
    def _format_unknown_ip_details(self, details: Dict[str, Any]) -> List[str]:
        """Format unknown IP details."""
        lines = []
        lines.append("External IP Details:")
        lines.append("-" * 30)
        
        if "reverse_dns" in details:
            lines.append(f"  Reverse DNS: {details['reverse_dns']}")
        
        if "whois" in details:
            whois = details["whois"]
            lines.append("")
            lines.append("  WHOIS Information:")
            if isinstance(whois, dict):
                for key, value in whois.items():
                    lines.append(f"    {key}: {value}")
            else:
                lines.append(f"    {whois}")
        
        lines.append("")
        lines.append("  Note: This IP does not belong to known AWS or F5 infrastructure")
        
        return lines
    
    def _format_generic_details(self, details: Dict[str, Any]) -> List[str]:
        """Format generic details."""
        lines = []
        lines.append("Details:")
        lines.append("-" * 30)
        
        for key, value in details.items():
            if isinstance(value, (dict, list)):
                lines.append(f"  {key}:")
                lines.append(f"    {json.dumps(value, indent=4)}")
            else:
                lines.append(f"  {key}: {value}")
        
        return lines


def format_fqdn_trace(data: Dict[str, Any], max_width: int = 100) -> str:
    """Format FQDN trace result."""
    formatter = FQDNTraceFormatter(max_width=max_width)
    return formatter.format(data)


def format_log_query(data: Dict[str, Any], max_rows: int = 100, max_width: int = 120) -> str:
    """Format log query result."""
    formatter = LogQueryFormatter(max_rows=max_rows, max_width=max_width)
    return formatter.format(data)


def format_ip_investigation(data: Dict[str, Any], max_width: int = 100) -> str:
    """Format IP investigation result."""
    formatter = IPInvestigationFormatter(max_width=max_width)
    return formatter.format(data)
